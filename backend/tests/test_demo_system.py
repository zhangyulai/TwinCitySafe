"""M10 checks use isolated SQLite and the real existing simulation; never live PostgreSQL."""
import asyncio
from datetime import UTC, datetime
from functools import wraps
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError
from app.main import app
from app.core.config import get_settings
from app.models.incident import Incident, IncidentTimelineEvent, IncidentSnapshot
from app.models.pipeline import Valve
from app.services.demo_service import DemoService
from app.services.pipeline_seed import seed_pipelines
from app.services.pipeline_graph_service import PipelineGraphService
from app.services.readiness_service import system_readiness
from app.services.realtime_service import RealtimeService


def async_test(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return run


def prepared(factory):
    with factory() as db:
        seed_pipelines(db)
        graph = PipelineGraphService(db).graph
    rt = RealtimeService()
    rt.engine.configure_pipelines(graph)
    return rt


def archives(factory):
    with factory() as db:
        return {model.__tablename__: db.scalar(select(func.count()).select_from(model))
                for model in (Incident, IncidentTimelineEvent, IncidentSnapshot)}


@async_test
async def test_readiness_is_read_only_and_reports_real_publisher_and_models(isolated_storage):
    rt = prepared(isolated_storage)
    rt.engine.stop()
    rt.engine.launch(rt.publish)
    before = rt.engine.snapshot()
    counts = archives(isolated_storage)
    try:
        result = system_readiness(rt)
        assert result['ready'] and result['core_ready'] and not result['degraded']
        assert result['pipeline_graph']['edge_count'] == 32
        assert result['pipeline_graph']['node_count'] == 34
        assert result['pipeline_graph']['valve_count'] == 10
        assert result['risk_model']['model_count'] == 6
        assert result['websocket']['active_connections'] == 0
        assert result['websocket']['publisher_running']
        assert rt.engine.snapshot() == before and archives(isolated_storage) == counts
    finally:
        await rt.engine.shutdown()


@async_test
async def test_models_unavailable_degrades_without_disabling_physical_demo(isolated_storage):
    rt = prepared(isolated_storage)
    rt.engine.launch(rt.publish)
    rt.risk.models.models = {}
    rt.operation.anomaly.artifact = None
    try:
        result = system_readiness(rt)
        assert not result['ready'] and result['core_ready'] and result['degraded']
        assert not result['risk_model']['available'] and not result['anomaly_model']['available']
        state = await DemoService(rt).start('flood')
        assert state.flood.scenario_id and state.flood.rainfall_recession and state.speed == 10
        rt.engine.tick(1)
        assert rt.engine.snapshot().flood.water_level >= 0
    finally:
        await rt.engine.shutdown()


def test_storage_outage_and_missing_runtime_report_components_not_credentials(isolated_storage):
    rt = prepared(isolated_storage)
    rt.telemetry.session_factory = lambda: (_ for _ in ()).throw(OperationalError('secret-db-url', {}, None))
    result = system_readiness(rt)
    assert not result['database']['available'] and not result['core_ready']
    assert 'secret-db-url' not in str(result)
    cold = system_readiness(None)
    assert cold['backend']['available'] and not cold['websocket']['available']


@async_test
async def test_demo_reset_recovers_physical_state_and_preserves_archives(isolated_storage):
    rt = prepared(isolated_storage)
    with isolated_storage() as db:
        db.add(Incident(id='closed-history', incident_code='HISTORY', incident_type='FLOOD', source_event_id='past',
            scenario_id='past', title='Saved closed incident', status='CLOSED', closed_at=datetime.now(UTC)))
        for valve in db.scalars(select(Valve)):
            valve.status='closed'; valve.open_percentage=0
        db.commit()
    engine=rt.engine
    engine.set_fault('P03', 'bearing_degradation')
    engine.set_weather('rain')
    engine.set_device_state('P01', 'running')
    engine._state.flood.entrance_closed=True
    engine.set_speed(10)
    before=archives(isolated_storage)
    state=await DemoService(rt).reset()
    assert state.running and state.speed == 1 and state.simulation_time == 0
    assert not state.flood.scenario_id and not state.leak.scenario_id and not state.emergency
    assert state.weather.condition == 'clear' and state.weather.rainfall == 0
    assert not state.flood.entrance_closed
    assert [d.status for d in state.devices] == ['standby','standby','running']
    assert all(d.fault == 'normal' for d in state.devices)
    assert len(state.valves) == 10 and all(v.status == 'open' for v in state.valves)
    assert not engine.pipelines.isolated
    assert archives(isolated_storage) == before
    with isolated_storage() as db:
        assert db.get(Incident,'closed-history').status == 'CLOSED'
        assert all(v.status == 'open' and v.open_percentage == 100 for v in db.scalars(select(Valve)))
    await DemoService(rt).reset()
    assert archives(isolated_storage) == before


@async_test
@pytest.mark.parametrize('scenario', ['flood','leak'])
async def test_demo_start_conflict_and_reset_archive_interruption(isolated_storage, scenario):
    rt=prepared(isolated_storage)
    demo=DemoService(rt)
    state=await demo.start(scenario)
    identity=rt.incidents.identity(state)
    assert state.speed == 10 and state.running and identity
    if scenario == 'flood':
        assert state.flood.duration_minutes == 60 and state.flood.rainfall_recession and state.flood.auto_fault
    else:
        assert state.leak.target_pipeline_id == 'WS-003'
    before=rt.engine.snapshot()
    with pytest.raises(HTTPException) as failure:
        await demo.start('leak' if scenario == 'flood' else 'flood')
    assert failure.value.status_code == 409 and rt.engine.snapshot() == before
    rt.engine.tick(1)
    await demo.reset()
    with isolated_storage() as db:
        incident=db.scalar(select(Incident).where(Incident.source_event_id == identity[1]))
        assert incident.status == 'ABORTED'
        assert db.scalar(select(func.count()).select_from(IncidentSnapshot).where(IncidentSnapshot.incident_id == incident.id)) > 0
    next_state=await demo.start('leak' if scenario == 'flood' else 'flood')
    assert rt.incidents.identity(next_state) != identity


@async_test
async def test_reset_database_outage_preserves_current_state(isolated_storage, monkeypatch):
    rt=prepared(isolated_storage)
    before=rt.engine.snapshot()
    demo=DemoService(rt)
    def unavailable():
        raise OperationalError('secret', {}, None)
    monkeypatch.setattr(demo,'inspect_assets',unavailable)
    with pytest.raises(HTTPException) as failure:
        await demo.reset()
    assert failure.value.status_code == 503 and rt.engine.snapshot() == before


@async_test
async def test_demo_api_confirmation_production_gate_and_dev_controls_stay_disabled(isolated_storage, monkeypatch):
    with isolated_storage() as db:seed_pipelines(db)
    settings=get_settings()
    monkeypatch.setattr(settings,'app_env','production')
    monkeypatch.setattr(settings,'demo_mode',False)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.post('/api/v1/demo/reset',json={'confirmed':True})).status_code == 404
            monkeypatch.setattr(settings,'demo_mode',True)
            assert (await client.post('/api/v1/demo/reset',json={'confirmed':False})).status_code == 422
            assert (await client.post('/api/v1/demo/reset',json={'confirmed':'true'})).status_code == 422
            assert (await client.post('/api/v1/demo/start',json={'scenario':'new','confirmed':True})).status_code == 422
            result=await client.post('/api/v1/demo/start',json={'scenario':'flood','confirmed':True})
            assert result.status_code == 200
            state=result.json()
            assert state['flood']['scenarioId'] and state['speed'] == 10 and 'state' not in state
            assert (await client.post('/api/v1/demo/pause')).json()['running'] is False
            assert (await client.post('/api/v1/demo/speed',json={'speed':5})).json()['speed'] == 5
            assert (await client.post('/api/v1/demo/speed',json={'speed':3})).status_code == 422
            assert (await client.post('/api/v1/demo/resume')).json()['running'] is True
            assert (await client.post('/api/v1/simulation/valve/V-W-03/state',json={'status':'closed'})).status_code == 404
            assert (await client.post('/api/v1/simulation/flood/start',json={'scenario':'extreme_rain'})).status_code == 404
            assert (await client.get('/api/v1/system/readiness')).json()['demo_enabled']
            assert (await client.post('/api/v1/demo/reset',json={'confirmed':True})).status_code == 200


