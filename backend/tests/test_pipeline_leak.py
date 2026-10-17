"""M8 observation-based diagnosis, shared valve control and persistent software isolation."""
import asyncio
from functools import wraps
from copy import deepcopy
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.main import app
from app.services.pipeline_seed import seed_pipelines
from app.services.pipeline_leak_service import PipelineLeakService
from app.services.leak_detection_service import LeakLocalizationService
from app.services.valve_service import ValveService
from app.services.flood_service import FloodService
from app.schemas.leak import LeakStart, IsolationExecute
from app.schemas.flood import FloodScenarioRequest
from app.models.leak import PipelineLeakEvent, PipelineLeakSnapshot, PipelineLeakIsolation
from app.websocket.manager import ConnectionManager
from simulator.engine import SimulationEngine


def async_test(fn):
    @wraps(fn)
    def run(*args, **kwargs): return asyncio.run(fn(*args, **kwargs))
    return run

async def setup(factory, target="WS-003", severity=.75):
    with factory() as db: seed_pipelines(db)
    e=SimulationEngine();s=PipelineLeakService(e,factory,ConnectionManager())
    await s.start_scenario(LeakStart(pipeline_id=target,severity=severity));e.set_speed(10)
    return e,s

def advance(e, seconds=600):
    for _ in range(int(seconds/10)): e.tick(1)

def execute_body(c,confirmed=True):
    return IsolationExecute(comparison_id=c['id'],option_id=c['options'][0]['id'],confirmed_simulation=confirmed)

@async_test
async def test_zero_leak_normal_noise_and_gradual_ramp(isolated_storage):
    e,s=await setup(isolated_storage,severity=0);advance(e)
    assert e._state.leak.detection_score<.35 and not e._state.leak.suspected_segments
    assert not e._state.leak.alarm and e._state.leak.risk_score==0
    await s.reset();await s.start_scenario(LeakStart());e.set_speed(10)
    pressure=[];severity=[]
    for _ in range(60):
        e.tick(1);pressure.append(next(p.pressure for p in e._state.pipelines if p.id=='WS-003'));severity.append(e._state.leak.leak_severity)
    assert severity==sorted(severity) and severity[-1]==.75
    assert max(abs(a-b) for a,b in zip(pressure,pressure[1:]))<.02
    assert pressure[-1]<pressure[0] and e._state.leak.confirmed_at

@pytest.mark.parametrize('target',['WS-003','WS-004','WS-001','WS-007'])
@async_test
async def test_localization_multiple_targets_without_injected_truth(isolated_storage,target):
    e,s=await setup(isolated_storage,target);advance(e)
    ranking=LeakLocalizationService.rank(e._state.pipelines,s.baseline,e.pipelines.graph)
    assert ranking[0]['pipeline_id']==target and len(ranking)==3
    e._state.leak.target_pipeline_id='NOT_AN_ASSET';e._state.leak.leak_severity=0
    assert LeakLocalizationService.rank(e._state.pipelines,s.baseline,e.pipelines.graph)==ranking
    assert all(0<=r['score']<=1 for r in ranking)
    assert e._state.leak.affected_buildings==s.graph_service.get_affected_buildings(target)

@async_test
async def test_compare_is_readonly_and_uses_m4_options(isolated_storage):
    e,s=await setup(isolated_storage);advance(e);e.stop();before=e.snapshot()
    c=await s.compare('WS-003')
    assert e.snapshot()==before
    assert [x['valves'] for x in c['options']]==[['V-W-03'],['V-W-02'],['V-W-01']]
    assert [len(x['affectedBuildings']) for x in c['options']]==[2,4,5]
    assert [x['estimatedServiceLoss'] for x in c['options']]==[.4,.8,1]
    with isolated_storage() as db: assert db.get(PipelineLeakIsolation,c['id']).state_hash==c['stateHash']
    with pytest.raises(HTTPException) as exc:await s.execute(execute_body(c,False))
    assert exc.value.status_code==422 and not e._state.leak.execution

