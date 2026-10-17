"""Independent copies call the unchanged M5 physics and M3 device models."""
from copy import deepcopy
from simulator import flood_config as cfg
from app.services.flood_risk_service import FloodRiskService

def planned_rain(profile, seconds):
    for (a, x), (b, y) in zip(profile, profile[1:]):
        if seconds <= b:
            return x + (y-x)*max(0, seconds-a)/(b-a)
    return profile[-1][1]

def planned_mean(profile, start, seconds):
    cuts = [start] + [t for t, _ in profile if start < t < start+seconds] + [start+seconds]
    return sum((b-a)*(planned_rain(profile,a)+planned_rain(profile,b))/2 for a,b in zip(cuts,cuts[1:]))/seconds

class SimulationCopy:
    def __init__(self, engine):
        self._state = engine.snapshot()
        self.weather = deepcopy(engine.weather)
        self.devices = deepcopy(engine.devices)
        self.flood = deepcopy(engine.flood)
        self.rain_profile = deepcopy(getattr(engine, "rain_profile", cfg.scenario_profile(self._state.flood)))
    def snapshot(self):
        return self._state.model_copy(deep=True)
    def step(self, dt=5.0):
        from app.services.emergency_execution_service import EmergencyExecutionEngine
        EmergencyExecutionEngine.advance(self)
        s=self._state; f=s.flood
        f.rainfall_target=planned_rain(self.rain_profile,f.elapsed_simulation_seconds)
        self.weather.rainfall_target=f.rainfall_target
        if f.auto_fault and not f.fault_triggered and f.elapsed_simulation_seconds>=cfg.AUTO_FAULT_SECONDS:
            self.devices.set_fault(s.devices,"P03","bearing_degradation"); f.fault_triggered=True
        s.simulation_time+=dt
        self.weather.tick(s.weather,s.simulation_time,dt)
        self.devices.tick(s.devices,s.weather.temperature,s.simulation_time,dt)
        self.flood.tick_scenario(f,s.environment,s.weather.rainfall,s.devices,dt)
        FloodRiskService.update(f)
