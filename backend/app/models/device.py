from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_code: Mapped[str] = mapped_column(String(32), unique=True)
    device_name: Mapped[str] = mapped_column(String(100))
    device_type: Mapped[str] = mapped_column(String(32), index=True)
    building_id: Mapped[str] = mapped_column(String(32))
    area_id: Mapped[str] = mapped_column(String(64))
    position_x: Mapped[float] = mapped_column(Float)
    position_y: Mapped[float] = mapped_column(Float)
    position_z: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    health_score: Mapped[float] = mapped_column(Float)
    install_date: Mapped[date] = mapped_column(Date)
    runtime_hours: Mapped[float] = mapped_column(Float)
    last_maintenance: Mapped[date] = mapped_column(Date)
    rated_power: Mapped[float] = mapped_column(Float)
    rated_rpm: Mapped[float] = mapped_column(Float)
    rated_current: Mapped[float] = mapped_column(Float)
    rated_capacity: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
