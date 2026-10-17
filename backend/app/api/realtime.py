from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.schemas.realtime import (
    DeviceStateRequest, ParkRealtimeState, SimulationStatus, SpeedRequest, WeatherRequest,
)
from app.services.realtime_service import RealtimeService
from app.websocket.messages import realtime_message

router = APIRouter()
websocket_router = APIRouter()


def service(request: Request) -> RealtimeService:
    instance: RealtimeService | None = getattr(request.app.state, "realtime", None)
    if instance is None:
        raise HTTPException(status_code=503, detail="Realtime service has not started")
    return instance


@router.get("/realtime/state", response_model=ParkRealtimeState)
async def state(request: Request) -> ParkRealtimeState:
    return service(request).engine.snapshot()


@router.get("/simulation/status", response_model=SimulationStatus)
async def status(request: Request) -> SimulationStatus:
    return service(request).engine.status()


@router.post("/simulation/start", response_model=ParkRealtimeState)
async def start(request: Request) -> ParkRealtimeState:
    return service(request).engine.start()


@router.post("/simulation/stop", response_model=ParkRealtimeState)
async def stop(request: Request) -> ParkRealtimeState:
    return service(request).engine.stop()


@router.post("/simulation/reset", response_model=ParkRealtimeState)
async def reset(request: Request) -> ParkRealtimeState:
    instance=service(request)
    async with instance.flood.lock:
        await instance.incidents.abort_current("演示 Reset，历史保留，非正式关闭")
        if instance.engine._state.leak.scenario_id:
            state=await instance.leak.reset();instance.publish(state);return state
        if instance.engine._state.flood.scenario_id:
            instance.engine.stop()
            await instance.flood_storage.archive(reset=True)
        return instance.engine.reset()


@router.post("/simulation/weather", response_model=ParkRealtimeState)
async def weather(body: WeatherRequest, request: Request) -> ParkRealtimeState:
    if service(request).engine._state.flood.scenario_id:
        raise HTTPException(409,"Reset flood scenario before changing standalone weather")
    return service(request).engine.set_weather(body.condition)


@router.post("/simulation/device/{device_id}/state", response_model=ParkRealtimeState)
async def device(device_id: str, body: DeviceStateRequest, request: Request) -> ParkRealtimeState:
    try:
        return service(request).engine.set_device_state(device_id, body.status)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown simulation device") from None


@router.post("/simulation/speed", response_model=ParkRealtimeState)
async def speed(body: SpeedRequest, request: Request) -> ParkRealtimeState:
    return service(request).engine.set_speed(body.speed)


@websocket_router.websocket("/ws/realtime")
async def realtime_socket(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    # CORS middleware does not protect WebSocket handshakes. CLI clients omit Origin.
    if origin is not None and origin not in get_settings().cors_origins:
        await websocket.close(code=1008, reason="Origin is not allowed")
        return
    instance: RealtimeService | None = getattr(websocket.app.state, "realtime", None)
    if instance is None:
        await websocket.close(code=1013, reason="Realtime service is unavailable")
        return
    await instance.connections.connect(websocket, realtime_message(instance.engine.snapshot()))
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except (WebSocketDisconnect, OSError, RuntimeError):
        pass
    finally:
        await instance.connections.disconnect(websocket)
