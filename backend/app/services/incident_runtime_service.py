"""M9 live ingestion and explicit close; historical reads never reach this runtime."""
import asyncio
import json
import logging
from collections import deque
from contextlib import suppress
from datetime import datetime, UTC
from time import monotonic

from fastapi import HTTPException
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.services.incident_service import IncidentService
from app.models.incident import Incident

logger = logging.getLogger("uvicorn.error")


class IncidentRuntimeService:
    def __init__(self, realtime):
        self.realtime = realtime
        self.engine = realtime.engine
        self.factory = realtime.telemetry.session_factory
        self.core = IncidentService(self.factory)
        self.pending = deque()
        self.lock = asyncio.Lock()
        self.task = None
        self.last_state = None
        self.last_signature = None
        self.last_sample = 0.0
        self.available = True
        self.error = ""
        self.dropped = 0

    @staticmethod
    def identity(state):
        if state.flood.scenario_id:
            return ("FLOOD", state.flood.scenario_id)
        if state.leak.scenario_id:
            return ("PIPELINE_LEAK", state.leak.event_id)
        return None

    @staticmethod
    def elapsed(state):
        return state.flood.elapsed_simulation_seconds if state.flood.scenario_id else state.leak.elapsed_simulation_seconds

    @staticmethod
    def signature(state):
        f, leak, execution = state.flood, state.leak, state.emergency
        return json.dumps({
            "identity": IncidentRuntimeService.identity(state),
            "running": state.running,
            "devices": [(d.id, d.status, d.fault) for d in state.devices],
            "valves": [(v.id, v.status) for v in state.valves],
            "flood": [f.stage, f.risk_level, f.entrance_closed],
            "leak": [leak.current_stage, leak.risk_level, leak.leak_status, leak.service_status,
                     leak.events[-1].get("sequence") if leak.events else 0],
            "execution": {"id":execution.id,"status":execution.status,"phase":execution.phase,"steps":[(step.index,step.status) for step in execution.steps],"last_event":execution.events[-1].get("sequence") if execution.events else 0} if execution else None,
        }, sort_keys=True)

    def enqueue(self, kind, state, reason=None):
        # Bounded queue: failure never grows RAM without limit or fabricates lost observations.
        if len(self.pending) >= 128:
            self.pending.popleft()
            self.dropped += 1
        self.pending.append((kind, state.model_copy(deep=True), reason))

    def observe(self, state):
        identity = self.identity(state)
        previous = self.identity(self.last_state) if self.last_state else None
        if previous and identity != previous:
            self.enqueue("abort", self.last_state, "场景重置或替换，未按正式流程关闭")
        if identity:
            signature = self.signature(state)
            now = monotonic()
            if signature != self.last_signature or now - self.last_sample >= 5:
                self.enqueue("capture", state)
                self.last_sample = now
                self.last_signature = signature
            self.last_state = state.model_copy(deep=True)
        else:
            self.last_state = None
            self.last_signature = None

    def _abort(self, state, reason):
        incident_id = self.core.capture(state)
        if incident_id:
            with self.factory() as db:
                self.core.abort_record(db, incident_id, reason,
                                       timestamp=datetime.now(UTC), simulation_time=self.elapsed(state))
                db.commit()

    async def flush(self, strict=False):
        async with self.lock:
            while self.pending:
                item = self.pending[0]
                try:
                    kind, state, reason = item
                    if kind == "capture":
                        await run_in_threadpool(self.core.capture, state)
                    else:
                        await run_in_threadpool(self._abort, state, reason)
                except Exception:
                    self.available = False
                    self.error = "事故档案写入失败，正在重试；缺失片段不会补造"
                    if strict:
                        raise HTTPException(503, self.error) from None
                    return
                if self.pending and self.pending[0] is item:
                    self.pending.popleft()
            self.available = True
            self.error = ""

    async def abort_current(self, reason):
        state = self.engine.snapshot()
        if self.identity(state):
            self.enqueue("abort", state, reason)
            await self.flush()
        self.last_state = None
        self.last_signature = None

    async def start(self):
        def initialize():
            with self.factory() as db:
                self.core.sync_sources(db)
                # An in-memory engine cannot resume old active records after process restart.
                for incident in db.scalars(select(Incident).where(Incident.status.not_in(["CLOSED", "ABORTED"]))):
                    self.core.abort_record(db, incident.id, "进程启动时没有对应活动场景，历史中断，未正常关闭")
                db.commit()
        try:
            await run_in_threadpool(initialize)
        except Exception:
            self.available = False
            self.error = "事故档案未就绪，请执行 M9 migration/backfill"
            logger.warning(self.error)
        self.task = asyncio.create_task(self._run(), name="incident-history-writer")

    async def _run(self):
        while True:
            await asyncio.sleep(1)
            await self.flush()

    async def shutdown(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        await self.abort_current("服务停止，事故中断，未正常关闭")
        await self.flush()

    async def close(self, incident_id, body):
        """Close the business incident, retaining device/valve/water outcomes unchanged."""
        rt = self.realtime
        async with rt.flood.lock:
            await self.flush(strict=True)
            with self.factory() as db:
                record = self.core.get_incident(db, incident_id)
                if record.status == "CLOSED":
                    return self.core.detail(db, incident_id)
                if not body.confirmed:
                    raise HTTPException(422, "请确认关闭该软件仿真事件")
                if record.status != "STABILIZING":
                    raise HTTPException(409, "仅 STABILIZING 事件可关闭；Reset/中断事件不能伪装正常关闭")
                active = self.identity(self.engine._state) == (record.incident_type, record.source_event_id)
                if active:
                    current = self.engine._state
                    stable = (current.leak.current_stage == "STABILIZING" and current.leak.leak_status == "CONTAINED") if record.incident_type == "PIPELINE_LEAK" else bool(current.emergency and current.emergency.phase == "STABILIZING" and current.flood.risk_score < 60)
                    if not stable:
                        raise HTTPException(409, "当前事故已不处于稳定状态，请重新观察")
            was_running = self.engine._state.running
            if active:
                self.engine.stop()
                terminal = self.engine.snapshot()
                try:
                    if terminal.flood.scenario_id:
                        await rt.flood_storage.sample(terminal)
                        await rt.emergency.flush()
                        await rt.risk.flush()
                    else:
                        await rt.leak.sample(terminal)
                    self.enqueue("capture", terminal)
                    await self.flush(strict=True)
                except Exception:
                    if was_running:
                        self.engine.start()
                    raise
            else:
                terminal = None
            try:
                # Short atomic business transaction; no await between commit and detach.
                with self.factory() as db:
                    self.core.close_record(db, incident_id, body,
                                           timestamp=datetime.now(UTC),
                                           simulation_time=self.elapsed(terminal) if terminal else None)
                    db.commit()
                    result = self.core.detail(db, incident_id)
            except Exception:
                if active and was_running:
                    self.engine.start()
                raise
            if active:
                # Deliberately do not call reset: closed valves, pumps and water remain as recorded.
                self.engine._state.flood = terminal.flood.model_copy(update={"scenario_id":None,"running":False,"status":"idle","started_at":None,"auto_fault":False,"requires_emergency":False,"alarm":None})
                self.engine._state.leak = terminal.leak.model_copy(update={"scenario_id":None,"event_id":None,"target_pipeline_id":None,"status":"idle","alarm":None,"execution":None,"events":[],"confirmed_at":None,"detected_at":None})
                self.engine._state.emergency = None
                self.engine.pipelines.configure_leak(None)
                self.engine.weather.rainfall_target = None
                self.last_state = None
                self.last_signature = None
                rt.publish(self.engine._touch())
                await rt.risk.flush()
            return result
