from datetime import datetime
from sqlalchemy import String,JSON,DateTime,Float,Integer,UniqueConstraint,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from app.models.base import Base
class PipelineLeakEvent(Base):
    __tablename__="pipeline_leak_events"
    id:Mapped[str]=mapped_column(String(40),primary_key=True)
    scenario_id:Mapped[str]=mapped_column(String(40),unique=True)
    pipeline_id:Mapped[str|None]=mapped_column(String(40))
    detected_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    confirmed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    peak_detection_score:Mapped[float]=mapped_column(Float)
    peak_risk:Mapped[float]=mapped_column(Float)
    status:Mapped[str]=mapped_column(String(24))
    state_json:Mapped[dict]=mapped_column(JSON)
class PipelineLeakSnapshot(Base):
    __tablename__="pipeline_leak_snapshots"
    __table_args__=(UniqueConstraint("scenario_id","simulation_time",name="uq_leak_snapshot_time"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    scenario_id:Mapped[str]=mapped_column(String(40),index=True)
    timestamp:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    simulation_time:Mapped[float]=mapped_column(Float)
    pipeline_id:Mapped[str|None]=mapped_column(String(40))
    pressure:Mapped[float]=mapped_column(Float)
    flow:Mapped[float]=mapped_column(Float)
    leak_severity:Mapped[float]=mapped_column(Float)
    detection_score:Mapped[float]=mapped_column(Float)
    risk_score:Mapped[float]=mapped_column(Float)
    top_suspects:Mapped[list]=mapped_column(JSON)
    affected_count:Mapped[int]=mapped_column(Integer)
class PipelineLeakIsolation(Base):
    __tablename__="pipeline_leak_isolations"
    id:Mapped[str]=mapped_column(String(40),primary_key=True)
    scenario_id:Mapped[str]=mapped_column(String(40),index=True)
    state_hash:Mapped[str]=mapped_column(String(64))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    comparison_json:Mapped[dict]=mapped_column(JSON)
    execution_json:Mapped[dict|None]=mapped_column(JSON)
