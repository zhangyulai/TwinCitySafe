from app.schemas.flood import FloodForecast, FloodForecastPoint

class FloodForecastService:
    @staticmethod
    def forecast(engine, horizons):
        from algorithm.risk_prediction.simulation import SimulationCopy
        frame = SimulationCopy(engine)
        state=frame._state; f=state.flood
        original_time=state.simulation_time
        if f.scenario_id is None:frame.flood.reset_history(0,f.water_level)
        def point(minute):return FloodForecastPoint(minute=minute,water_level=f.water_level,water_area=f.water_area,risk_score=f.risk_score,risk_level=f.risk_level)
        current=point(0);points=[];elapsed=0
        for minute in horizons:
            while elapsed<minute*60:
                dt=min(5.0,minute*60-elapsed)
                frame.step(dt);elapsed+=dt
            points.append(point(minute))
        return FloodForecast(scenario_id=f.scenario_id,based_on_revision=state.revision,simulation_time=original_time,current=current,points=points)
