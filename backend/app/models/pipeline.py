from datetime import date, datetime
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, JSON, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PipelineNode(Timestamps, Base):
    __tablename__ = "pipeline_nodes"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    node_code: Mapped[str] = mapped_column(String(40), unique=True)
    node_type: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(100))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    z: Mapped[float] = mapped_column(Float)
    building_id: Mapped[str | None] = mapped_column(String(40))
    area_id: Mapped[str] = mapped_column(String(40))
    attributes: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

class PipelineEdge(Timestamps, Base):
    __tablename__ = "pipeline_edges"
    __table_args__ = (CheckConstraint("start_node_id <> end_node_id", name="edge_distinct_nodes"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    pipeline_code: Mapped[str] = mapped_column(String(40), unique=True)
    pipeline_type: Mapped[str] = mapped_column(String(16), index=True)
    start_node_id: Mapped[str] = mapped_column(ForeignKey("pipeline_nodes.id"))
    end_node_id: Mapped[str] = mapped_column(ForeignKey("pipeline_nodes.id"))
    diameter: Mapped[float] = mapped_column(Float)
    length: Mapped[float] = mapped_column(Float)
    depth: Mapped[float] = mapped_column(Float)
    material: Mapped[str] = mapped_column(String(40))
    install_date: Mapped[date] = mapped_column(Date)
    design_pressure: Mapped[float] = mapped_column(Float)
    current_pressure: Mapped[float] = mapped_column(Float)
    current_flow: Mapped[float] = mapped_column(Float)
    health_score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="normal")

class Valve(Timestamps, Base):
    __tablename__ = "valves"
    __table_args__ = (CheckConstraint("open_percentage >= 0 AND open_percentage <= 100", name="valve_open_bounds"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    valve_code: Mapped[str] = mapped_column(String(40), unique=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("pipeline_nodes.id"), unique=True)
    valve_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="open")
    open_percentage: Mapped[float] = mapped_column(Float, default=100)
    last_maintenance: Mapped[date] = mapped_column(Date)
