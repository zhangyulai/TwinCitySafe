from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import get_settings
from app.models import Device, DeviceAlarm
from app.services.device_service import DeviceService
from app.api.realtime import service
from app.schemas.operation import DeviceAsset, DeviceAnalysis, Advice, TelemetryHistory, FaultRequest
from app.schemas.realtime import DeviceState, ParkRealtimeState

router = APIRouter()

def storage_db():
    try:
        yield from get_db()
    except SQLAlchemyError:
        raise HTTPException(503, "Device storage unavailable; check PostgreSQL, migration and seed") from None

def current(request, device_id):
    item = next((d for d in service(request).engine.snapshot().devices if d.id == device_id), None)
    if item is None:
        raise HTTPException(404, "Device not found")
    return item

@router.get("/devices", response_model=list[DeviceAsset])
def devices(request: Request, device_type: Literal["pump", "valve", "fan", "distribution_box", "fire_device"] | None = None,
            status: Literal["normal", "running", "standby", "warning", "offline"] | None = None,
            keyword: str = Query(default="", max_length=100), session: Session = Depends(storage_db)):
    query = select(Device).order_by(Device.device_code)
    if device_type:
        query = query.where(Device.device_type == device_type)
    snapshot = service(request).engine.snapshot()
    items = [DeviceService.serialize(item, snapshot) for item in session.scalars(query)]
    needle = keyword.strip().casefold()
    return [d for d in items if (not needle or needle in (d.device_code + d.device_name).casefold()) and
        (status is None or d.status == status or status == "normal" and d.status in ("running", "standby"))]

@router.get("/devices/{device_id}", response_model=DeviceAsset)
def detail(device_id: str, request: Request, session: Session = Depends(storage_db)):
    return DeviceService.serialize(DeviceService.asset(session, device_id), service(request).engine.snapshot())

@router.get("/devices/{device_id}/realtime", response_model=DeviceState)
def realtime(device_id: str, request: Request):
    return current(request, device_id)

@router.get("/devices/{device_id}/health")
def health(device_id: str, request: Request):
    d = current(request, device_id)
    return {"deviceId": device_id, "healthScore": d.health, "grade": d.analysis.health_grade,
            "target": d.analysis.health_target, "method": "weighted_deviation_exponential_smoothing"}

@router.get("/devices/{device_id}/anomaly", response_model=DeviceAnalysis)
def anomaly(device_id: str, request: Request):
    return current(request, device_id).analysis

@router.get("/devices/{device_id}/maintenance-advice", response_model=Advice)
def advice(device_id: str, request: Request):
    return current(request, device_id).analysis.advice

@router.get("/devices/{device_id}/telemetry", response_model=TelemetryHistory)
def telemetry(device_id: str, request: Request, range: Literal["1h", "6h", "24h"] = "1h",
              start_time: datetime | None = None, end_time: datetime | None = None, session: Session = Depends(storage_db)):
    return DeviceService.telemetry(session, device_id, range, start_time, end_time, service(request).telemetry.interval)

@router.get("/devices/{device_id}/alarms")
def alarms(device_id: str, session: Session = Depends(storage_db)):
    DeviceService.asset(session, device_id)
    records = session.scalars(select(DeviceAlarm).where(DeviceAlarm.device_id == device_id).order_by(DeviceAlarm.created_at.desc()).limit(100)).all()
    return [{"id": a.id, "deviceId": a.device_id, "level": a.level, "message": a.message, "status": a.status,
             "maxScore": a.max_score, "createdAt": a.created_at, "updatedAt": a.updated_at, "resolvedAt": a.resolved_at} for a in records]

@router.get("/telemetry/status")
def sampling_status(request: Request):
    sampler = service(request).telemetry
    return {"available": sampler.available, "intervalSeconds": sampler.interval, "lastSampleAt": sampler.last_sample_at, "message": sampler.last_error}

@router.post("/simulation/device/{device_id}/fault", response_model=ParkRealtimeState)
async def fault(device_id: str, body: FaultRequest, request: Request):
    if get_settings().app_env != "development":
        raise HTTPException(404, "Development control unavailable")
    try:
        return service(request).engine.set_fault(device_id, body.fault)
    except KeyError:
        raise HTTPException(404, "Unknown simulation device") from None
