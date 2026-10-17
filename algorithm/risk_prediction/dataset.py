import numpy as np
from simulator.engine import SimulationEngine
from simulator import flood_config as cfg
from app.schemas.flood import FloodScenarioRequest
from app.services.flood_service import FloodService
from app.services.flood_risk_service import FloodRiskService
from .simulation import SimulationCopy
from .features import build_features
from .config import HORIZONS, SEED

FAMILIES = ("normal_healthy", "heavy_healthy", "extreme_healthy", "heavy_degraded", "extreme_degraded",
            "p03_offline", "one_backup", "two_backups", "overheat", "low_efficiency")

def create_scenario(seed, family):
    rng=np.random.default_rng(seed)
    kind="normal" if family==0 else "heavy_rain" if family in (1,3,8) else "extreme_rain"
    e=SimulationEngine()
    FloodService(e).start(FloodScenarioRequest(scenario=kind,duration_minutes=120,
        people_count=int(rng.integers(0,100)),vehicle_count=int(rng.integers(0,120))),linked=False)
    f=e._state.flood
    f.water_level=float(rng.uniform(0,12));f.flood_volume=f.water_level/100*cfg.PARKING_EFFECTIVE_AREA_M2
    # Vary both storm amplitude and ramp duration; runtime uses the same explicit plan features.
    amplitude=float(rng.uniform(.6,1.18));stretch=float(rng.uniform(.65,1.6))
    e.rain_profile=[(t*stretch,min(118,v*amplitude)) for t,v in cfg.RAIN_PROFILES[kind]]
    e._state.weather.rainfall=e.rain_profile[0][1]
    for d in e._state.devices:
        e.flood.rated_capacities[d.id]=float(rng.uniform(85,160))
        d.efficiency=float(rng.uniform(75,100))
    if family in (3,4):
        f.auto_fault=bool(rng.integers(0,2))
        if not f.auto_fault:e.set_fault("P03","bearing_degradation")
    if family==5:e.set_device_state("P03","offline")
    if family in (6,7):e.set_device_state("P01","running")
    if family==7:e.set_device_state("P02","running")
    if family==8:e.set_fault("P03","overheat")
    if family==9:e.set_fault("P03","low_efficiency")
    e.flood.reset_history(0,f.water_level)
    e.flood.tick_scenario(f,e._state.environment,e._state.weather.rainfall,e._state.devices,0)
    FloodRiskService.update(f)
    return SimulationCopy(e)

def scenario_rows(task):
    index,seed,samples=task
    model=create_scenario(seed,index%len(FAMILIES))
    rows=[];outcomes=[]
    # Adjacent samples share deterministic suffixes. Advance a copied trajectory once,
    # then index exact +600/+1200/+1800 s states instead of recomputing overlapping work.
    # Tests compare these labels with independent per-sample cloned rollouts.
    for step in range(samples+180):
        if step<samples:rows.append(build_features(model))
        f=model._state.flood;outcomes.append((f.water_level,f.risk_score))
        if step<samples+179:
            model.step(5);model.step(5)
    targets=[[outcomes[i+h*6][k] for k in (0,1) for h in HORIZONS] for i in range(samples)]
    return np.asarray(rows,dtype=np.float32),np.asarray(targets,dtype=np.float32)

def scenario_split(count, seed=SEED):
    if count<30:raise ValueError("At least 30 independent scenarios required")
    # Stratify by scenario family, grouping all rows from each scenario together.
    rng=np.random.default_rng(seed);groups={"train":[],"validation":[],"test":[]}
    for family in range(len(FAMILIES)):
        ids=np.arange(family,count,len(FAMILIES));rng.shuffle(ids)
        n=len(ids);a=max(1,int(n*.7));b=max(a+1,int(n*.85))
        if n>=3:a=min(a,n-2);b=min(b,n-1)
        for name,part in zip(groups,(ids[:a],ids[a:b],ids[b:])):groups[name].extend(map(int,part))
    return groups
