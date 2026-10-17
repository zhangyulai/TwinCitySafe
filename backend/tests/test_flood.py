import asyncio
from copy import deepcopy
import httpx
import pytest
from sqlalchemy import select, func
from app.main import app
from app.schemas.flood import FloodScenarioRequest, FloodSimulationState
from app.services.flood_service import FloodService
from app.services.flood_risk_service import FloodRiskService
from app.services.flood_forecast_service import FloodForecastService
from app.services.flood_storage_service import FloodStorageService
from app.models import Device, DeviceTelemetry
from app.models.flood import FloodScenarioRecord, FloodSnapshot
from app.services.pipeline_seed import seed_pipelines
from app.models.pipeline import PipelineEdge
from simulator.engine import SimulationEngine
from simulator import flood_config as cfg

def scenario(kind="extreme_rain",linked=True):
    e=SimulationEngine();FloodService(e).start(FloodScenarioRequest(scenario=kind),linked);e.set_speed(10);return e

def advance(e,seconds):
    for _ in range(int(seconds/10)):e.tick()
    return e.snapshot()

def test_normal_rain_pumping_no_sustained_rise():
    e=scenario("normal",False);initial=e.snapshot().flood.water_level
    state=advance(e,600)
    assert state.flood.water_level<=initial and state.flood.flood_volume>=0
    dry=scenario("normal",False)
    for _ in range(120):
        previous=dry._state.flood.water_level
        dry.flood.tick_scenario(dry._state.flood,dry._state.environment,0,dry._state.devices,5)
        assert 0<=dry._state.flood.water_level<=previous

def test_heavy_normal_vs_extreme_degraded():
    heavy=scenario("heavy_rain",False);extreme=scenario()
    h=advance(heavy,1800);x=advance(extreme,1800)
    assert x.flood.water_level>h.flood.water_level>0
    assert x.flood.water_level>25 and x.flood.risk_score>=80
    assert x.devices[2].fault=="bearing_degradation" and x.devices[2].efficiency==pytest.approx(76,abs=.05)
    assert x.flood.status=="completed" and not x.running
    before=x.model_dump();after=extreme.tick().model_dump()
    for key in ("revision","timestamp"):before.pop(key);after.pop(key)
    assert before==after

def test_manual_fault_true_device_dependency():
    normal=scenario(linked=False);bad=scenario(linked=False)
    bad.set_fault("P03","bearing_degradation")
    n=advance(normal,1200);b=advance(bad,1200)
    assert b.flood.water_level>n.flood.water_level
    assert b.flood.effective_pump_capacity==pytest.approx(120/3600*b.devices[2].efficiency/100)

def test_backup_pumps_and_offline_capacity():
    e=scenario();advance(e,400);base=e.snapshot().flood.effective_pump_capacity
    e.set_device_state("P01","running");e.set_device_state("P02","running")
    state=advance(e,120);assert state.flood.effective_pump_capacity>base*2
    e.set_device_state("P03","offline");state=e.tick()
    expected=sum(120/3600*d.efficiency/100 for d in state.devices if d.status in ("running","warning"))
    assert state.flood.effective_pump_capacity==pytest.approx(expected)

def test_conservation_and_bounds():
    e=scenario()
    for _ in range(100):
        before=e.snapshot().flood.flood_volume
        # Isolated direct physics step with fixed rainfall/pump values validates units exactly.
        f=e._state.flood
        e.flood.tick_scenario(f,e._state.environment,100,e._state.devices,1)
        expected=before+(f.surface_inflow-f.outflow)
        assert f.flood_volume==pytest.approx(expected)
        assert f.surface_inflow==pytest.approx(100/1000/3600*12000*.85)
        FloodRiskService.update(f)
        assert f.flood_volume>=0 and f.water_level>=0 and 0<=f.water_area<=1500 and f.effective_pump_capacity>=0 and 0<=f.risk_score<=100
    e._state.flood.flood_volume=0
    e.flood.tick_scenario(e._state.flood,e._state.environment,0,e._state.devices,100)
    assert e._state.flood.flood_volume==0 and e._state.flood.outflow==0

def test_forecast_has_no_side_effects_and_matches_rollout():
    e=scenario();advance(e,300)
    before=e.snapshot().model_dump();internals=(deepcopy(e.devices.__dict__),list(e.flood.history),e.weather.rainfall_target)
    result=FloodForecastService.forecast(e,[10,20,30])
    assert e.snapshot().model_dump()==before
    assert (e.devices.__dict__,list(e.flood.history),e.weather.rainfall_target)==internals
    actual=advance(e,600)
    assert result.points[0].water_level==pytest.approx(actual.flood.water_level,abs=.12)
    assert result.points[-1].water_level>result.current.water_level

def test_forecast_higher_rain_lower_drainage_is_worse():
    a=scenario();advance(a,400)
    low=FloodForecastService.forecast(a,[30]).points[0].water_level
    a.set_device_state("P01","running");a.set_device_state("P02","running")
    high_capacity=FloodForecastService.forecast(a,[30]).points[0].water_level
    assert high_capacity<low

