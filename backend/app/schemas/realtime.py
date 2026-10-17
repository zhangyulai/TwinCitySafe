"""M2's shared REST/WebSocket contract. Values are simulated, never sensor readings."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from app.schemas.operation import DeviceAnalysis, FaultProfile
from app.schemas.flood import FloodSimulationState
from app.schemas.emergency import EmergencyExecutionState
from app.schemas.leak import LeakState

WeatherCondition = Literal["clear", "cloudy", "rain"]
DeviceStatus = Literal["offline", "standby", "running", "warning"]
PipelineKind = Literal["water", "drain", "fire"]


class WireModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True,
                              extra="forbid", validate_assignment=True, allow_inf_nan=False)


class WeatherState(WireModel):
    condition: WeatherCondition = "clear"
    rainfall: float = Field(default=0, ge=0, le=120, description="mm/h")
    temperature: float = Field(default=26, ge=-30, le=60, description="degrees Celsius")
    humidity: float = Field(default=58, ge=0, le=100)
    wind_speed: float = Field(default=2.4, ge=0, le=30, description="m/s")


class EnvironmentState(WireModel):
    b2_water_level: float = Field(default=0.8, ge=0, description="cm; software simulation water depth")
    b2_water_area: float = Field(default=0, ge=0, description="square metres")
    smoke: float = Field(default=0, ge=0)
    air_quality: float = Field(default=92, ge=0, le=100, description="simulated indicator, not a formal risk score")


class DeviceState(WireModel):
    startup_progress: float = Field(default=1, ge=0, le=1)
    id: str
    name: str
    fault: FaultProfile = "normal"
    runtime_hours: float = Field(default=0, ge=0)
    analysis: DeviceAnalysis | None = None
    status: DeviceStatus
    temperature: float = Field(ge=-30, le=100)
    vibration: float = Field(ge=0, le=10, description="mm/s")
    current: float = Field(ge=0, le=50, description="A")
    rpm: float = Field(ge=0, le=2000)
    efficiency: float = Field(ge=0, le=100)
    health: float = Field(ge=0, le=100, description="preset simulated device indicator")


class PipelineState(WireModel):
    inlet_pressure: float = Field(default=.42,ge=0)
    outlet_pressure: float = Field(default=.42,ge=0)
    inlet_flow: float = Field(default=28,ge=0)
    outlet_flow: float = Field(default=28,ge=0)
    id: str
    type: PipelineKind
    pressure: float = Field(ge=0, le=2, description="MPa")
    flow: float = Field(ge=0, le=200, description="cubic metres/hour")
    status: Literal["normal", "warning", "offline", "isolated"] = "normal"


class ValveRealtimeState(WireModel):
    id: str
    status: Literal["open", "closed", "fault"]
    open_percentage: float = Field(ge=0, le=100)


class SystemState(WireModel):
    online_devices: int = Field(default=1268, ge=0, le=1268)
    alerts: int = Field(default=0, ge=0, le=4)
    event_count: int = Field(default=0, ge=0)


class SimulationStatus(WireModel):
    running: bool = True
    speed: float = Field(default=1, ge=0.25, le=10)
    simulation_time: float = Field(default=0, ge=0, description="simulated seconds since reset")


class ParkRealtimeState(SimulationStatus):
    timestamp: datetime
    session_id: str
    revision: int = Field(ge=0)
    weather: WeatherState
    environment: EnvironmentState
    devices: list[DeviceState]
    pipelines: list[PipelineState]
    valves: list[ValveRealtimeState] = Field(default_factory=list)
    system: SystemState
    flood: FloodSimulationState = Field(default_factory=FloodSimulationState)
    emergency: EmergencyExecutionState | None = None
    leak: LeakState = Field(default_factory=LeakState)


class WeatherRequest(WireModel):
    condition: WeatherCondition


class DeviceStateRequest(WireModel):
    status: DeviceStatus


class SpeedRequest(WireModel):
    speed: float = Field(ge=0.25, le=10, strict=True)
