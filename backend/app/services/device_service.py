from datetime import UTC, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from app.models import Device, DeviceTelemetry
from app.schemas.operation import DeviceAsset, TelemetryHistory, TelemetryPoint

class DeviceService:
    @staticmethod
    def asset(session, device_id):
        asset = session.get(Device, device_id)
        if asset is None:
            raise HTTPException(404, "Device not found")
        return asset

    @staticmethod
    def serialize(asset, snapshot):
        fields = {column.name: getattr(asset, column.name) for column in Device.__table__.columns}
        fields["install_date"] = asset.install_date.isoformat()
        fields["last_maintenance"] = asset.last_maintenance.isoformat()
        live = next((d for d in snapshot.devices if d.id == asset.id), None)
        if live:
            fields.update(status=live.status, health_score=live.health, runtime_hours=live.runtime_hours)
        return DeviceAsset(**fields)

    @staticmethod
    def telemetry(session, device_id, range_, start_time, end_time, interval):
        DeviceService.asset(session, device_id)
        now = datetime.now(UTC)
        if (start_time is None) != (end_time is None):
            raise HTTPException(422, "Provide both start_time and end_time")
        start = start_time or now - timedelta(hours={"1h": 1, "6h": 6, "24h": 24}[range_])
        end = end_time or now
        if start.tzinfo is None or end.tzinfo is None or start >= end or end-start > timedelta(days=1):
            raise HTTPException(422, "Use timezone-aware timestamps and a positive range of at most 24 hours")
        rows = session.scalars(select(DeviceTelemetry).where(DeviceTelemetry.device_id == device_id,
            DeviceTelemetry.timestamp >= start, DeviceTelemetry.timestamp <= end).order_by(DeviceTelemetry.timestamp, DeviceTelemetry.id)).all()
        total = len(rows)
        # Evenly sample the bounded 24h result, preserving endpoints. <=600 ECharts points.
        if total > 600:
            rows = [rows[round(i * (total - 1) / 599)] for i in range(600)]
        points = []
        for row in rows:
            point = TelemetryPoint.model_validate(row)
            if point.timestamp.tzinfo is None:
                point.timestamp = point.timestamp.replace(tzinfo=UTC)
            points.append(point)
        return TelemetryHistory(device_id=device_id, start_time=start, end_time=end, sample_interval_seconds=interval,
            points=points, total=total, downsampled=total > 600)
