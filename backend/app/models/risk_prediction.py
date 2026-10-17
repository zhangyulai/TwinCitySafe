from datetime import datetime
from sqlalchemy import String,Float,Integer,DateTime,ForeignKey,UniqueConstraint,Index
from sqlalchemy.orm import Mapped,mapped_column
from app.models.base import Base

class RiskPredictionRecord(Base):
    __tablename__="risk_predictions"
    __table_args__=(UniqueConstraint("scenario_id","origin_time","horizon_minutes",name="uq_risk_origin_horizon"),Index("ix_risk_scenario_target","scenario_id","target_time"))
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    scenario_id:Mapped[str]=mapped_column(ForeignKey("flood_scenarios.id"))
    session_id:Mapped[str]=mapped_column(String(40))
    generated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    origin_time:Mapped[float]=mapped_column(Float)
    target_time:Mapped[float]=mapped_column(Float)
    horizon_minutes:Mapped[int]=mapped_column(Integer)
    model_version:Mapped[str|None]=mapped_column(String(40),nullable=True)
    predicted_water:Mapped[float|None]=mapped_column(Float,nullable=True)
    predicted_risk:Mapped[float|None]=mapped_column(Float,nullable=True)
    physical_water:Mapped[float]=mapped_column(Float)
    physical_risk:Mapped[float]=mapped_column(Float)
    agreement:Mapped[str|None]=mapped_column(String(12),nullable=True)
    evaluation_status:Mapped[str]=mapped_column(String(20),default="pending")
    actual_water:Mapped[float|None]=mapped_column(Float,nullable=True)
    actual_risk:Mapped[float|None]=mapped_column(Float,nullable=True)
    sample_span_seconds:Mapped[float|None]=mapped_column(Float,nullable=True)
    water_error:Mapped[float|None]=mapped_column(Float,nullable=True)
    risk_error:Mapped[float|None]=mapped_column(Float,nullable=True)
    physical_water_error:Mapped[float|None]=mapped_column(Float,nullable=True)
    physical_risk_error:Mapped[float|None]=mapped_column(Float,nullable=True)