@async_test
async def test_isolation_decay_persistence_reopen_and_reset(isolated_storage):
    e,s=await setup(isolated_storage);advance(e);c=await s.compare('WS-003');before=e.snapshot()
    await s.execute(execute_body(c));f=e._state.leak
    assert f.risk_score==before.leak.risk_score and f.estimated_leak_flow==before.leak.estimated_leak_flow
    e.set_speed(1);e.tick(.25)
    assert 0<f.estimated_leak_flow<before.leak.estimated_leak_flow
    e.set_speed(10);advance(e,300)
    assert f.current_stage=='STABILIZING' and f.leak_status=='CONTAINED'
    assert f.risk_score<before.leak.risk_score and f.risk_score>=6
    assert len(f.interrupted_buildings)==2 and f.service_status=='INTERRUPTED'
    assert f.alarm['id']==before.leak.alarm['id'] and f.alarm['status']=='active'
    await asyncio.gather(s.sample(),s.sample())
    with isolated_storage() as db:
        assert len(list(db.scalars(select(PipelineLeakEvent))))==1
        assert len(list(db.scalars(select(PipelineLeakSnapshot))))==2
        assert db.get(PipelineLeakIsolation,c['id']).execution_json['valves']==['V-W-03']
        graph=ValveService.apply(db,{'V-W-03':'open'});db.commit()
    e.configure_pipelines(graph);advance(e,300)
    assert f.leak_status=='DETECTED' and f.current_stage in ('CONFIRMED','HIGH') and f.estimated_leak_flow>10
    assert not f.interrupted_buildings
    await s.reset()
    assert not e._state.leak.scenario_id and len(e._state.pipelines)==32
    with isolated_storage() as db:
        assert db.scalar(select(PipelineLeakEvent)).status=='reset'
        assert s.load_graph().graph.valves['V-W-03'].status=='open'

@pytest.mark.parametrize('change',['time','pressure','flow','suspect','valve','graph','scenario'])
@async_test
async def test_stale_comparison_rejected_without_actuation(isolated_storage,change):
    e,s=await setup(isolated_storage);advance(e);c=await s.compare('WS-003');g=s.load_graph().graph
    if change=='time':e._state.leak.elapsed_simulation_seconds+=61
    if change=='pressure':next(p for p in e._state.pipelines if p.id=='WS-003').pressure+=.1
    if change=='flow':next(p for p in e._state.pipelines if p.id=='WS-003').flow+=6
    if change=='suspect':e._state.leak.suspected_segments[0]['pipeline_id']='WS-004'
    if change=='scenario':e._state.leak.scenario_id='different'
    if change=='valve':
        with isolated_storage() as db:g=ValveService.apply(db,{'V-W-02':'closed'});db.commit()
    if change=='graph':
        from dataclasses import replace
        g.edges['WS-003']=replace(g.edges['WS-003'],weight=g.edges['WS-003'].weight+1)
    with pytest.raises(HTTPException) as exc:s.validate_comparison(c,g)
    assert exc.value.detail['code']=='STALE_ISOLATION' and not e._state.leak.execution

@async_test
async def test_conflicts_both_directions_and_non_water_target(isolated_storage):
    e,s=await setup(isolated_storage);e.stop()
    with pytest.raises(HTTPException) as exc:FloodService(e).start(FloodScenarioRequest(scenario='extreme_rain'),linked=True)
    assert exc.value.status_code==409
    await s.reset();FloodService(e).start(FloodScenarioRequest(scenario='extreme_rain'),linked=True);e.stop()
    with pytest.raises(HTTPException) as exc:await s.start_scenario(LeakStart())
    assert exc.value.status_code==409
    e.reset()
    with pytest.raises(HTTPException) as exc:await s.start_scenario(LeakStart(pipeline_id='DS-001'))
    assert exc.value.status_code==422

