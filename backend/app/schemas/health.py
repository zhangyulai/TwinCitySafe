from typing import Literal
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["TwinCitySafe"] = "TwinCitySafe"
    version: Literal["2.0"] = "2.0"
