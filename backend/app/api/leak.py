from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.realtime import service
from app.api.devices import storage_db
from app.schemas.leak import LeakStart,IsolationCompare,IsolationExecute
from app.models.leak import PipelineLeakEvent,PipelineLeakSnapshot,PipelineLeakIsolation
router=APIRouter()
@router.post("/simulation/pipeline-leak/start")
async def start(body:LeakStart,request:Request):
    s=service(request)
    async with s.flood.lock:
        state=await s.leak.start_scenario(body);s.publish(state);return state
@router.post("/simulation/pipeline-leak/stop")
async def stop(request:Request):
    s=service(request)
    async with s.flood.lock:
        if not s.engine._state.leak.scenario_id:raise HTTPException(409,"没有活动泄漏场景")
        state=s.engine.stop();s.publish(state);await s.leak.sample(state);return state
@router.post("/simulation/pipeline-leak/reset")
async def reset(request:Request):
    s=service(request)
    async with s.flood.lock:
        if s.engine._state.flood.scenario_id:raise HTTPException(409,"请使用内涝场景重置")
        await s.incidents.abort_current("泄漏演示 Reset，历史保留，非正式关闭")
        state=await s.leak.reset();s.publish(state);return state
@router.get("/simulation/pipeline-leak/status")
@router.get("/pipeline-leak/status")
def status(request:Request):return service(request).engine.snapshot().leak
@router.get("/pipeline-leak/localization")
def localization(request:Request):
    f=service(request).engine.snapshot().leak
    return {"suspects":f.suspected_segments,"method":f.confidence_method,"latencyMs":f.localization_latency_ms}
@router.get("/pipeline-leak/risk")
def risk(request:Request):
    f=service(request).engine.snapshot().leak
    return {"riskScore":f.risk_score,"riskLevel":f.risk_level,"breakdown":f.risk_breakdown,"affectedBuildings":f.affected_buildings,"interruptedBuildings":f.interrupted_buildings,"serviceStatus":f.service_status}
@router.post("/pipeline-leak/isolation/compare")
async def compare(body:IsolationCompare,request:Request):
    s=service(request)
    async with s.flood.lock:return await s.leak.compare(body.pipeline_id)
@router.post("/pipeline-leak/isolation/execute")
async def execute(body:IsolationExecute,request:Request):
    s=service(request)
    async with s.flood.lock:
        state=await s.leak.execute(body);s.publish(state);await s.leak.sample(state);return state
@router.get("/pipeline-leak/history/{scenario_id}")
def history(scenario_id:str,session:Session=Depends(storage_db)):
    event=session.scalar(select(PipelineLeakEvent).where(PipelineLeakEvent.scenario_id==scenario_id))
    if event is None:raise HTTPException(404,"事件不存在")
    rows=list(session.scalars(select(PipelineLeakSnapshot).where(PipelineLeakSnapshot.scenario_id==scenario_id).order_by(PipelineLeakSnapshot.simulation_time)))
    if len(rows)>600:rows=rows[::max(1,len(rows)//600+1)]
    actions=list(session.scalars(select(PipelineLeakIsolation).where(PipelineLeakIsolation.scenario_id==scenario_id)))
    return {"event":event.state_json,"status":event.status,"snapshots":[{"time":x.simulation_time,"pressure":x.pressure,"flow":x.flow,"risk":x.risk_score,"suspects":x.top_suspects} for x in rows],"comparisons":[{"id":x.id,"stateHash":x.state_hash,"execution":x.execution_json} for x in actions]}