@async_test
async def test_storage_failure_does_not_close_valves(isolated_storage,monkeypatch):
    e,s=await setup(isolated_storage);advance(e);c=await s.compare('WS-003')
    with isolated_storage() as db:db.delete(db.get(PipelineLeakIsolation,c['id']));db.commit()
    with pytest.raises(HTTPException):await s.execute(execute_body(c))
    assert not e._state.leak.execution and s.load_graph().graph.valves['V-W-03'].status=='open'
    original=s.persist
    def failure(*args):raise RuntimeError('offline')
    monkeypatch.setattr(s,'persist',failure);await s.sample()
    assert not s.storage_available and len(s.pending)==1
    monkeypatch.setattr(s,'persist',original);await s.sample();assert s.storage_available and not s.pending

@async_test
async def test_event_buffer_sequences_and_restart_history(isolated_storage):
    e,s=await setup(isolated_storage);advance(e)
    for i in range(250):s.event(e._state,str(i))
    assert len(e._state.leak.events)==200
    assert e._state.leak.events[-1]['sequence']>250
    await s.sample();replacement=PipelineLeakService(SimulationEngine(),isolated_storage,ConnectionManager())
    await replacement.startup();await replacement.shutdown()
    with isolated_storage() as db:assert db.scalar(select(PipelineLeakEvent)).status=='interrupted'
    assert not replacement.engine._state.leak.scenario_id

@async_test
async def test_leak_api_validation_and_ml_separation(isolated_storage):
    with isolated_storage() as db:seed_pipelines(db)
    async with app.router.lifespan_context(app),httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test/api/v1') as c:
        assert (await c.post('/simulation/pipeline-leak/start',json={'severity':2})).status_code==422
        assert (await c.post('/simulation/pipeline-leak/start',json={})).status_code==200
        assert (await c.post('/simulation/flood/start',json={'scenario':'extreme_rain'})).status_code==409
        assert (await c.post('/pipeline-leak/isolation/compare',json={'pipeline_id':'WS-003'})).status_code==409
        assert (await c.get('/pipeline-leak/localization')).json()['suspects']==[]
        assert (await c.get('/pipeline-leak/risk')).json()['riskScore']==0
        assert (await c.post('/simulation/pipeline-leak/stop')).status_code==200
        assert (await c.get('/simulation/pipeline-leak/status')).json()['status']=='stopped'
        assert (await c.post('/simulation/pipeline-leak/reset')).status_code==200


@async_test
async def test_paused_speed_change_preserves_leak_status_and_observations(isolated_storage):
    e,s=await setup(isolated_storage);advance(e,300);e.stop();before=e.snapshot()
    e.set_speed(5);e.tick(1)
    assert not e._state.running and e._state.leak.status=='stopped'
    assert e._state.leak==before.leak and e._state.pipelines==before.pipelines
    e.start();e.tick(1)
    assert e._state.leak.status=='running' and e._state.leak.elapsed_simulation_seconds>before.leak.elapsed_simulation_seconds

@async_test
async def test_severity_controls_pressure_flow_detection_and_risk(isolated_storage):
    values=[]
    for severity in [0,.2,.5,.75,1]:
        e,s=await setup(isolated_storage,severity=severity);advance(e)
        f=e._state.leak;p=next(p for p in e._state.pipelines if p.id=='WS-003')
        values.append((p.pressure,p.inlet_flow-p.outlet_flow,f.detection_score,f.risk_score))
        assert all(p.pressure>=0 and p.flow>=0 for p in e._state.pipelines)
        assert 0<=f.detection_score<=1 and 0<=f.risk_score<=100
        await s.reset()
    assert [x[0] for x in values]==sorted([x[0] for x in values],reverse=True)
    for i in [1,2,3]:assert [x[i] for x in values]==sorted(x[i] for x in values)
