from fastapi import APIRouter,Request,Query,HTTPException,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.realtime import service
from app.api.devices import storage_db
from app.models.risk_prediction import RiskPredictionRecord
router=APIRouter(prefix="/risk")

@router.get('/prediction')
async def prediction(request:Request,horizons:str=Query('10,20,30',max_length=30)):
    try:
        values=sorted(set(int(v) for v in horizons.split(',')))
        if not values or any(v not in (10,20,30) for v in values):raise ValueError()
    except ValueError:raise HTTPException(422,'Available horizons: 10,20,30') from None
    result=await service(request).risk.prediction()
    for key in ('physicalForecast','mlForecast','comparison'):result[key]=[p for p in result[key] if p['minute'] in values]
    return result

@router.get('/model/status')
async def status(request:Request):return service(request).risk.status()

@router.get('/prediction/explanation')
async def explanation(request:Request,minutes:int=30):
    if minutes not in (10,20,30):raise HTTPException(422,'Available minutes: 10,20,30')
    return await service(request).risk.explanation(minutes)

@router.get('/evaluation')
async def evaluation(request:Request):
    realtime=service(request)
    return realtime.risk.evaluation.summary(realtime.engine._state.flood.scenario_id)

@router.get('/predictions/{scenario_id}')
def history(scenario_id:str,session:Session=Depends(storage_db)):
    rows=session.scalars(select(RiskPredictionRecord).where(RiskPredictionRecord.scenario_id==scenario_id).order_by(RiskPredictionRecord.origin_time.desc()).limit(300))
    return [{'id':r.id,'originTime':r.origin_time,'targetTime':r.target_time,'minutes':r.horizon_minutes,
             'predictedWater':r.predicted_water,'predictedRisk':r.predicted_risk,'physicalWater':r.physical_water,'physicalRisk':r.physical_risk,
             'status':r.evaluation_status,'actualWater':r.actual_water,'actualRisk':r.actual_risk,'waterError':r.water_error,'riskError':r.risk_error} for r in rows]
