from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Boolean, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class EmergencyPlanTemplate(Base):
    __tablename__ = "emergency_plan_templates"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    scenario_type: Mapped[str] = mapped_column(String(24))
    actions: Mapped[list] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
class EmergencyComparison(Base):
    __tablename__ = "emergency_comparisons"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(40), index=True)
    baseline_state_hash: Mapped[str] = mapped_column(String(64))
    compared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    horizon: Mapped[int] = mapped_column(Integer)
    results_json: Mapped[dict] = mapped_column(JSON)
class EmergencyExecution(Base):
    __tablename__ = "emergency_executions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(40), index=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("emergency_comparisons.id"))
    plan_code: Mapped[str] = mapped_column(String(24))
    operator: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state_json: Mapped[dict] = mapped_column(JSON)
class EmergencyExecutionStep(Base):
    __tablename__ = "emergency_execution_steps"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("emergency_executions.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    state_json: Mapped[dict] = mapped_column(JSON)
