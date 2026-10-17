from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictBool
from starlette.concurrency import run_in_threadpool
from app.api.realtime import service
from app.core.config import get_settings
from app.schemas.realtime import ParkRealtimeState
from app.services.demo_service import DemoService
from app.services.readiness_service import system_readiness

router = APIRouter(tags=["system-demo"])


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool


class DemoStart(Confirmation):
    scenario: Literal["flood", "leak"]


class DemoSpeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speed: Literal[1, 2, 5, 10]


def allow_demo():
    settings = get_settings()
    if settings.app_env != "development" and not settings.demo_mode:
        raise HTTPException(404, "演示控制未启用；生产环境需要显式配置 DEMO_MODE=true")


def confirmed(body):
    if not body.confirmed:
        raise HTTPException(422, "请确认：将重置当前软件演示状态，但不会删除历史事故档案。")


@router.get("/system/readiness")
async def readiness(request: Request):
    return await run_in_threadpool(system_readiness, getattr(request.app.state, "realtime", None))


@router.post("/demo/reset", response_model=ParkRealtimeState, dependencies=[Depends(allow_demo)])
async def reset(body: Confirmation, request: Request):
    confirmed(body)
    return await DemoService(service(request)).reset()


@router.post("/demo/start", response_model=ParkRealtimeState, dependencies=[Depends(allow_demo)])
async def start(body: DemoStart, request: Request):
    confirmed(body)
    return await DemoService(service(request)).start(body.scenario)


@router.post("/demo/speed", response_model=ParkRealtimeState, dependencies=[Depends(allow_demo)])
async def speed(body: DemoSpeed, request: Request):
    rt = service(request)
    async with rt.flood.lock:
        state = rt.engine.set_speed(body.speed)
        rt.publish(state)
        return state


@router.post("/demo/pause", response_model=ParkRealtimeState, dependencies=[Depends(allow_demo)])
async def pause(request: Request):
    rt = service(request)
    async with rt.flood.lock:
        state = rt.engine.stop()
        rt.publish(state)
        return state


@router.post("/demo/resume", response_model=ParkRealtimeState, dependencies=[Depends(allow_demo)])
async def resume(request: Request):
    rt = service(request)
    async with rt.flood.lock:
        state = rt.engine.start()
        rt.publish(state)
        return state
