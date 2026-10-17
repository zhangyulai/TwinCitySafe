from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class FloodScenarioRecord(Base):
    __tablename__="flood_scenarios"
    id: Mapped[str]=mapped_column(String(40),primary_key=True)
    scenario: Mapped[str]=mapped_column(String(24))
    status: Mapped[str]=mapped_column(String(16))
    started_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    simulation_started_at: Mapped[float]=mapped_column(Float)
    elapsed_simulation_seconds: Mapped[float]=mapped_column(Float)
    duration_minutes: Mapped[int]=mapped_column(Integer)
    people_count: Mapped[int]=mapped_column(Integer)
    vehicle_count: Mapped[int]=mapped_column(Integer)
    auto_fault: Mapped[bool]=mapped_column(Boolean)
    current_stage: Mapped[str]=mapped_column(String(16))
    peak_water_level: Mapped[float]=mapped_column(Float)
    peak_risk: Mapped[float]=mapped_column(Float)
    alarm: Mapped[dict|None]=mapped_column(JSON)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class FloodSnapshot(Base):
    __tablename__="flood_snapshots"
    __table_args__=(UniqueConstraint("scenario_id","simulation_time",name="uq_flood_scenario_time"),Index("ix_flood_scenario_time","scenario_id","simulation_time"))
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    scenario_id: Mapped[str]=mapped_column(ForeignKey("flood_scenarios.id"))
    timestamp: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    simulation_time: Mapped[float]=mapped_column(Float)
    rainfall: Mapped[float]=mapped_column(Float)
    water_level: Mapped[float]=mapped_column(Float)
    water_area: Mapped[float]=mapped_column(Float)
    inflow: Mapped[float]=mapped_column(Float)
    outflow: Mapped[float]=mapped_column(Float)
    pump_capacity: Mapped[float]=mapped_column(Float)
    risk_score: Mapped[float]=mapped_column(Float)
    stage: Mapped[str]=mapped_column(String(16))
