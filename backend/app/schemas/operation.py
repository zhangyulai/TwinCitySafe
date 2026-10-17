from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

FaultProfile = Literal["normal", "bearing_degradation", "overheat", "low_efficiency"]
AnomalyLevel = Literal["normal", "attention", "warning", "critical", "unavailable", "not_applicable", "warming_up"]

class OperationModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid", allow_inf_nan=False)

class Contribution(OperationModel):
    feature: str
    label: str
    deviation: float = Field(ge=0)
    contribution: float = Field(ge=0, le=1)

class Advice(OperationModel):
    priority: Literal["P0", "P1", "P2", "P3"]
    title: str
    message: str

class DeviceAnalysis(OperationModel):
    health_score: float = Field(ge=0, le=100)
    health_grade: str
    health_target: float = Field(ge=0, le=100)
    model_available: bool
    model_version: str | None = None
    evaluated: bool
    anomaly_score: float | None = Field(default=None, ge=0, le=1)
    raw_score: float | None = None
    is_anomaly: bool = False
    level: AnomalyLevel
    contributions: list[Contribution] = []
    explanation: str
    advice: Advice
    active_alarm_id: str | None = None

class FaultRequest(OperationModel):
    fault: FaultProfile

class TelemetryPoint(OperationModel):
    timestamp: datetime
    temperature: float
    vibration: float
    current: float
    rpm: float
    efficiency: float
    health_score: float
    anomaly_score: float | None
    status: str

class TelemetryHistory(OperationModel):
    device_id: str
    source: str = "database_samples"
    start_time: datetime
    end_time: datetime
    sample_interval_seconds: float
    points: list[TelemetryPoint]
    total: int
    downsampled: bool

class DeviceAsset(OperationModel):
    id: str
    device_code: str
    device_name: str
    device_type: str
    building_id: str
    area_id: str
    position_x: float
    position_y: float
    position_z: float
    status: str
    health_score: float
    install_date: str
    runtime_hours: float
    last_maintenance: str
    rated_power: float
    rated_rpm: float
    rated_current: float
    rated_capacity: float
    created_at: datetime
    updated_at: datetime
