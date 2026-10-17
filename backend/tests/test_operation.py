import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
import numpy as np
import pytest
import httpx
from sqlalchemy import select, func
from app.main import app
from app.models import Device, DeviceTelemetry, DeviceAlarm
from app.schemas.operation import FaultRequest
from app.services.seed_service import seed_devices
from app.services.operation_service import OperationService
from app.services.anomaly_service import AnomalyDetectionService
from app.services.health_service import HealthService
from app.services.maintenance_service import MaintenanceAdviceService
from app.services.telemetry_service import TelemetrySamplingService
from app.services.device_service import DeviceService
from simulator.engine import SimulationEngine
from algorithm.anomaly_detection.features import normalize_scores


def operational_engine():
    engine = SimulationEngine()
    operation = OperationService(engine.devices)
    engine.processor = operation.process
    operation.process(engine._state, 0)
    return engine, operation


def test_seed_is_idempotent_and_assets_have_positions(isolated_storage):
    with isolated_storage() as db:
        db.get(Device, "P03").runtime_hours = 4200
        db.commit()
        assert seed_devices(db) == 0
        assert db.scalar(select(func.count()).select_from(Device)) == 3
        assert db.get(Device, "P03").runtime_hours == 4200
        assert db.get(Device, "P03").position_x == 10


def test_health_formula_grade_bounds_and_smoothing():
    engine = SimulationEngine()
    device = engine.snapshot().devices[2]
    service = HealthService()
    device.runtime_hours = 4000
    normal, target, grade = service.calculate(device, 1, True)
    assert normal > 94 and target == 96 and grade == "优秀"
    device.temperature, device.vibration, device.efficiency = 80, 6.5, 60
    first, target, _ = service.calculate(device, 1, True)
    assert 0 < normal-first < 4 and target < 40
    for _ in range(180):
        score, _, _ = service.calculate(device, 1, True)
    assert 0 <= score < 40
    assert service.calculate(device, 1, False)[0] == score
    assert [service.grade(x) for x in (90,80,60,30,0)] == ["优秀","良好","一般","较差","严重"]


def test_real_model_normalization_and_missing_model(tmp_path):
    service = AnomalyDetectionService()
    assert service.available
    assert service.artifact["samples"] == 10000
    calibration = service.artifact["calibration"]
    normalized = normalize_scores([calibration["median"],calibration["cutoff"],calibration["cutoff"]+.2],calibration)
    assert np.allclose(normalized, [.12,.6,.92])
    missing = AnomalyDetectionService(tmp_path / "missing.joblib")
    engine = SimulationEngine(); operation = OperationService(engine.devices, anomaly=missing)
    engine.processor = operation.process
    snapshot = engine.tick()
    assert snapshot.devices[2].analysis.model_available is False
    assert snapshot.devices[2].analysis.anomaly_score is None
    assert snapshot.devices[2].analysis.level == "unavailable"
    assert "未加载" in snapshot.devices[2].analysis.explanation
    assert snapshot.devices[2].health > 0


def test_fault_deterioration_dedup_and_recovery():
    engine, op = operational_engine()
    initial = engine.snapshot().devices[2]
    assert initial.analysis.anomaly_score < .35
    for d in engine.snapshot().devices[:2]:
        assert d.analysis.level == "not_applicable" and d.analysis.anomaly_score is None
    engine.set_fault("P03", "bearing_degradation")
    assert engine.snapshot().devices[2].temperature == initial.temperature
    scores, identities = [], set()
    previous = initial
    for _ in range(180):
        current = engine.tick().devices[2]
        assert abs(current.temperature-previous.temperature) < 1
        assert abs(current.vibration-previous.vibration) < .15
        assert abs(current.health-previous.health) < 2
        scores.append(current.analysis.anomaly_score)
        if current.analysis.active_alarm_id: identities.add(current.analysis.active_alarm_id)
        previous = current
    assert current.temperature > 65 and current.vibration > 5
    assert current.health < 60 and scores[-1] > .8 and scores[-1] > scores[10] > scores[0]
    assert current.status == "warning" and len(identities) == 1 and len(op.alarms.active) == 1
    assert sum(c.contribution for c in current.analysis.contributions) == pytest.approx(1)
    assert "非" in current.analysis.explanation or "不代表" in current.analysis.explanation
    assert current.analysis.advice.priority == "P0"
    engine.set_fault("P03", "normal")
    for _ in range(240): current = engine.tick().devices[2]
    assert current.status == "running" and current.analysis.anomaly_score < .35
    assert current.health > 90 and not op.alarms.active
    assert len(op.alarms.pending) == 1
    assert list(op.alarms.pending.values())[0]["status"] == "resolved"


