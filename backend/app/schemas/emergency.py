"""Software-only emergency actions and auditable execution state."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ActionType = Literal["START_PUMP", "STOP_PUMP", "SET_PUMP_STATE", "CLOSE_ENTRANCE", "OPEN_ENTRANCE", "CLOSE_VALVE", "OPEN_VALVE", "REDUCE_OCCUPANCY"]
class EmergencyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)
class EmergencyAction(EmergencyModel):
    action_type: ActionType
    target_id: str = Field(min_length=1, max_length=40)
    parameters: dict = Field(default_factory=dict)
    delay_seconds: float = Field(default=0, ge=0, le=600)
    duration_seconds: float = Field(default=0, ge=0, le=600)
    priority: int = Field(default=0, ge=0, le=100)
class EmergencyStep(EmergencyModel):
    index: int
    action: EmergencyAction
    status: Literal["pending", "executing", "completed", "cancelled", "failed"] = "pending"
    started_simulation_time: float | None = None
    timestamp: datetime | None = None
    message: str = "等待执行"
class EmergencyExecutionState(EmergencyModel):
    id: str
    scenario_id: str
    plan_code: str
    plan_name: str
    comparison_id: str
    operator: str = "demo-user"
    status: Literal["pending", "executing", "completed", "cancelled", "failed"] = "pending"
    phase: Literal["EXECUTING", "STABILIZING", "COMPLETED", "CANCELLED", "FAILED"] = "EXECUTING"
    started_at: datetime
    simulation_started_at: float
    initial_risk: float
    steps: list[EmergencyStep]
    events: list[dict] = Field(default_factory=list)
class CompareRequest(EmergencyModel):
    plan_codes: list[str] = Field(default_factory=lambda:["FLOOD-A","FLOOD-B","FLOOD-C"],min_length=1,max_length=3)
    horizon_minutes: Literal[30] = 30
class PreviewRequest(EmergencyModel):
    plan_code: str
    horizon_minutes: Literal[30] = 30
class ExecuteRequest(EmergencyModel):
    plan_code: str
    comparison_id: str = Field(min_length=1,max_length=40)
    confirmed_simulation: bool = False
