from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

FloodScenario = Literal["normal","heavy_rain","extreme_rain"]
FloodStage = Literal["normal","watch","warning","high","extreme"]
FloodRiskLevel = Literal["low","general","elevated","high","extreme"]
class FloodWire(BaseModel):
    model_config=ConfigDict(alias_generator=to_camel,populate_by_name=True,extra="forbid",validate_assignment=True,allow_inf_nan=False)
class FloodScenarioRequest(FloodWire):
    rainfall_recession: bool = False
    scenario: FloodScenario="extreme_rain"
    duration_minutes: int=Field(default=30,ge=1,le=120,strict=True)
    people_count: int=Field(default=32,ge=0,le=500,strict=True)
    vehicle_count: int=Field(default=48,ge=0,le=300,strict=True)
class FloodExposureRequest(FloodWire):
    people_count: int=Field(ge=0,le=500,strict=True)
    vehicle_count: int=Field(ge=0,le=300,strict=True)
class FloodRiskFactor(FloodWire):
    key: str
    label: str
    weight: float
    normalized_value: float=Field(ge=0,le=1)
    points: float=Field(ge=0,le=100)
    contribution: float=Field(ge=0,le=100)
class FloodRiskBreakdown(FloodWire):
    factors: list[FloodRiskFactor]=Field(default_factory=list)
    method: str="Flood scenario risk score · 场景规则模型"
class FloodAlarm(FloodWire):
    id: str
    alarm_type: str="FLOOD_SCENARIO"
    level: Literal["info","warning","major","critical"]
    stage: FloodStage
    peak_risk: float
    status: Literal["active","ended_by_reset"]="active"
    message: str
class FloodSimulationState(FloodWire):
    rainfall_recession: bool = False
    entrance_closed: bool = False
    vehicle_entry_rate: float = Field(default=0, ge=0)
    exposure_remaining: float | None = None
    exposure_target: int = Field(default=0, ge=0, le=500)
    scenario_id: str|None=None
    running: bool=False
    scenario: FloodScenario="normal"
    status: Literal["idle","running","stopped","completed"]="idle"
    started_at: datetime|None=None
    simulation_started_at: float=0
    elapsed_simulation_seconds: float=Field(default=0,ge=0)
    duration_minutes: int=30
    auto_fault: bool=False
    fault_triggered: bool=False
    rainfall: float=Field(default=0,ge=0)
    rainfall_target: float=Field(default=8,ge=0)
    surface_inflow: float=Field(default=0,ge=0)
    natural_drainage: float=Field(default=0,ge=0)
    pump_capacity: float=Field(default=0,ge=0)
    pump_efficiency: float=Field(default=0,ge=0,le=100)
    effective_pump_capacity: float=Field(default=0,ge=0)
    outflow: float=Field(default=0,ge=0)
    water_level: float=Field(default=.8,ge=0)
    water_area: float=Field(default=0,ge=0)
    flood_volume: float=Field(default=12,ge=0)
    effective_area: float=1500
    growth_rate: float=0
    risk_score: float=Field(default=0,ge=0,le=100)
    risk_level: FloodRiskLevel="low"
    stage: FloodStage="normal"
    risk_breakdown: FloodRiskBreakdown=Field(default_factory=FloodRiskBreakdown)
    people_count: int=32
    vehicle_count: int=48
    peak_water_level: float=0
    peak_risk: float=0
    alarm: FloodAlarm|None=None
    requires_emergency: bool=False
class FloodForecastPoint(FloodWire):
    minute: int
    water_level: float
    water_area: float
    risk_score: float
    risk_level: FloodRiskLevel
class FloodForecast(FloodWire):
    scenario_id: str|None
    based_on_revision: int
    simulation_time: float
    current: FloodForecastPoint
    points: list[FloodForecastPoint]
    assumption: str="假设所选降雨计划继续（含已选择的雨势回落工况）、泵指令/启动过渡、待执行应急动作与故障演化持续；外推不受演示时长截断，非实际防洪预测。"
class FloodScenarioStatus(FloodWire):
    available: bool
    interval_seconds: float
    last_sample_at: datetime|None=None
    message: str=""
