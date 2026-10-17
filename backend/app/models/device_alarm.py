from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class DeviceAlarm(Base):
    __tablename__ = "device_alarms"
    __table_args__ = (Index("uq_active_device_alarm", "device_id", "alarm_type", unique=True,
                          postgresql_where=text("status = 'active'"), sqlite_where=text("status = 'active'")),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    alarm_type: Mapped[str] = mapped_column(String(32))
    level: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    max_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