def test_risk_monotonic_and_breakdown():
    state=FloodSimulationState(rainfall=85,effective_pump_capacity=.025,growth_rate=.8,people_count=32,vehicle_count=48)
    scores=[]
    for level in (0,3,8,15,25,40):
        state.water_level=level;FloodRiskService.update(state);scores.append(state.risk_score)
        assert sum(x.points for x in state.risk_breakdown.factors)==pytest.approx(state.risk_score)
        assert sum(x.contribution for x in state.risk_breakdown.factors)==pytest.approx(100)
    assert scores==sorted(scores)
    prior=state.risk_score;state.people_count=0;state.vehicle_count=0;FloodRiskService.update(state);assert state.risk_score<prior

def test_growth_uses_window_and_nonlinear_area():
    e=scenario();e.flood.history.clear()
    e.flood.history.extend([(i,2+i*.01) for i in range(61)])
    assert e.flood.growth_rate(60)==pytest.approx(.6)
    f=e._state.flood;ratios=[]
    for cm in (1,4,16):
        f.flood_volume=cm/100*1500;e.flood.tick_scenario(f,e._state.environment,0,e._state.devices,0);ratios.append(f.water_area/cm)
    assert ratios[0]>ratios[1]>ratios[2]

def test_stop_resume_and_reset_keep_assets(isolated_storage):
    e=scenario();advance(e,600);s=FloodService(e)
    s.stop();before=e.snapshot();after=e.tick();assert before.flood==after.flood and before.weather==after.weather
    e.start();assert e.tick().flood.elapsed_simulation_seconds>before.flood.elapsed_simulation_seconds
    with isolated_storage() as db:
        seed_pipelines(db);count=db.scalar(select(func.count()).select_from(PipelineEdge))
    state=s.reset()
    assert state.flood.scenario_id is None and state.environment.b2_water_level==.8 and state.devices[2].fault=="normal"
    with isolated_storage() as db:assert db.scalar(select(func.count()).select_from(PipelineEdge))==count

def test_snapshot_alarm_dedup_and_persistence(isolated_storage):
    async def exercise():
        e=scenario();s=FloodStorageService(e,isolated_storage)
        first=advance(e,600);alarm_id=first.flood.alarm.id
        await s.sample();await s.sample()
        advance(e,600);await s.sample()
        with isolated_storage() as db:
            assert db.scalar(select(func.count()).select_from(FloodScenarioRecord))==1
            assert db.scalar(select(func.count()).select_from(FloodSnapshot))==2
            item=db.get(FloodScenarioRecord,first.flood.scenario_id)
            assert item.alarm["id"]==alarm_id and item.alarm["level"]=="major"
        e.stop();await s.archive(reset=True)
        with isolated_storage() as db:assert db.get(FloodScenarioRecord,first.flood.scenario_id).alarm["status"]=="ended_by_reset"
    asyncio.run(exercise())

def test_flood_api_and_forecast(isolated_storage,monkeypatch):
    async def exercise():
        with isolated_storage() as db:
            db.get(Device,"P03").rated_capacity=240;db.commit()
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
                response=await c.post('/api/v1/simulation/flood/start',json={"scenario":"extreme_rain","duration_minutes":30})
                assert response.status_code==200
                f=response.json()['flood'];assert f['effectivePumpCapacity']==pytest.approx(240/3600*.96)
                id=f['scenarioId']
                forecast=await c.get('/api/v1/simulation/flood/forecast?horizons=10,20,30');assert forecast.status_code==200 and len(forecast.json()['points'])==3
                assert (await c.get('/api/v1/simulation/flood/forecast?horizons=-1,NaN')).status_code==422
                assert (await c.post('/api/v1/simulation/flood/start',json={'scenario':'fake'})).status_code==422
                assert (await c.post('/api/v1/simulation/flood/exposure',json={'peopleCount':-1,'vehicleCount':2})).status_code==422
                assert (await c.post('/api/v1/simulation/flood/stop')).json()['flood']['status']=='stopped'
                assert (await c.get('/api/v1/simulation/flood/snapshots/'+id)).json()['total']>=1
                assert (await c.post('/api/v1/simulation/flood/reset')).json()['flood']['scenarioId'] is None
                from app.core.config import get_settings
                monkeypatch.setattr(get_settings(),'app_env','production')
                assert (await c.post('/api/v1/simulation/flood/start',json={'scenario':'normal'})).status_code==404
                assert (await c.post('/api/v1/simulation/flood/demo-start')).status_code==200
                await c.post('/api/v1/simulation/flood/reset')
    asyncio.run(exercise())


def test_noninteger_wall_ticks_end_at_exact_duration():
    e=scenario()
    for i in range(220):
        state=e.tick(1.013+(i%7)*.001)
        if not state.running:break
    assert state.flood.status=="completed"
    assert state.flood.elapsed_simulation_seconds==1800
