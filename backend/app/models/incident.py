"""Business archive index; source simulation records remain immutable history owners."""
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, JSON, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class Incident(Base):
    __tablename__ = 'incidents'
    __table_args__ = (UniqueConstraint('incident_type','source_event_id',name='uq_incident_source'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_code: Mapped[str] = mapped_column(String(64), unique=True)
    incident_type: Mapped[str] = mapped_column(String(24), index=True)
    source_event_id: Mapped[str] = mapped_column(String(40))
    scenario_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(180))
    area_id: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), index=True, default='OPEN')
    source_status: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stabilized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    peak_risk: Mapped[float | None] = mapped_column(Float)
    peak_water_level: Mapped[float | None] = mapped_column(Float)
    peak_detection_score: Mapped[float | None] = mapped_column(Float)
    close_result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class IncidentTimelineEvent(Base):
    __tablename__ = 'incident_timeline_events'
    __table_args__ = (UniqueConstraint('incident_id','event_type','source_id',name='uq_incident_timeline_source'),
        Index('ix_incident_timeline_order','incident_id','simulation_time','event_time'))
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey('incidents.id'), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    simulation_time: Mapped[float | None] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(String(40))
    event_level: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(1500))
    source: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(160))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class IncidentSnapshot(Base):
    __tablename__ = 'incident_snapshots'
    __table_args__ = (UniqueConstraint('incident_id','simulation_time','state_hash',name='uq_incident_snapshot_state'),
        Index('ix_incident_snapshot_order','incident_id','simulation_time','timestamp'))
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey('incidents.id'), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    simulation_time: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(24))
    scene_state: Mapped[dict] = mapped_column(JSON)
    source_snapshot_id: Mapped[str | None] = mapped_column(String(80))
    state_hash: Mapped[str] = mapped_column(String(64))
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)

class WorkOrder(Base):
    __tablename__ = 'work_orders'
    __table_args__ = (UniqueConstraint('incident_id','category',name='uq_work_order_incident_category'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    work_order_code: Mapped[str] = mapped_column(String(64), unique=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey('incidents.id'), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(2000))
    category: Mapped[str] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), index=True, default='PENDING')
    assignee: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(String(3000))
    created_by: Mapped[str] = mapped_column(String(100))

class ReviewReport(Base):
    __tablename__ = 'review_reports'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey('incidents.id'), unique=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(String(4000))
    cause_analysis: Mapped[str] = mapped_column(String(4000))
    response_analysis: Mapped[str] = mapped_column(String(4000))
    prediction_analysis: Mapped[str] = mapped_column(String(4000))
    impact_analysis: Mapped[str] = mapped_column(String(4000))
    lessons: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24))
    metrics: Mapped[dict] = mapped_column(JSON)
