from fastapi import APIRouter, Request, Query
from app.api.realtime import service
from app.schemas.emergency import CompareRequest, PreviewRequest, ExecuteRequest
router=APIRouter(prefix="/emergency")
@router.get("/plans")
async def plans(request:Request,scenario_type:str=Query("flood",max_length=24)):
    return await service(request).emergency.plans(scenario_type)
@router.post("/compare")
async def compare(body:CompareRequest,request:Request):
    return await service(request).emergency.compare(body.plan_codes,body.horizon_minutes)
@router.post("/preview")
async def preview(body:PreviewRequest,request:Request):
    return await service(request).emergency.compare([body.plan_code],body.horizon_minutes)
@router.post("/execute")
async def execute(body:ExecuteRequest,request:Request):
    s=service(request)
    async with s.flood.lock:
        result=await s.emergency.execute(body);s.publish(s.engine.snapshot());return result
@router.get("/executions/{id}")
async def execution(id:str,request:Request):return await service(request).emergency.get_execution(id)
@router.post("/executions/{id}/cancel")
async def cancel(id:str,request:Request):
    s=service(request)
    async with s.flood.lock:
        result=await s.emergency.cancel(id);s.publish(s.engine.snapshot());return result
@router.get("/status")
def status(request:Request):
    s=service(request).emergency
    return {"storage_available":s.storage_available,"message":s.last_error,"pending_writes":len(s.dirty),
            "compare_latency_ms":list(s.latencies),"execution":s.engine._state.emergency}
