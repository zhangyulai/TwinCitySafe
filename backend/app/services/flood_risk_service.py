from simulator import flood_config as cfg
from app.schemas.flood import FloodRiskBreakdown, FloodRiskFactor, FloodAlarm

def clamp(value):return max(0.0,min(1.0,value))

def water_risk(level):
    for (a,x),(b,y) in zip(cfg.WATER_RISK_KNOTS,cfg.WATER_RISK_KNOTS[1:]):
        if level<=b:return x+(y-x)*clamp((level-a)/(b-a))
    return 1.0

class FloodRiskService:
    @staticmethod
    def update(state):
        values={"water":water_risk(state.water_level),"rainfall":clamp(state.rainfall/cfg.RISK_RAIN_SCALE),
            "pump":clamp(1-state.effective_pump_capacity/cfg.REFERENCE_CAPACITY_M3S),
            "trend":clamp(state.growth_rate/cfg.RISK_TREND_SCALE),
            "exposure":clamp(.6*state.people_count/cfg.EXPOSURE_PEOPLE_SCALE+.4*state.vehicle_count/cfg.EXPOSURE_VEHICLE_SCALE)}
        labels={"water":"积水水位","rainfall":"降雨强度","pump":"泵站能力","trend":"上涨趋势","exposure":"人员 / 车辆暴露"}
        points={key:100*cfg.RISK_WEIGHTS[key]*value for key,value in values.items()}
        score=max(0,min(100,sum(points.values())))
        state.risk_score=score
        state.risk_breakdown=FloodRiskBreakdown(factors=[FloodRiskFactor(key=k,label=labels[k],weight=cfg.RISK_WEIGHTS[k],normalized_value=v,
            points=points[k],contribution=points[k]/score*100 if score else 0) for k,v in values.items()])
        risk_index=sum(score>=t for t in cfg.RISK_LEVEL_THRESHOLDS)
        water_index=sum(state.water_level>=t for t in cfg.WATER_STAGE_THRESHOLDS)
        state.risk_level=["low","general","elevated","high","extreme"][risk_index]
        state.stage=["normal","watch","warning","high","extreme"][max(risk_index,water_index)]
        state.requires_emergency=score>=60
        state.peak_risk=max(state.peak_risk,score)
        if state.scenario_id and state.stage!="normal":
            severity={"watch":"info","warning":"warning","high":"major","extreme":"critical"}[state.stage]
            state.alarm=FloodAlarm(id="FLOOD-"+state.scenario_id,level=severity,stage=state.stage,peak_risk=state.peak_risk,
                message=f"B2 内涝场景：水位 {state.water_level:.1f} cm，场景风险 {score:.1f}，{'建议进入应急方案推演' if score>=60 else '持续关注演化'}")