@pytest.mark.parametrize("fault,field,threshold",[("overheat","temperature",70),("low_efficiency","current",23)])
def test_other_fault_profiles_remain_continuous(fault,field,threshold):
    engine = SimulationEngine();engine.set_fault("P03", fault)
    engine.set_speed(10)
    for _ in range(18): snapshot = engine.tick()
    assert getattr(snapshot.devices[2],field) > threshold
    reset = engine.reset()
    assert reset.devices[2].fault == "normal" and reset.speed == 1


def test_maintenance_priorities_and_no_certain_damage_claim():
    for level,health,expected in [("normal",95,"P3"),("attention",90,"P3"),("warning",80,"P2"),("warning",50,"P1"),("critical",20,"P0")]:
        explanation, advice = MaintenanceAdviceService.build(health,level,[],"normal")
        assert advice.priority == expected
        assert "一定损坏" not in explanation+advice.message


def test_sampling_alarm_storage_history_and_cancellation(isolated_storage):
    async def exercise():
        engine, op = operational_engine()
        sampler = TelemetrySamplingService(engine,op,interval=.03)
        await sampler.start()
        engine.set_fault("P03","bearing_degradation");engine.set_speed(10)
        for _ in range(18): engine.tick()
        await asyncio.sleep(.08)
        assert sampler.available
        with isolated_storage() as db:
            assert db.scalar(select(func.count()).select_from(DeviceTelemetry)) == 3
            assert db.scalar(select(func.count()).select_from(DeviceAlarm)) == 1
            assert db.scalar(select(DeviceAlarm.status)) == "active"
        for _ in range(3):engine.tick()
        await sampler.sample()
        with isolated_storage() as db:
            assert db.scalar(select(func.count()).select_from(DeviceAlarm)) == 1
            history = DeviceService.telemetry(db,"P03","24h",None,None,5)
            assert history.total == 2 and history.points[0].timestamp <= history.points[-1].timestamp
        engine.set_fault("P03","normal")
        for _ in range(24):engine.tick()
        await sampler.sample()
        with isolated_storage() as db:
            alarm = db.scalar(select(DeviceAlarm))
            assert alarm.status == "resolved" and alarm.resolved_at is not None
            assert alarm.max_score > .8
        await sampler.shutdown()
        assert sampler.task is None
        assert not [t for t in asyncio.all_tasks() if t.get_name() == "park-telemetry-sampler"]
    asyncio.run(exercise())


