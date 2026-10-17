import asyncio
import logging
from copy import deepcopy
from contextlib import suppress
from datetime import UTC, datetime
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from app.core.database import SessionLocal
from app.models import Device, DeviceTelemetry, DeviceAlarm

logger = logging.getLogger("uvicorn.error")

class TelemetrySamplingService:
    def __init__(self, engine, operation, interval=5, session_factory=SessionLocal):
        self.engine = engine
        self.operation = operation
        self.interval = interval
        self.session_factory = session_factory
        self.task = None
        self.available = False
        self.last_sample_at = None
        self.last_error = "等待首次采样"
        self.last_key = None
        self.sample_lock = asyncio.Lock()

    def restore(self):
        with self.session_factory() as session:
            devices = session.scalars(select(Device)).all()
            if len(devices) < 3:
                raise RuntimeError("Device seed not installed")
            runtime = {d.id: d.runtime_hours for d in devices}
            # A process restart creates a new simulation session; do not carry an old active simulation alarm into it.
            now = datetime.now(UTC)
            session.execute(update(DeviceAlarm).where(DeviceAlarm.status == "active").values(status="resolved", resolved_at=now, updated_at=now,
                message="仿真会话已重启，旧告警结束；新工况重新评估"))
            session.commit()
            return runtime

    async def start(self):
        try:
            self.operation.runtime.update(await run_in_threadpool(self.restore))
        except (SQLAlchemyError, RuntimeError):
            logger.warning("Device storage unavailable: run Alembic upgrade and seed-devices.py; realtime simulation remains available.")
        self.task = asyncio.create_task(self._run(), name="park-telemetry-sampler")

    def persist(self, snapshot, alarms):
        with self.session_factory() as session:
            for live in snapshot.devices:
                asset = session.get(Device, live.id)
                if asset is None:
                    raise RuntimeError("Missing device seed")
                asset.status, asset.health_score, asset.runtime_hours = live.status, live.health, live.runtime_hours
                asset.updated_at = snapshot.timestamp
                existing = session.scalar(select(DeviceTelemetry.id).where(DeviceTelemetry.session_id == snapshot.session_id,
                    DeviceTelemetry.revision == snapshot.revision, DeviceTelemetry.device_id == live.id))
                if existing is None:
                    session.add(DeviceTelemetry(device_id=live.id, timestamp=snapshot.timestamp, session_id=snapshot.session_id,
                        revision=snapshot.revision, temperature=live.temperature, vibration=live.vibration, current=live.current,
                        rpm=live.rpm, efficiency=live.efficiency, health_score=live.health,
                        anomaly_score=live.analysis.anomaly_score if live.analysis else None, status=live.status))
            # Resolve older alarms first before inserting a new active one for the same device.
            for item in sorted(alarms, key=lambda a: a["status"] == "active"):
                record = session.get(DeviceAlarm, item["id"])
                if record:
                    for key, value in item.items():
                        setattr(record, key, value)
                else:
                    session.add(DeviceAlarm(**item))
                session.flush()
            session.commit()

    async def sample(self):
        async with self.sample_lock:
            await self._sample_locked()

    async def _sample_locked(self):
        snapshot = self.engine.snapshot()
        alarms = deepcopy(list(self.operation.alarms.pending.values()))
        key = (snapshot.session_id, snapshot.revision)
        if key == self.last_key:
            return
        try:
            await run_in_threadpool(self.persist, snapshot, alarms)
            self.operation.alarms.acknowledge(alarms)
            self.available = True
            self.last_error = ""
            self.last_sample_at = snapshot.timestamp
            self.last_key = key
        except (SQLAlchemyError, RuntimeError):
            if self.available or self.last_error != "历史采样暂不可用，请检查数据库及 migration":
                logger.warning("Telemetry sample not stored; checking database again at the next sampling interval.")
            self.available = False
            self.last_error = "历史采样暂不可用，请检查数据库及 migration"

    async def _run(self):
        while True:
            await asyncio.sleep(self.interval)
            await self.sample()

    async def shutdown(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
