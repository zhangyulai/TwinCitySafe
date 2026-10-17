"""One feature contract used by both dataset generation and serving.
Known future rain-plan integrals are inputs, never future observed water/risk.
HI/IF scores are omitted: derived diagnostics do not independently drive M5 physics.
"""
import numpy as np
from simulator import flood_config as cfg
from .config import STATUS, STAGE, FAULT
from .simulation import planned_rain, planned_mean
FEATURE_NAMES = (
    "rainfall_current", "rainfall_trend", "rainfall_target", "planned_rain_mean_10m", "planned_rain_mean_20m", "planned_rain_mean_30m",
    "water_level", "water_area", "flood_volume", "water_growth_rate", "natural_drainage",
    "pump_total_capacity", "pump_effective_capacity",
    "p01_status", "p01_efficiency", "p01_rated_capacity", "p02_status", "p02_efficiency", "p02_rated_capacity",
    "p03_status", "p03_efficiency", "p03_rated_capacity", "p03_fault", "p03_fault_age", "p03_auto_fault_remaining",
    "people_count", "vehicle_count", "current_risk_score", "current_stage", "time_since_scenario_start",
)
LABELS = dict(zip(FEATURE_NAMES, (
    "当前降雨", "降雨变化速度", "当前计划雨量", "未来10分钟计划平均雨量", "未来20分钟计划平均雨量", "未来30分钟计划平均雨量",
    "当前水位", "积水面积", "积水体积", "水位上涨速度", "自然排水", "运行泵额定能力", "运行泵有效能力",
    "P01指令", "P01效率", "P01额定排量", "P02指令", "P02效率", "P02额定排量",
    "P03指令", "P03效率", "P03额定排量", "P03故障类型", "P03故障持续时间", "计划故障剩余时间",
    "人员数量", "车辆数量", "当前规则风险", "当前场景阶段", "场景持续时间")))

def build_features(engine):
    s=engine._state; f=s.flood
    profile=getattr(engine,"rain_profile",cfg.scenario_profile(f))
    t=f.elapsed_simulation_seconds
    target=planned_rain(profile,t)
    rated,effective=engine.flood.capacities(s.devices)
    values=[s.weather.rainfall,(target-s.weather.rainfall)/cfg.RAIN_TAU_SECONDS,target,
            *[planned_mean(profile,t,h*60) for h in (10,20,30)],
            f.water_level,f.water_area,f.flood_volume,f.growth_rate,cfg.NATURAL_DRAINAGE_M3S,rated,effective]
    for id in ("P01","P02","P03"):
        d=next(d for d in s.devices if d.id==id)
        values.extend([STATUS[engine.devices.commanded.get(id,d.status)],d.efficiency,engine.flood.rated_capacities[id]])
    p03=next(d for d in s.devices if d.id=="P03")
    values.extend([FAULT[p03.fault],min(1800,engine.devices.fault_age.get("P03",0)),
                   max(0,cfg.AUTO_FAULT_SECONDS-t) if f.auto_fault and not f.fault_triggered else -1,
                   f.people_count,f.vehicle_count,f.risk_score,STAGE[f.stage],t])
    row=np.asarray(values,dtype=np.float32)
    if row.shape!=(len(FEATURE_NAMES),) or not np.isfinite(row).all():
        raise ValueError("Invalid M6 features")
    return row
