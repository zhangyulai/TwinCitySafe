"""Software demonstration calibration, not an engineering flood design model.
Units: rainfall mm/h; capacities m3/s; volume m3; business depth cm.
"""
CATCHMENT_AREA_M2 = 12000.0
RUNOFF_COEFFICIENT = 0.85
PARKING_EFFECTIVE_AREA_M2 = 1500.0
NATURAL_DRAINAGE_M3S = 0.0015
INITIAL_LEVEL_CM = 0.8
AREA_FULL_DEPTH_CM = 30.0
AREA_EXPONENT = 0.75
DEFAULT_RATED_CAPACITY_M3H = {"P01":120.0,"P02":120.0,"P03":120.0}
REFERENCE_CAPACITY_M3S = 120.0 / 3600
RAIN_TAU_SECONDS = 12.0
AUTO_FAULT_SECONDS = 180.0
DEFAULT_PEOPLE = 32
DEFAULT_VEHICLES = 48
HISTORY_SECONDS = 60.0
SNAPSHOT_INTERVAL_SECONDS = 5.0
RISK_WEIGHTS = {"water":.35,"rainfall":.20,"pump":.20,"trend":.15,"exposure":.10}
WATER_RISK_KNOTS = [(0,0),(3,.10),(8,.30),(15,.65),(25,1.0)]
WATER_STAGE_THRESHOLDS = [3,8,15,25]
RISK_LEVEL_THRESHOLDS = [20,40,60,80]
RAIN_PROFILES = {
 "normal": [(0,8),(120,8)],
 "heavy_rain": [(0,8),(120,30),(300,45),(600,55)],
 "extreme_rain": [(0,8),(120,35),(240,55),(420,72),(600,86),(900,100)],
}
DEMO_EXTREME_RAIN = {"scenario":"extreme_rain","duration_minutes":30,"people_count":32,"vehicle_count":48,"auto_fault":True}

def rainfall_target(scenario,elapsed):
    profile=RAIN_PROFILES[scenario]
    for (a,x),(b,y) in zip(profile,profile[1:]):
        if elapsed<=b:return x+(y-x)*max(0,elapsed-a)/(b-a)
    return profile[-1][1]

RISK_RAIN_SCALE=100.0
RISK_TREND_SCALE=1.0
EXPOSURE_PEOPLE_SCALE=40.0
EXPOSURE_VEHICLE_SCALE=60.0


def scenario_profile(state):
    if state.rainfall_recession and state.scenario == "extreme_rain":
        # Explicit M7 demonstration boundary condition, common to every branch.
        return [*RAIN_PROFILES[state.scenario], (1800,100), (2100,20)]
    return RAIN_PROFILES[state.scenario]

def scenario_rainfall(state):
    profile=scenario_profile(state)
    t=state.elapsed_simulation_seconds
    for (a,x),(b,y) in zip(profile,profile[1:]):
        if t <= b:return x+(y-x)*max(0,t-a)/(b-a)
    return profile[-1][1]
