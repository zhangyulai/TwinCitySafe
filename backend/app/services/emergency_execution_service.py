"""The same deterministic action scheduler runs on live and independent cloned state."""
from datetime import datetime, UTC
from uuid import uuid4
from app.schemas.emergency import EmergencyExecutionState, EmergencyStep
from app.services.flood_service import FloodService

class EmergencyExecutionEngine:
    @staticmethod
    def create(state, plan, comparison_id):
        f=state.flood
        return EmergencyExecutionState(id=str(uuid4()), scenario_id=f.scenario_id,
            plan_code=plan["plan_code"],plan_name=plan["name"],comparison_id=comparison_id,
            started_at=datetime.now(UTC),simulation_started_at=f.elapsed_simulation_seconds,
            initial_risk=f.risk_score,steps=[EmergencyStep(index=i,action=a) for i,a in enumerate(plan["actions"])])

    @staticmethod
    def event(execution, state, message, step=None):
        execution.events.append({"sequence":len(execution.events)+1,"timestamp":datetime.now(UTC).isoformat(),
            "simulation_time":state.flood.elapsed_simulation_seconds,"message":message,
            "step":step.index if step else None,"status":step.status if step else execution.status})

    @staticmethod
    def cancel(execution,state,message="用户取消后续步骤；已施加动作保留"):
        for step in execution.steps:
            if step.status == "pending":step.status="cancelled";step.message="尚未开始，已取消"
            elif step.status == "executing":step.status="completed";step.message="动作已施加，取消不撤销；设备过渡继续"
        execution.status="cancelled";execution.phase="CANCELLED"
        EmergencyExecutionEngine.event(execution,state,message)

    @staticmethod
    def advance(frame):
        s=frame._state; x=s.emergency
        if x is None:return
        if x.scenario_id!=s.flood.scenario_id:return
        if x.status=="completed":
            if x.phase!="STABILIZING" and s.flood.risk_score<x.initial_risk-1 and s.flood.growth_rate<=0:
                x.phase="STABILIZING";EmergencyExecutionEngine.event(x,s,"风险开始回落；继续监测，事件未关闭")
            return
        if x.status not in ("pending","executing"):return
        x.status="executing"
        now=s.flood.elapsed_simulation_seconds
        for step in sorted(x.steps,key=lambda item:(item.action.delay_seconds,item.action.priority,item.index)):
            a=step.action
            if step.status=="pending" and now+1e-8>=x.simulation_started_at+a.delay_seconds:
                try:
                    if a.action_type in ("START_PUMP","STOP_PUMP","SET_PUMP_STATE"):
                        command="running" if a.action_type=="START_PUMP" else "standby" if a.action_type=="STOP_PUMP" else a.parameters["status"]
                        device=next(d for d in s.devices if d.id==a.target_id)
                        if command=="running" and (device.status=="offline" or device.fault!="normal"):raise ValueError("设备已不可用")
                        frame.devices.set_state(s.devices,a.target_id,command)
                    elif a.action_type in ("CLOSE_ENTRANCE","OPEN_ENTRANCE"):
                        FloodService.set_entrance(s.flood,a.action_type=="CLOSE_ENTRANCE")
                    elif a.action_type=="REDUCE_OCCUPANCY":
                        s.flood.exposure_remaining=float(s.flood.people_count)
                        s.flood.exposure_target=min(s.flood.people_count,a.parameters["people_count"])
                    else:raise ValueError("动作没有仿真执行适配器")
                    step.status="executing";step.started_simulation_time=now;step.timestamp=datetime.now(UTC)
                    step.message=f"{a.target_id} {a.action_type} 已施加，等待过渡完成"
                    EmergencyExecutionEngine.event(x,s,step.message,step)
                except (KeyError, ValueError, StopIteration) as err:
                    step.status="failed";step.message=f"{a.target_id} 执行失败：{err}"
                    step.timestamp=datetime.now(UTC);x.status="failed";x.phase="FAILED"
                    for other in x.steps:
                        if other.status=="pending":other.status="cancelled"
                    EmergencyExecutionEngine.event(x,s,step.message,step);return
            if step.status=="executing":
                is_start=a.action_type=="START_PUMP" or (a.action_type=="SET_PUMP_STATE" and a.parameters.get("status")=="running")
                if is_start:
                    d=next((d for d in s.devices if d.id==a.target_id),None)
                    if d is None or d.status=="offline" or d.fault!="normal" or frame.devices.commanded.get(a.target_id)!="running":
                        step.status="failed";step.message=f"{a.target_id} 启动被中断";x.status="failed";x.phase="FAILED"
                        for other in x.steps:
                            if other.status=="pending":other.status="cancelled"
                        EmergencyExecutionEngine.event(x,s,step.message,step);return
                settled=not is_start or frame.devices.settling.get(a.target_id,0)<=1e-8
                if settled and now-(step.started_simulation_time or 0)+1e-8>=a.duration_seconds:
                    step.status="completed";step.timestamp=datetime.now(UTC)
                    step.message=f"{a.target_id} 已运行" if is_start else f"{a.target_id} {a.action_type} 已完成"
                    EmergencyExecutionEngine.event(x,s,step.message,step)
        if all(t.status=="completed" for t in x.steps):
            x.status="completed";x.phase="COMPLETED"
            EmergencyExecutionEngine.event(x,s,"方案动作完成；继续观察风险，未关闭内涝告警")
