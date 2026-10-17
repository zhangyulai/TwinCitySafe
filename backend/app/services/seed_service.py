from datetime import date
from sqlalchemy.orm import Session
from app.models import Device

def seed_devices(session: Session) -> int:
    added = 0
    for i, code in enumerate(("P01", "P02", "P03")):
        if session.get(Device, code):
            continue
        session.add(Device(id=code, device_code=code, device_name=f"{code} {'主' if i == 2 else '备用'}排水泵",
            device_type="pump", building_id="B2-PARKING", area_id="B2 排水机房",
            position_x=(i-1)*10, position_y=-5.45, position_z=23,
            status="running" if i == 2 else "standby", health_score=94 if i == 2 else 95,
            install_date=date(2025,3,12), runtime_hours=4138 if i == 2 else 480+i*120,
            last_maintenance=date(2026,9,18), rated_power=11, rated_rpm=1450, rated_current=18, rated_capacity=120))
        added += 1
    session.commit()
    return added
