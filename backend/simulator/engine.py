"""One in-memory engine per ASGI app lifespan, with one independent 1 Hz publisher."""
import asyncio
import math
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from uuid import uuid4
from time import monotonic

from app.schemas.operation import FaultProfile
from app.schemas.realtime import PipelineState, ValveRealtimeState, DeviceStatus, ParkRealtimeState, SimulationStatus, WeatherCondition
from simulator.config import BACKGROUND_ONLINE_DEVICES, MAX_SUBSTEP, MAX_WALL_DELTA, TICK_INTERVAL
from simulator.device_simulator import DeviceSimulator
from simulator.flood_simulator import FloodSimulator
from simulator.pipeline_simulator import PipelineSimulator
from simulator.state import initial_state
from simulator.weather_simulator import WeatherSimulator
from simulator import flood_config as flood_cfg
from app.services.flood_risk_service import FloodRiskService


class SimulationEngine:
    def __init__(self) -> None:
        self._state = initial_state(str(uuid4()))
        self.leak_processor = None
        self.processor: Callable[[ParkRealtimeState, float], None] | None = None
        self.weather = WeatherSimulator()
        self.devices = DeviceSimulator()
        self.flood = FloodSimulator()
        self.flood_risk = FloodRiskService()
        self.pipelines = PipelineSimulator()
        self._task: asyncio.Task[None] | None = None
        self._wall_mark = monotonic()

    def configure_pipelines(self, graph):
        self.pipelines.configure(graph)
        old={p.id:p for p in self._state.pipelines}
        self._state.pipelines=[old[e.id] if e.id in old else PipelineState(id=e.id,type="drain" if e.kind=="drainage" else e.kind,
            pressure=.08 if e.kind=="drainage" else .42 if e.kind=="water" else .48,
            flow=20 if e.kind=="drainage" else 28 if e.kind=="water" else 2) for e in graph.edges.values()]
        self._state.valves=[ValveRealtimeState(id=v.id,status=v.status,open_percentage=0 if v.status=="closed" else 100) for v in graph.valves.values()]
        for p in self._state.pipelines:
            p.status=self.pipelines.asset_status.get(p.id,"normal")
            if p.status=="normal" and p.id in self.pipelines.isolated:p.status="isolated"
        return self._touch()

    def snapshot(self) -> ParkRealtimeState:
        # Consumers never obtain the mutable state used by the simulators.
        return self._state.model_copy(deep=True)

    def status(self) -> SimulationStatus:
        return SimulationStatus(running=self._state.running, speed=self._state.speed,
                                simulation_time=self._state.simulation_time)

    def _touch(self) -> ParkRealtimeState:
        self._state.revision += 1
        self._state.timestamp = datetime.now(UTC)
        self._state.system.online_devices = BACKGROUND_ONLINE_DEVICES + sum(device.status != "offline" for device in self._state.devices)
        self._state.system.alerts = sum(device.status in ("warning", "offline") for device in self._state.devices)
        self._state.system.alerts += int(self._state.flood.alarm is not None or self._state.leak.alarm is not None)
        self._state.system.event_count = int(self._state.flood.scenario_id is not None or self._state.leak.scenario_id is not None)
        return self.snapshot()

    def start(self) -> ParkRealtimeState:
        if self._state.running:
            return self.snapshot()
        self._state.running = True
        if self._state.flood.scenario_id and self._state.flood.status != "completed":
            self._state.flood.running = True
            self._state.flood.status = "running"
        if self._state.leak.scenario_id:self._state.leak.status="running"
        self._wall_mark = monotonic()
        return self._touch()

    def stop(self) -> ParkRealtimeState:
        if not self._state.running:
            return self.snapshot()
        self._state.running = False
        if self._state.leak.scenario_id:self._state.leak.status="stopped"
        if self._state.flood.scenario_id and self._state.flood.status != "completed":
            self._state.flood.running = False
            self._state.flood.status = "stopped"
        return self._touch()

    def reset(self) -> ParkRealtimeState:
        # Preserve pause/run choice and engine identity. Revision never rewinds.
        self.devices.reset()
        self.pipelines.configure_leak(None)
        self.weather.rainfall_target = None
        self.flood.reset_history()
        self._state = initial_state(self._state.session_id, revision=self._state.revision + 1,
                                    running=self._state.running)
        self._wall_mark = monotonic()
        if self.pipelines.graph: self.configure_pipelines(self.pipelines.graph)
        if self.processor:
            self.processor(self._state, 0)
        return self.snapshot()

    def set_weather(self, condition: WeatherCondition) -> ParkRealtimeState:
        self.weather.set_weather(self._state.weather, condition)
        return self._touch()

    def set_device_state(self, device_id: str, status: DeviceStatus) -> ParkRealtimeState:
        self.devices.set_state(self._state.devices, device_id, status)
        return self._touch()

    def set_fault(self, device_id: str, fault: FaultProfile) -> ParkRealtimeState:
        self.devices.set_fault(self._state.devices, device_id, fault)
        return self._touch()

    def set_speed(self, speed: float) -> ParkRealtimeState:
        self._state.speed = speed  # Pydantic also guards programmatic callers.
        self._wall_mark = monotonic()
        return self._touch()

    def tick(self, wall_delta: float = TICK_INTERVAL) -> ParkRealtimeState:
        if not math.isfinite(wall_delta) or wall_delta < 0:
            raise ValueError("wall_delta must be a finite non-negative number")
        if self._state.running:
            elapsed = min(wall_delta, MAX_WALL_DELTA) * self._state.speed
            scenario=self._state.flood
            if scenario.scenario_id:
                if scenario.status == "completed": elapsed=0
                else: elapsed=min(elapsed,max(0,scenario.duration_minutes*60-scenario.elapsed_simulation_seconds))
            steps = max(1, math.ceil(elapsed / MAX_SUBSTEP))
            dt = elapsed / steps
            for _ in range(steps):
                from app.services.emergency_execution_service import EmergencyExecutionEngine
                EmergencyExecutionEngine.advance(self)
                self._state.simulation_time += dt
                time = self._state.simulation_time
                if scenario.scenario_id and scenario.status != "completed":
                    self.weather.rainfall_target=flood_cfg.scenario_rainfall(scenario)
                    scenario.rainfall_target=self.weather.rainfall_target
                    if scenario.auto_fault and not scenario.fault_triggered and scenario.elapsed_simulation_seconds>=flood_cfg.AUTO_FAULT_SECONDS:
                        self.devices.set_fault(self._state.devices,"P03","bearing_degradation")
                        scenario.fault_triggered=True
                self.weather.tick(self._state.weather, time, dt)
                self.devices.tick(self._state.devices, self._state.weather.temperature, time, dt)
                capacity = self.devices.drainage_capacity(self._state.devices)
                if scenario.scenario_id:
                    self.flood.tick_scenario(scenario,self._state.environment,self._state.weather.rainfall,self._state.devices,dt)
                else:
                    self.flood.tick(self._state.environment, self._state.weather.rainfall, capacity, time, dt)
                self.pipelines.tick(self._state.pipelines, self._state.weather.rainfall, capacity, time, dt,self._state.leak)
        if self.processor and self._state.running:
            self._state.timestamp = datetime.now(UTC)
            self.processor(self._state, elapsed)
        scenario=self._state.flood
        if self._state.running:
            if scenario.scenario_id:
                self.flood_risk.update(scenario)
                if scenario.elapsed_simulation_seconds>=scenario.duration_minutes*60-1e-6:
                    scenario.elapsed_simulation_seconds=scenario.duration_minutes*60
                    scenario.status="completed"
                    scenario.running=False
                    self._state.running=False
            else:
                scenario.water_level=self._state.environment.b2_water_level
                scenario.water_area=self._state.environment.b2_water_area
                scenario.rainfall=self._state.weather.rainfall
                scenario.flood_volume=scenario.water_level/100*flood_cfg.PARKING_EFFECTIVE_AREA_M2
                rated,effective=self.flood.capacities(self._state.devices)
                scenario.pump_capacity=rated
                scenario.effective_pump_capacity=effective
                scenario.pump_efficiency=effective/rated*100 if rated else 0
                self.flood_risk.update(scenario)
        if self.leak_processor and self._state.running:self.leak_processor(self._state)
        # Paused clients still receive live heartbeats, with all telemetry/time frozen.
        return self._touch()

    def launch(self, publish: Callable[[ParkRealtimeState], None]) -> None:
        if self._task is None or self._task.done():
            self._wall_mark = monotonic()
            self._task = asyncio.create_task(self._run(publish), name="park-simulation-engine")

    async def _run(self, publish: Callable[[ParkRealtimeState], None]) -> None:
        while True:
            await asyncio.sleep(TICK_INTERVAL)
            now = monotonic()
            publish(self.tick(now - self._wall_mark))
            self._wall_mark = now

    async def shutdown(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
