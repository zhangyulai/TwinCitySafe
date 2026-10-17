from typing import Literal
from app.schemas.realtime import WireModel
PipelineType = Literal["water", "drainage", "fire"]
PipelineStatus = Literal["normal", "warning", "offline", "isolated"]
class ValveStateRequest(WireModel):
    status: Literal["open", "closed"]
