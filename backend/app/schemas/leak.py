from pydantic import Field
from typing import Literal
from app.schemas.flood import FloodWire
from simulator.leak_config import DEMO_PIPELINE,DEMO_SEVERITY
class LeakStart(FloodWire):
    pipeline_id:str=Field(default=DEMO_PIPELINE,max_length=40)
    severity:float=Field(default=DEMO_SEVERITY,ge=0,le=1)
class LeakState(FloodWire):
    scenario_id:str|None=None
    scenario_type:str="WATER_SUPPLY_LEAK"
    scenario_name:str="PIPELINE_LEAK_DEMO"
    target_pipeline_id:str|None=None
    status:Literal["idle","running","stopped"]="idle"
    elapsed_simulation_seconds:float=0
    target_severity:float=0
    leak_severity:float=0
    leak_coefficient:float=0
    estimated_leak_flow:float=0
    upstream_pressure:float=0
    downstream_pressure:float=0
    pipeline_flow:float=0
    pressure_drop_rate:float=0
    flow_change_rate:float=0
    detection_score:float=0
    confidence:float=0
    confidence_method:str="多变量软件异常匹配分数，未经概率校准"
    risk_score:float=0
    risk_level:str="low"
    risk_breakdown:list[dict]=Field(default_factory=list)
    detection_breakdown:dict=Field(default_factory=dict)
    suspected_segments:list[dict]=Field(default_factory=list)
    affected_buildings:list[dict]=Field(default_factory=list)
    affected_nodes:list[str]=Field(default_factory=list)
    affected_edges:list[str]=Field(default_factory=list)
    interrupted_buildings:list[dict]=Field(default_factory=list)
    estimated_service_loss:float=0
    current_stage:str="NORMAL"
    leak_status:str="MONITORING"
    service_status:str="AVAILABLE"
    event_id:str|None=None
    detected_at:str|None=None
    confirmed_at:str|None=None
    peak_detection_score:float=0
    peak_risk:float=0
    alarm:dict|None=None
    events:list[dict]=Field(default_factory=list)
    execution:dict|None=None
    localization_latency_ms:float=0
class IsolationCompare(FloodWire):
    pipeline_id:str=Field(max_length=40)
class IsolationExecute(FloodWire):
    option_id:str=Field(max_length=80)
    comparison_id:str=Field(max_length=40)
    confirmed_simulation:bool=False
