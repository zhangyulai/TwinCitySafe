import asyncio
from datetime import datetime, UTC
from uuid import uuid4
from app.schemas.flood import FloodSimulationState
from simulator import flood_config as cfg

class FloodService:
    def __init__(self, engine):
        self.engine=engine
        self.lock=asyncio.Lock()

    def start(self, request, linked=False):
        e=self.engine
        if e._state.leak.scenario_id:
            from fastapi import HTTPException
            raise HTTPException(409,"当前已有管网泄漏场景，请先重置")
        if linked:
            # Reuse the existing reset and device fault service; no duplicate P03 model.
            e.reset()
        state=e._state
        state.emergency=None
        state.flood=FloodSimulationState(scenario_id=str(uuid4()),scenario=request.scenario,status="running",running=True,
            started_at=datetime.now(UTC),simulation_started_at=state.simulation_time,duration_minutes=request.duration_minutes,
            people_count=request.people_count,vehicle_count=request.vehicle_count,auto_fault=linked,
            rainfall_recession=request.rainfall_recession,
            water_level=cfg.INITIAL_LEVEL_CM,flood_volume=cfg.INITIAL_LEVEL_CM/100*cfg.PARKING_EFFECTIVE_AREA_M2,
            effective_area=cfg.PARKING_EFFECTIVE_AREA_M2)
        state.environment.b2_water_level=cfg.INITIAL_LEVEL_CM
        state.weather.condition="rain"
        state.weather.rainfall=cfg.RAIN_PROFILES[request.scenario][0][1]
        e.weather.rainfall_target=state.weather.rainfall
        e.flood.reset_history()
        e.flood.tick_scenario(state.flood,state.environment,state.weather.rainfall,state.devices,0)
        e.flood_risk.update(state.flood)
        e.start()
        return e._touch()

    @staticmethod
    def set_entrance(state, closed):
        state.entrance_closed = closed
        # Original M5 has fixed occupancy, no simulated vehicle arrivals.
        state.vehicle_entry_rate = 0
        state.exposure_remaining = float(state.people_count) if closed else None
        state.exposure_target = 0

    def stop(self):return self.engine.stop()
    def reset(self):
        state=self.engine.reset()
        self.engine.start()
        return self.engine.snapshot()
    def exposure(self, body):
        f=self.engine._state.flood
        f.people_count,f.vehicle_count=body.people_count,body.vehicle_count
        if f.exposure_remaining is not None: f.exposure_remaining = float(body.people_count)
        self.engine.flood_risk.update(f)
        return self.engine._touch()
