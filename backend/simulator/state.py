from datetime import UTC, datetime

from app.schemas.realtime import (
    DeviceState, EnvironmentState, ParkRealtimeState, PipelineState, SystemState, WeatherState,
)


def initial_state(session_id: str, *, revision: int = 0, running: bool = True) -> ParkRealtimeState:
    return ParkRealtimeState(
        timestamp=datetime.now(UTC), session_id=session_id, revision=revision, running=running,
        weather=WeatherState(), environment=EnvironmentState(), system=SystemState(),
        devices=[
            DeviceState(id="P01", name="P01 备用排水泵", status="standby", temperature=28,
                        vibration=0.2, current=0, rpm=0, efficiency=100, health=95),
            DeviceState(id="P02", name="P02 备用排水泵", status="standby", temperature=28,
                        vibration=0.2, current=0, rpm=0, efficiency=100, health=95),
            DeviceState(id="P03", name="P03 主排水泵", status="running", temperature=42,
                        vibration=1.8, current=18, rpm=1450, efficiency=96, health=94),
        ],
        pipelines=[
            PipelineState(id="WS-001", type="water", pressure=0.42, flow=28),
            PipelineState(id="DS-001", type="drain", pressure=0.08, flow=20),
            PipelineState(id="FS-001", type="fire", pressure=0.48, flow=2),
        ],
    )
