from fastapi import APIRouter, Request, HTTPException, Query, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api.realtime import service
from app.api.devices import storage_db
from app.schemas.flood import FloodScenarioRequest, FloodExposureRequest, FloodSimulationState, FloodForecast, FloodScenarioStatus
from app.services.flood_forecast_service import FloodForecastService
from app.models.flood import FloodScenarioRecord, FloodSnapshot
from app.core.config import get_settings
from simulator.flood_config import DEMO_EXTREME_RAIN
router=APIRouter(prefix="/simulation/flood")

def require_dev():
    if get_settings().app_env!="development":raise HTTPException(404,"Development scenario control unavailable")

@router.post("/start")
async def start(body:FloodScenarioRequest,request:Request):
    require_dev()
    s=service(request)
    async with s.flood.lock:
        if s.engine._state.leak.scenario_id:raise HTTPException(409,"当前已有管网泄漏场景，请先重置")
        s.engine.stop()
        await s.incidents.abort_current("新内涝场景替换旧场景，历史中断")
        await s.flood_storage.archive()
        state=s.flood.start(body)
        s.publish(state)
        await s.flood_storage.sample(state)
        return state

@router.post("/demo-start")
async def demo(request:Request):
    s=service(request)
    async with s.flood.lock:
        if s.engine._state.leak.scenario_id:raise HTTPException(409,"当前已有管网泄漏场景，请先重置")
        s.engine.stop()
        await s.incidents.abort_current("演示 Reset 或替换，历史保留，非正式关闭")
        await s.flood_storage.archive(reset=True)
        template={key:value for key,value in DEMO_EXTREME_RAIN.items() if key!="auto_fault"}
        state=s.flood.start(FloodScenarioRequest(**template),linked=DEMO_EXTREME_RAIN["auto_fault"])
        s.publish(state)
        await s.flood_storage.sample(state)
        return state

@router.post("/stop")
async def stop(request:Request):
    s=service(request)
    async with s.flood.lock:
        if s.engine._state.leak.scenario_id:raise HTTPException(409,"当前已有管网泄漏场景，请先重置")
        state=s.flood.stop()
        s.publish(state)
        await s.flood_storage.sample(state)
        return state

@router.post("/reset")
async def reset(request:Request):
    s=service(request)
    async with s.flood.lock:
        if s.engine._state.leak.scenario_id:raise HTTPException(409,"当前已有管网泄漏场景，请先重置")
        s.engine.stop()
        await s.incidents.abort_current("演示 Reset 或替换，历史保留，非正式关闭")
        await s.flood_storage.archive(reset=True)
        state=s.flood.reset()
        s.publish(state)
        return state

@router.post("/exposure")
async def exposure(body:FloodExposureRequest,request:Request):
    require_dev()
    s=service(request)
    async with s.flood.lock:
        if s.engine._state.leak.scenario_id:raise HTTPException(409,"当前已有管网泄漏场景，请先重置")
        state=s.flood.exposure(body)
        s.publish(state)
        return state

@router.get("/status",response_model=FloodSimulationState)
def status(request:Request):return service(request).engine.snapshot().flood

@router.get("/forecast",response_model=FloodForecast)
async def forecast(request:Request,horizons:str=Query("10,20,30",max_length=50)):
    try:
        values=sorted(set(int(x) for x in horizons.split(',')))
        if not values or len(values)>6 or min(values)<1 or max(values)>60:raise ValueError()
    except ValueError:raise HTTPException(422,"horizons must contain 1–6 integer minutes in [1,60]") from None
    # Clone on the event-loop thread before dispatching CPU work.
    from copy import deepcopy
    from types import SimpleNamespace
    engine=service(request).engine
    snapshot=engine.snapshot()
    clone=SimpleNamespace(snapshot=lambda:snapshot.model_copy(deep=True),_state=snapshot,
        weather=deepcopy(engine.weather),devices=deepcopy(engine.devices),flood=deepcopy(engine.flood))
    return await run_in_threadpool(FloodForecastService.forecast,clone,values)

@router.get("/storage",response_model=FloodScenarioStatus)
def storage(request:Request):
    s=service(request).flood_storage
    return FloodScenarioStatus(available=s.available,interval_seconds=s.interval,last_sample_at=s.last_sample_at,message=s.last_error)

@router.get("/scenarios")
def scenarios(session:Session=Depends(storage_db)):
    rows=session.scalars(select(FloodScenarioRecord).order_by(FloodScenarioRecord.started_at.desc()).limit(30))
    return [{"id":r.id,"scenario":r.scenario,"status":r.status,"stage":r.current_stage,"peakWaterLevel":r.peak_water_level,"peakRisk":r.peak_risk,"alarm":r.alarm} for r in rows]

@router.get("/snapshots/{scenario_id}")
def snapshots(scenario_id:str,session:Session=Depends(storage_db)):
    if session.get(FloodScenarioRecord,scenario_id) is None:raise HTTPException(404,"Flood scenario not found")
    rows=list(session.scalars(select(FloodSnapshot).where(FloodSnapshot.scenario_id==scenario_id).order_by(FloodSnapshot.simulation_time)))
    total=len(rows)
    if total>600:rows=[rows[round(i*(total-1)/599)] for i in range(600)]
    return {"source":"database_samples","total":total,"points":[{"simulationTime":r.simulation_time,"waterLevel":r.water_level,"riskScore":r.risk_score,"rainfall":r.rainfall,"pumpCapacity":r.pump_capacity} for r in rows]}

@router.post("/emergency-demo-start")
async def emergency_demo(request:Request):
    s=service(request)
    async with s.flood.lock:
        if s.engine._state.leak.scenario_id:raise HTTPException(409,"当前已有管网泄漏场景，请先重置")
        s.engine.stop();await s.incidents.abort_current("新应急演示替换旧场景，历史中断");await s.flood_storage.archive(reset=True)
        state=s.flood.start(FloodScenarioRequest(scenario="extreme_rain",duration_minutes=60,rainfall_recession=True),linked=True)
        s.publish(state);await s.flood_storage.sample(state);return state
