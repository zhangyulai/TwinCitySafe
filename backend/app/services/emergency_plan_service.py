from copy import deepcopy
from datetime import datetime, UTC
from hashlib import sha256
import json
from app.schemas.emergency import EmergencyAction
from app.services.emergency_execution_service import EmergencyExecutionEngine


def default_templates():
    def action(kind,target,delay=0):return EmergencyAction(action_type=kind,target_id=target,delay_seconds=delay).model_dump()
    a=action("START_PUMP","P01");b=action("START_PUMP","P02",10);c=action("CLOSE_ENTRANCE","B2-EAST",20)
    return [dict(id=code,plan_code=code,name=name,description=description,scenario_type="flood",actions=actions,enabled=True)
        for code,name,description,actions in [
        ("FLOOD-A","方案 A · 单备用泵","启动 P01 增加排水能力，资源投入较少；降水效果取决于实际入流。",[a]),
        ("FLOOD-B","方案 B · 双备用泵","依次启动 P01、P02，10 秒错峰；增加排水能力，不能保证超过持续暴雨入流。",[a,b]),
        ("FLOOD-C","方案 C · 双泵与入口封控","双泵排水并封控 B2 东入口，人员暴露按 5 分钟时间常数渐减；保留现有车辆和水量。",[a,b,c])]]

class EmergencyPlanMatchService:
    @staticmethod
    def reasons(frame,plan):
        s=frame._state;f=s.flood;reasons=[]
        if not plan.get("enabled"):reasons.append("模板已停用")
        if plan.get("scenario_type")!="flood":reasons.append("场景类型不匹配")
        if not f.scenario_id or f.status in ("idle","completed"):reasons.append("没有可执行的活动内涝场景")
        if s.emergency and s.emergency.status in ("pending","executing"):reasons.append("当前已有应急动作执行中")
        from app.core.config import get_settings
        if get_settings().app_env!="development" and f.risk_score<60:reasons.append("正式演示需达到高风险阈值 60；低风险强制推演仅用于 DEV")
        devices={d.id:d for d in s.devices};seen={}
        for raw in plan["actions"]:
            try:a=EmergencyAction.model_validate(raw)
            except ValueError:reasons.append("动作模型无效");continue
            kind=a.action_type;target=a.target_id
            if target in seen:reasons.append(f"{target} 存在重复或冲突动作")
            seen[target]=kind
            if kind in ("CLOSE_VALVE","OPEN_VALVE"):
                reasons.append("M7 不支持阀门动作的内涝水力推演，请使用 M4 管网控制")
            elif kind in ("START_PUMP","STOP_PUMP","SET_PUMP_STATE"):
                d=devices.get(target)
                if d is None:reasons.append(f"{target} 泵不存在")
                elif d.status=="offline" or d.fault!="normal":reasons.append(f"{target} 当前不可用（离线或故障）")
                if target not in frame.flood.rated_capacities:reasons.append(f"{target} 缺少额定排量")
                if kind=="SET_PUMP_STATE" and a.parameters.get("status") not in ("running","standby"):reasons.append("泵指令只支持 running / standby")
                allowed={"status"} if kind=="SET_PUMP_STATE" else set()
                if set(a.parameters)-allowed:reasons.append("泵动作参数不支持")
            elif kind in ("CLOSE_ENTRANCE","OPEN_ENTRANCE","REDUCE_OCCUPANCY"):
                if target!="B2-EAST":reasons.append(f"入口 {target} 不存在")
                if kind=="REDUCE_OCCUPANCY":
                    n=a.parameters.get("people_count")
                    if type(n) is not int or not 0<=n<=500 or set(a.parameters)!={"people_count"}:reasons.append("人员目标必须为 0–500 的整数")
                elif a.parameters:reasons.append("入口动作不接受隐含入流参数")
        if not plan["actions"] or len(plan["actions"])>10:reasons.append("动作数量需为 1–10")
        return list(dict.fromkeys(reasons))

    @classmethod
    def match(cls,frame,plans):
        return [{**deepcopy(p),"available":not (reasons:=cls.reasons(frame,p)),"unavailable_reasons":reasons,
                 "risk_stage":frame._state.flood.stage} for p in plans]


def key_state(frame):
    s=frame._state;f=s.flood
    return {"session":s.session_id,"scenario":f.scenario_id,"rain_plan":f.rainfall_recession,
            "entrance":f.entrance_closed,"people":f.people_count,"vehicles":f.vehicle_count,
            "devices":[[d.id,frame.devices.commanded.get(d.id,d.status),d.fault,frame.flood.rated_capacities.get(d.id)] for d in s.devices],
            "execution":s.emergency.id if s.emergency else None}

def baseline_signature(frame):
    s=frame._state
    payload={"state":s.model_dump(mode="json"),"commands":frame.devices.commanded,"fault_age":frame.devices.fault_age,
             "settling":frame.devices.settling,"ratings":frame.flood.rated_capacities,"history":list(frame.flood.history),
             "profile":getattr(frame,"rain_profile",None)}
    return sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

class EmergencyPlanSimulationService:
    @staticmethod
    def rollout(baseline,plan,horizon=30):
        # Copy the common captured frame, never the previous candidate's output.
        from algorithm.risk_prediction.simulation import SimulationCopy
        frame=SimulationCopy(baseline);s=frame._state;f=s.flood
        s.emergency=None
        if plan:s.emergency=EmergencyExecutionEngine.create(s,plan,"counterfactual")
        first60=0.0 if f.risk_score<60 else None;first40=0.0 if f.risk_score<40 else None
        peakwater=f.water_level;peakrisk=f.risk_score;runtime={"P01":0.,"P02":0.};timeline=[]
        def point(minute):
            return {"minute":minute,"water_level":f.water_level,"risk_score":f.risk_score,"water_area":f.water_area,
                    "pump_capacity":f.effective_pump_capacity,"exposure":{"people":f.people_count,"vehicles":f.vehicle_count},
                    "rainfall":f.rainfall}
        timeline.append(point(0))
        for second in range(5,horizon*60+1,5):
            frame.step(5)
            for d in s.devices:
                if d.id in runtime and d.status in ("running","warning"):runtime[d.id]+=5/60
            peakwater=max(peakwater,f.water_level);peakrisk=max(peakrisk,f.risk_score)
            if first60 is None and f.risk_score<60:first60=second/60
            if first40 is None and f.risk_score<40:first40=second/60
            if second%60==0:timeline.append(point(second/60))
        closure=bool(plan and any(a["action_type"]=="CLOSE_ENTRANCE" for a in plan["actions"]) and not baseline._state.flood.entrance_closed)
        return {"plan_code":plan["plan_code"] if plan else "BASELINE","plan_name":plan["name"] if plan else "维持当前状态（无新增动作）",
                "baseline_timestamp":baseline._state.timestamp.isoformat(),"horizon_minutes":horizon,
                "final_water_level":f.water_level,"final_risk_score":f.risk_score,"final_risk_level":f.risk_level,
                "final_affected_area":f.water_area,"peak_water_level":peakwater,"peak_risk_score":peakrisk,
                "time_to_risk_below_60":first60,"time_to_risk_below_40":first40,"pump_runtime_minutes":runtime,
                "resource_cost_score":sum(runtime.values())+10*closure,"affected_people":f.people_count,"affected_vehicles":f.vehicle_count,
                "final_pump_capacity":f.effective_pump_capacity,"timeline":timeline}
