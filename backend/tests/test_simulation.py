import math
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.realtime import ParkRealtimeState, SpeedRequest
from simulator.engine import SimulationEngine


def telemetry(state: ParkRealtimeState) -> dict:
    return state.model_dump(exclude={"timestamp", "session_id", "revision", "running", "speed"})


def test_shared_state_schema_defaults_and_snapshot_isolation():
    engine = SimulationEngine()
    state = engine.snapshot()
    wire = state.model_dump(mode="json", by_alias=True)
    assert ParkRealtimeState.model_validate(wire) == state
    assert wire["timestamp"].endswith("Z")
    assert UUID(wire["sessionId"])
    assert set(wire) == {"timestamp", "sessionId", "revision", "simulationTime", "running", "speed", "weather", "environment", "devices", "pipelines", "system", "valves", "flood", "emergency", "leak"}
    assert [device["id"] for device in wire["devices"]] == ["P01", "P02", "P03"]
    assert [pipeline["id"] for pipeline in wire["pipelines"]] == ["WS-001", "DS-001", "FS-001"]
    assert wire["devices"][2] == {"id": "P03", "name": "P03 主排水泵", "status": "running", "temperature": 42, "vibration": 1.8, "current": 18, "rpm": 1450, "efficiency": 96, "health": 94, "fault": "normal", "runtimeHours": 0, "analysis": None, "startupProgress": 1}
    state.devices[2].temperature = 55
    assert engine.snapshot().devices[2].temperature == 42
    wire["weather"]["condition"] = "storm"
    with pytest.raises(ValidationError):
        ParkRealtimeState.model_validate(wire)


def test_stop_freezes_telemetry_heartbeat_and_reset_preserves_running():
    engine = SimulationEngine()
    engine.set_weather("rain")
    engine.tick(1)
    stopped = engine.stop()
    assert engine.stop() == stopped  # Idempotent; no duplicate control mutation.
    paused = engine.tick(2)
    assert telemetry(paused) == telemetry(stopped)
    assert paused.revision > stopped.revision
    assert paused.timestamp >= stopped.timestamp
    engine.set_speed(3)
    engine.set_device_state("P03", "offline")
    reset = engine.reset()
    assert not reset.running and reset.simulation_time == 0 and reset.speed == 1
    assert reset.weather.condition == "clear" and reset.weather.rainfall == 0
    assert reset.environment.b2_water_level == 0.8
    assert reset.devices[2].status == "running"
    assert reset.session_id == stopped.session_id and reset.revision > paused.revision
    started = engine.start()
    assert engine.start() == started
    assert engine.reset().running
    assert engine.tick().simulation_time == 1


def test_weather_and_manual_device_change_are_smooth_and_link_system_counts():
    engine = SimulationEngine()
    initial = engine.snapshot()
    commanded = engine.set_weather("rain")
    assert commanded.weather.rainfall == initial.weather.rainfall  # Target changes, no jump.
    previous = commanded
    for _ in range(60):
        state = engine.tick()
        assert 0 < state.weather.rainfall - previous.weather.rainfall < 1.5
        assert abs(state.weather.temperature - previous.weather.temperature) < 0.2
        assert abs(state.weather.humidity - previous.weather.humidity) < 1.2
        assert abs(state.environment.b2_water_level - previous.environment.b2_water_level) < 0.02
        assert abs(state.devices[2].temperature - previous.devices[2].temperature) < 0.1
        previous = state
    assert 10 < state.weather.rainfall < 15
    assert 0.8 < state.environment.b2_water_level < 1.5
    warning = engine.set_device_state("P03", "warning")
    after = engine.tick()
    assert after.devices[2].temperature - warning.devices[2].temperature < 0.7
    assert after.devices[2].vibration - warning.devices[2].vibration < 0.2
    assert after.system.alerts == 1 and after.system.online_devices == 1268
    offline = engine.set_device_state("P01", "offline")
    assert offline.system.alerts == 2 and offline.system.online_devices == 1267
    engine.set_device_state("P03", "running")
    assert engine.snapshot().system.alerts == 1
    with pytest.raises(KeyError):
        engine.set_device_state("UNKNOWN", "running")


def test_speed_substeps_are_equivalent_and_large_dt_bounded():
    fast, regular = SimulationEngine(), SimulationEngine()
    fast.set_weather("rain")
    regular.set_weather("rain")
    fast.set_speed(10)
    accelerated = fast.tick(1)
    for _ in range(10):
        normal = regular.tick(1)
    assert telemetry(accelerated) == telemetry(normal)
    assert accelerated.simulation_time == 10
    assert fast.tick(100000).simulation_time == 60  # Catch-up capped at 5 wall seconds.
    for invalid in [float("nan"), float("inf"), -1]:
        with pytest.raises(ValueError):
            fast.tick(invalid)
    for invalid in [0, 11, float("nan"), float("inf"), "2"]:
        with pytest.raises(ValidationError):
            SpeedRequest(speed=invalid)


def test_pump_state_affects_drainage_and_water_stays_in_m2_range():
    inactive, active = SimulationEngine(), SimulationEngine()
    for engine in (inactive, active):
        engine.set_weather("rain")
        engine.set_speed(10)
    inactive.set_device_state("P03", "offline")
    active.set_device_state("P01", "running")
    active.set_device_state("P02", "running")
    for _ in range(120):
        first, second = inactive.tick(), active.tick()
        assert 0.45 <= first.environment.b2_water_level <= 2.5
        assert 0.45 <= second.environment.b2_water_level <= 2.5
        assert all(math.isfinite(value) for device in first.devices for value in [device.temperature, device.rpm, device.efficiency])
    assert first.environment.b2_water_level > second.environment.b2_water_level + 0.6
    assert first.pipelines[1].flow < second.pipelines[1].flow
    assert all(pipeline.status == "normal" for pipeline in first.pipelines)
    assert first.system.event_count == 0
