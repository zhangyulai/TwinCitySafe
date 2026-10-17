from math import sin
from collections import deque
from simulator import flood_config as cfg

from app.schemas.realtime import EnvironmentState
from simulator.config import MAX_WATER_LEVEL, relax


class FloodSimulator:
    def __init__(self):
        self.rated_capacities = dict(cfg.DEFAULT_RATED_CAPACITY_M3H)
        self.history = deque(maxlen=62)
        self.last_history_time = -1.0

    def reset_history(self, time=0, level=cfg.INITIAL_LEVEL_CM):
        self.history.clear()
        self.history.append((time,level))
        self.last_history_time=time

    def capacities(self, devices):
        active=[d for d in devices if d.status in ("running","warning")]
        rated=sum(self.rated_capacities.get(d.id,0)/3600 for d in active)
        effective=sum(self.rated_capacities.get(d.id,0)/3600*d.efficiency/100*d.startup_progress for d in active)
        return rated,effective

    def tick_scenario(self, state, environment, rainfall, devices, dt):
        if state.exposure_remaining is not None and dt > 0:
            from math import exp, ceil
            state.exposure_remaining = state.exposure_target + max(0, state.exposure_remaining-state.exposure_target)*exp(-dt/300)
            state.people_count = ceil(state.exposure_remaining)
        rated,effective=self.capacities(devices)
        incoming=rainfall/1000/3600*cfg.CATCHMENT_AREA_M2*cfg.RUNOFF_COEFFICIENT
        available=state.flood_volume/dt+incoming if dt>0 else (float("inf") if state.flood_volume>0 else incoming)
        outgoing=min(available,cfg.NATURAL_DRAINAGE_M3S+effective)
        state.flood_volume=max(0,state.flood_volume+(incoming-outgoing)*dt)
        state.water_level=state.flood_volume/cfg.PARKING_EFFECTIVE_AREA_M2*100
        state.water_area=cfg.PARKING_EFFECTIVE_AREA_M2*min(1,(state.water_level/cfg.AREA_FULL_DEPTH_CM)**cfg.AREA_EXPONENT)
        state.rainfall=rainfall
        state.surface_inflow=incoming
        state.natural_drainage=cfg.NATURAL_DRAINAGE_M3S
        state.pump_capacity=rated
        state.effective_pump_capacity=effective
        state.pump_efficiency=effective/rated*100 if rated else 0
        state.outflow=outgoing
        state.elapsed_simulation_seconds+=dt
        state.peak_water_level=max(state.peak_water_level,state.water_level)
        environment.b2_water_level=state.water_level
        environment.b2_water_area=state.water_area
        if state.elapsed_simulation_seconds-self.last_history_time>=1-1e-8:
            self.history.append((state.elapsed_simulation_seconds,state.water_level))
            self.last_history_time=state.elapsed_simulation_seconds
        state.growth_rate=self.growth_rate(state.elapsed_simulation_seconds)

    def growth_rate(self, now):
        points=[(t,h) for t,h in self.history if t>=now-cfg.HISTORY_SECONDS]
        if len(points)<2:return 0.0
        origin=points[0][0]
        x=[t-origin for t,h in points];y=[h for t,h in points]
        mx,my=sum(x)/len(x),sum(y)/len(y)
        denominator=sum((t-mx)**2 for t in x)
        return sum((t-mx)*(h-my) for t,h in zip(x,y))/denominator*60 if denominator else 0.0

    def tick(self, state: EnvironmentState, rainfall: float, pump_capacity: float, time: float, dt: float) -> None:
        # cm/s: seepage + mild rainfall input - effective pumping - passive drainage.
        inflow = 0.0016 + rainfall * 0.00045
        drainage = 0.0017 * pump_capacity + 0.005 * (state.b2_water_level - 0.8)
        state.b2_water_level = min(MAX_WATER_LEVEL, max(0.45, state.b2_water_level + (inflow - drainage) * dt))
        state.b2_water_area = max(0, state.b2_water_level - 0.8) * 45
        state.air_quality = relax(state.air_quality, 92 + 0.4 * sin(time / 120), dt, 35)
        state.smoke = 0
