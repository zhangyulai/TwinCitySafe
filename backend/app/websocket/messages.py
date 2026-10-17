from datetime import datetime
from typing import Literal

from app.schemas.realtime import ParkRealtimeState, WireModel

# Reserved message categories are not generated until their milestone is implemented.
MessageType = Literal["REALTIME_STATE", "DEVICE_UPDATE", "WEATHER_UPDATE", "PIPELINE_UPDATE",
                      "RISK_UPDATE", "ALARM", "SIMULATION_UPDATE", "EMERGENCY_EVENT"]


class RealtimeMessage(WireModel):
    type: Literal["REALTIME_STATE"] = "REALTIME_STATE"
    timestamp: datetime
    data: ParkRealtimeState


def realtime_message(state: ParkRealtimeState) -> str:
    return RealtimeMessage(timestamp=state.timestamp, data=state).model_dump_json(by_alias=True)
