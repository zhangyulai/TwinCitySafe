"""Archive queries are read-only; only explicit lifecycle/work-order/report commands write."""
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.api.devices import storage_db
from app.api.realtime import service
from app.models.incident import Incident, WorkOrder, ReviewReport
from app.schemas.incident import CreateWorkOrder, UpdateWorkOrder, CloseIncident
from app.services.incident_service import IncidentService, date
from app.services.incident_replay_service import IncidentReplayService, row_dict

router=APIRouter()
core=IncidentService(None)

@router.get('/incidents')
def list_incidents(type:Literal['FLOOD','PIPELINE_LEAK']|None=None,
        status:Literal['OPEN','DETECTED','CONFIRMED','RESPONDING','STABILIZING','CLOSED','ABORTED']|None=None,
        start_time:datetime|None=None,end_time:datetime|None=None,keyword:str=Query('',max_length=180),
        limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),session:Session=Depends(storage_db)):
    start_time=date(start_time);end_time=date(end_time)
    conditions=[]
    if type:conditions.append(Incident.incident_type==type)
    if status:conditions.append(Incident.status==status)
    if start_time:conditions.append(Incident.started_at>=start_time)
    if end_time:conditions.append(Incident.started_at<=end_time)
    if start_time and end_time and start_time>end_time:raise HTTPException(422,'开始时间不能晚于结束时间')
    if keyword:
        like='%'+keyword.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        conditions.append(or_(Incident.title.ilike(like,escape='\\'),Incident.incident_code.ilike(like,escape='\\'),Incident.area_id.ilike(like,escape='\\')))
    rows=session.scalars(select(Incident).where(*conditions).order_by(Incident.started_at.desc().nulls_last(),Incident.created_at.desc()).offset(offset).limit(limit))
    return {'items':[row_dict(row) for row in rows],'total':session.scalar(select(func.count()).select_from(Incident).where(*conditions))}

@router.get('/incidents/{incident_id}')
def detail(incident_id:str,session:Session=Depends(storage_db)):return core.detail(session,incident_id)

@router.get('/incidents/{incident_id}/timeline')
def timeline(incident_id:str,session:Session=Depends(storage_db)):return core.timeline(session,incident_id)

@router.get('/incidents/{incident_id}/replay')
def replay(incident_id:str,from_time:float|None=Query(None,ge=0,allow_inf_nan=False),to_time:float|None=Query(None,ge=0,allow_inf_nan=False),
        step_seconds:float=Query(5,gt=0,le=3600,allow_inf_nan=False),session:Session=Depends(storage_db)):
    return IncidentReplayService().replay(session,incident_id,from_time,to_time,step_seconds)

@router.get('/incidents/{incident_id}/metrics')
def metrics(incident_id:str,session:Session=Depends(storage_db)):return core.metrics(session,incident_id)

@router.post('/incidents/{incident_id}/close')
async def close(incident_id:str,body:CloseIncident,request:Request):return await service(request).incidents.close(incident_id,body)

@router.get('/incidents/{incident_id}/review')
def review(incident_id:str,session:Session=Depends(storage_db)):
    core.get_incident(session,incident_id)
    row=session.scalar(select(ReviewReport).where(ReviewReport.incident_id==incident_id))
    return {'report':row_dict(row) if row else None}

@router.post('/incidents/{incident_id}/review/generate')
def generate(incident_id:str,session:Session=Depends(storage_db)):
    result=core.generate_report(session,incident_id);session.commit();return result

@router.get('/work-orders')
def list_orders(incident_id:str|None=None,status:Literal['PENDING','ASSIGNED','IN_PROGRESS','COMPLETED','CANCELLED']|None=None,
        limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),session:Session=Depends(storage_db)):
    conditions=[]
    if incident_id:conditions.append(WorkOrder.incident_id==incident_id)
    if status:conditions.append(WorkOrder.status==status)
    rows=session.scalars(select(WorkOrder).where(*conditions).order_by(WorkOrder.created_at.desc()).offset(offset).limit(limit))
    return {'items':[row_dict(r) for r in rows],'total':session.scalar(select(func.count()).select_from(WorkOrder).where(*conditions))}

@router.get('/work-orders/{order_id}')
def order(order_id:str,session:Session=Depends(storage_db)):
    row=session.get(WorkOrder,order_id)
    if row is None:raise HTTPException(404,'工单不存在')
    return row_dict(row)

@router.post('/work-orders')
def create_order(body:CreateWorkOrder,session:Session=Depends(storage_db)):
    result=core.create_work_order(session,body);session.commit();return result

@router.patch('/work-orders/{order_id}')
def update_order(order_id:str,body:UpdateWorkOrder,session:Session=Depends(storage_db)):
    result=core.update_work_order(session,order_id,body);session.commit();return result