@async_test
@pytest.mark.parametrize('scenario', ['flood', 'leak'])
async def test_production_demo_allows_human_comparison_execution_and_close(isolated_storage, monkeypatch, scenario):
    with isolated_storage() as db:seed_pipelines(db)
    settings=get_settings()
    monkeypatch.setattr(settings,'app_env','production')
    monkeypatch.setattr(settings,'demo_mode',True)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.post('/api/v1/demo/start',json={'scenario':scenario,'confirmed':True})
            assert response.status_code == 200
            rt=app.state.realtime
            # Real deterministic integrations on the isolated engine, no state shortcuts.
            for _ in range(174 if scenario=='flood' else 60):rt.engine.tick(1)
            await client.post('/api/v1/demo/pause')
            if scenario=='flood':
                assert rt.engine._state.flood.risk_score>=60
                comparison=await client.post('/api/v1/emergency/compare',json={'plan_codes':['FLOOD-B'],'horizon_minutes':30})
                assert comparison.status_code==200
                body={'plan_code':'FLOOD-B','comparison_id':comparison.json()['id'],'confirmed_simulation':True}
                execution=await client.post('/api/v1/emergency/execute',json=body)
            else:
                assert rt.engine._state.leak.confirmed_at
                comparison=await client.post('/api/v1/pipeline-leak/isolation/compare',json={'pipeline_id':'WS-003'})
                assert comparison.status_code==200
                option=next(x for x in comparison.json()['options'] if x['valves']==['V-W-03'])
                body={'comparison_id':comparison.json()['id'],'option_id':option['id'],'confirmed_simulation':True}
                execution=await client.post('/api/v1/pipeline-leak/isolation/execute',json=body)
            assert execution.status_code==200, execution.text
            await client.post('/api/v1/demo/resume')
            for _ in range(80 if scenario=='flood' else 35):rt.engine.tick(1)
            await client.post('/api/v1/demo/pause')
            await rt.flood_storage.sample()
            await rt.leak.sample()
            rt.publish(rt.engine.snapshot())
            await rt.emergency.flush()
            await rt.incidents.flush(strict=True)
            with isolated_storage() as db:
                incident=db.scalar(select(Incident).where(Incident.scenario_id == (
                    rt.engine._state.flood.scenario_id if scenario=='flood' else rt.engine._state.leak.scenario_id)))
                assert incident.status=='STABILIZING'
                incident_id=incident.id
            closed=await client.post(f'/api/v1/incidents/{incident_id}/close',json={
                'confirmed':True,'operator':'demo-user','result':'人工确认软件演示已稳定；保留处置与服务影响'})
            assert closed.status_code==200 and closed.json()['status']=='CLOSED'
            assert not rt.engine._state.running


def test_explicit_missing_model_paths_use_real_file_failure(isolated_storage, monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, 'anomaly_model_path', str(tmp_path / 'missing-device.joblib'))
    monkeypatch.setattr(settings, 'risk_model_dir', str(tmp_path / 'empty-risk-models'))
    rt = prepared(isolated_storage)
    assert not rt.operation.anomaly.available and not rt.risk.models.available
    assert len(rt.risk.models.models) == 0
    assert rt.engine.snapshot().devices and rt.engine.pipelines.graph.edges
