from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"
    __table_args__ = (Index("ix_telemetry_device_time", "device_id", "timestamp"),
                     UniqueConstraint("session_id", "revision", "device_id", name="uq_telemetry_snapshot"))
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    session_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(BigInteger)
    temperature: Mapped[float] = mapped_column(Float)
    vibration: Mapped[float] = mapped_column(Float)
    current: Mapped[float] = mapped_column(Float)
    rpm: Mapped[float] = mapped_column(Float)
    efficiency: Mapped[float] = mapped_column(Float)
    health_score: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