def test_device_api_filters_queries_and_controls():
    async def exercise():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
                assert len((await client.get('/api/v1/devices')).json()) == 3
                assert (await client.get('/api/v1/devices?device_type=fan')).json() == []
                assert len((await client.get('/api/v1/devices?status=running&keyword=P03')).json()) == 1
                assert len((await client.get('/api/v1/devices?status=standby')).json()) == 2
                for suffix in ('','/realtime','/health','/anomaly','/maintenance-advice','/alarms'):
                    assert (await client.get('/api/v1/devices/P03'+suffix)).status_code == 200
                for range_ in ('1h','6h','24h'):
                    response = await client.get('/api/v1/devices/P03/telemetry',params={'range':range_})
                    assert response.status_code == 200 and response.json()['points'] == []
                for path in ('/devices/unknown','/devices/unknown/telemetry','/devices/unknown/realtime'):
                    assert (await client.get('/api/v1'+path)).status_code == 404
                assert (await client.get('/api/v1/devices/P03/telemetry?range=7d')).status_code == 422
                assert (await client.get('/api/v1/devices/P03/telemetry?start_time=2026-10-01T00:00:00')).status_code == 422
                body=(await client.post('/api/v1/simulation/device/P03/fault',json={'fault':'bearing_degradation'})).json()
                assert body['devices'][2]['fault'] == 'bearing_degradation'
                assert (await client.post('/api/v1/simulation/device/P03/fault',json={'fault':'unknown'})).status_code == 422
                assert (await client.post('/api/v1/simulation/device/unknown/fault',json={'fault':'normal'})).status_code == 404
                assert (await client.get('/api/v1/health')).json()['status'] == 'ok'
    asyncio.run(exercise())

def test_history_downsample_and_time_window_validation(isolated_storage):
    from fastapi import HTTPException
    with isolated_storage() as db:
        end=datetime.now(UTC)
        for i in range(605):
            db.add(DeviceTelemetry(device_id='P03',timestamp=end-timedelta(seconds=(605-i)*5),session_id='history-test',revision=i,
                temperature=42,vibration=1.8,current=18,rpm=1450,efficiency=96,health_score=94,anomaly_score=.12,status='running'))
        db.commit()
        result=DeviceService.telemetry(db,'P03','1h',None,None,5)
        assert result.total==605 and len(result.points)==600 and result.downsampled
        assert result.points[0].timestamp==end-timedelta(seconds=605*5)
        assert result.points[-1].timestamp==end-timedelta(seconds=5)
        with pytest.raises(HTTPException): DeviceService.telemetry(db,'P03','1h',end,end-timedelta(hours=1),5)
        with pytest.raises(HTTPException): DeviceService.telemetry(db,'P03','1h',end-timedelta(days=2),end,5)


def test_database_sampling_failure_does_not_stop_engine(isolated_storage):
    async def exercise():
        engine,operation=operational_engine()
        sampler=TelemetrySamplingService(engine,operation)
        def fail(*args): raise RuntimeError('offline')
        sampler.persist=fail
        await sampler.sample()
        assert not sampler.available and sampler.last_error
        before=engine.snapshot().simulation_time
        assert engine.tick().simulation_time>before
    asyncio.run(exercise())


def test_fault_controls_disabled_in_production(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(),'app_env','production')
    async def exercise():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                assert (await client.post('/api/v1/simulation/device/P03/fault',json={'fault':'overheat'})).status_code==404
                assert (await client.get('/api/v1/devices/P03/realtime')).status_code==200
    asyncio.run(exercise())


def test_normal_startup_is_not_reported_as_a_fault():
    engine, op = operational_engine()
    engine.set_device_state("P01", "running")
    for i in range(150):
        d = engine.tick().devices[0]
        assert d.status == "running" and d.analysis.active_alarm_id is None
        if i < 59:
            assert d.analysis.level == "warming_up" and d.analysis.anomaly_score is None
    assert d.analysis.level == "normal" and d.health > 90
    assert not op.alarms.active
    engine.set_device_state("P02", "running")
    engine.set_fault("P02", "bearing_degradation")
    for _ in range(160): d = engine.tick().devices[1]
    assert d.analysis.is_anomaly and d.status == "warning"


def test_concurrent_samples_are_serialized(isolated_storage):
    async def exercise():
        engine, operation = operational_engine()
        sampler = TelemetrySamplingService(engine, operation, session_factory=isolated_storage)
        await asyncio.gather(*(sampler.sample() for _ in range(8)))
        assert sampler.available
        with isolated_storage() as db:
            assert db.scalar(select(func.count()).select_from(DeviceTelemetry)) == 3
    asyncio.run(exercise())
