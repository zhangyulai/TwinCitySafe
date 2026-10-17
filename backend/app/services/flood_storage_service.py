import asyncio
import logging
from collections import OrderedDict
from contextlib import suppress
from datetime import datetime, UTC
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from app.models.flood import FloodScenarioRecord, FloodSnapshot
from simulator.flood_config import SNAPSHOT_INTERVAL_SECONDS

class FloodStorageService:
    def __init__(self, engine, session_factory):
        self.engine,self.session_factory=engine,session_factory
        self.interval=SNAPSHOT_INTERVAL_SECONDS
        self.task=None;self.available=False;self.last_sample_at=None;self.last_error="等待首次事故采样"
        self.lock=asyncio.Lock()
        self.pending=OrderedDict()
    async def start(self):
        def mark_interrupted():
            with self.session_factory() as session:
                session.execute(update(FloodScenarioRecord).where(FloodScenarioRecord.status=="running").values(status="stopped",updated_at=datetime.now(UTC)))
                session.commit()
        try:
            await run_in_threadpool(mark_interrupted)
            self.available=True;self.last_error=""
        except SQLAlchemyError:
            self.last_error="内涝存储未就绪，请执行 M5 migration"
        self.task=asyncio.create_task(self._run(),name="flood-snapshot-sampler")
    def persist(self, snapshot):
        f=snapshot.flood
        if not f.scenario_id:return
        with self.session_factory() as session:
            record=session.get(FloodScenarioRecord,f.scenario_id)
            values=dict(scenario=f.scenario,status=f.status,started_at=f.started_at,simulation_started_at=f.simulation_started_at,
                elapsed_simulation_seconds=f.elapsed_simulation_seconds,duration_minutes=f.duration_minutes,
                people_count=f.people_count,vehicle_count=f.vehicle_count,auto_fault=f.auto_fault,current_stage=f.stage,
                peak_water_level=f.peak_water_level,peak_risk=f.peak_risk,alarm=f.alarm.model_dump(mode="json",by_alias=True) if f.alarm else None,
                updated_at=snapshot.timestamp)
            if record is None:session.add(FloodScenarioRecord(id=f.scenario_id,**values))
            else:
                for key,value in values.items():setattr(record,key,value)
            session.flush()
            existing=session.scalar(select(FloodSnapshot.id).where(FloodSnapshot.scenario_id==f.scenario_id,FloodSnapshot.simulation_time==f.elapsed_simulation_seconds))
            if existing is None:
                session.add(FloodSnapshot(scenario_id=f.scenario_id,timestamp=snapshot.timestamp,simulation_time=f.elapsed_simulation_seconds,
                    rainfall=f.rainfall,water_level=f.water_level,water_area=f.water_area,inflow=f.surface_inflow,outflow=f.outflow,
                    pump_capacity=f.effective_pump_capacity,risk_score=f.risk_score,stage=f.stage))
            session.commit()
    async def sample(self, snapshot=None):
        snapshot=snapshot or self.engine.snapshot()
        if snapshot.flood.scenario_id:
            self.pending[snapshot.flood.scenario_id]=snapshot
        async with self.lock:
            for id,item in list(self.pending.items()):
                try:
                    await run_in_threadpool(self.persist,item)
                    if self.pending.get(id) is item:self.pending.pop(id,None)
                    self.available=True;self.last_error="";self.last_sample_at=item.timestamp
                except SQLAlchemyError:
                    if self.available or self.last_error!="内涝采样失败，将保留最新状态并重试":
                        logging.getLogger("uvicorn.error").warning("Flood snapshot storage unavailable; retrying at next interval")
                    self.available=False;self.last_error="内涝采样失败，将保留最新状态并重试"
                    break
    async def archive(self, reset=False):
        if reset and self.engine._state.flood.alarm:
            self.engine._state.flood.alarm.status="ended_by_reset"
        state=self.engine.snapshot()
        if state.flood.scenario_id:
            if state.flood.status=="running":state.flood.status="stopped"
            state.flood.running=False
            if reset and state.flood.alarm:state.flood.alarm.status="ended_by_reset"
            await self.sample(state)
    async def _run(self):
        while True:
            await asyncio.sleep(self.interval)
            await self.sample()
    async def shutdown(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):await self.task
            self.task=None
        await self.archive()
