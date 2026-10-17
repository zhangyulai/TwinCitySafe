from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class IncidentInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)

class CloseIncident(IncidentInput):
    result: str = Field(min_length=1, max_length=3000)
    operator: str = Field(default='demo-user', min_length=1, max_length=100)
    confirmed: bool = False

class CreateWorkOrder(IncidentInput):
    incident_id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default='', max_length=2000)
    category: str = Field(default='EMERGENCY', min_length=1, max_length=40)
    priority: Literal['LOW','NORMAL','HIGH','CRITICAL'] = 'HIGH'
    assignee: str | None = Field(default=None, max_length=100)
    created_by: str = Field(default='demo-user', min_length=1, max_length=100)

class UpdateWorkOrder(IncidentInput):
    status: Literal['ASSIGNED','IN_PROGRESS','COMPLETED','CANCELLED']
    assignee: str | None = Field(default=None, max_length=100)
    result: str | None = Field(default=None, max_length=3000)
