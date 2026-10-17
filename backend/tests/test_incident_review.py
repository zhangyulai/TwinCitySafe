"""M9 archival contracts, using isolated SQLite only (never the demo PostgreSQL).

Fixtures intentionally contain inconsistent terminal summary peaks and missing legacy
fields. Replay must preserve what each historical row actually recorded.
"""
import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from functools import wraps

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.main import app
from app.models.flood import FloodScenarioRecord, FloodSnapshot
from app.models.leak import PipelineLeakEvent, PipelineLeakIsolation, PipelineLeakSnapshot
from app.models.emergency import EmergencyComparison, EmergencyExecution
from app.models.risk_prediction import RiskPredictionRecord
from app.models.pipeline import Valve
from app.services.pipeline_seed import seed_pipelines
from app.services.flood_service import FloodService
from app.schemas.flood import FloodScenarioRequest
from simulator.engine import SimulationEngine

T0 = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)
FLOOD_ID = "test-m9-flood"
LEAK_ID = "test-m9-leak"


def async_test(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return run


def stamp(seconds):
    return T0 + timedelta(seconds=seconds)


def seed_sources(factory, *, flood_status="running", leak_status="STABILIZING", emergency=False):
    """Two documented source histories, not generated replay frames."""
    with factory() as db:
        seed_pipelines(db)
        db.add(FloodScenarioRecord(
            id=FLOOD_ID, scenario="extreme_rain", status="stopped" if flood_status=="reset" else flood_status,
            started_at=T0, simulation_started_at=0, elapsed_simulation_seconds=600,
            duration_minutes=30, people_count=32, vehicle_count=48, auto_fault=True,
            current_stage="HIGH", peak_water_level=99, peak_risk=99,
            alarm={"id": "flood-alarm", "status": "ended_by_reset" if flood_status=="reset" else "active"}, updated_at=stamp(600),
        ))
        for t, water, rain, risk, pump in [(0,1,5,5,.03),(30,2,20,25,.03),
                                           (60,10,100,65,.023),(300,20,100,75,.023),
                                           (600,15,20,35,.09)]:
            db.add(FloodSnapshot(scenario_id=FLOOD_ID, timestamp=stamp(t), simulation_time=t,
                rainfall=rain, water_level=water, water_area=water*50, inflow=.2,
                outflow=pump, pump_capacity=pump, risk_score=risk,
                stage="HIGH" if risk>=60 else "LOW"))
        events=[]
        for seq,t,stage,message in [(1,0,"NORMAL","管网泄漏软件场景启动"),
                                    (2,30,"SUSPECTED","管网泄漏疑似异常"),
                                    (3,60,"CONFIRMED","管网泄漏确认"),
                                    (4,300,"ISOLATING","阀门关闭，隔离执行"),
                                    (5,600,"STABILIZING","泄漏受控，风险稳定，供水仍中断")]:
            events.append(dict(sequence=seq,timestamp=stamp(t).isoformat(),simulationTime=t,stage=stage,message=message))
        buildings=[{"buildingId":"B-RESEARCH","buildingName":"科研楼 B"},
                   {"buildingId":"C-LAB","buildingName":"实验楼 C"}]
        db.add(PipelineLeakEvent(id="event-m9-leak",scenario_id=LEAK_ID,pipeline_id="WS-003",
            detected_at=stamp(30),confirmed_at=stamp(60),peak_detection_score=.99,peak_risk=99,
            status=leak_status,state_json={"scenarioId":LEAK_ID,"eventId":"event-m9-leak",
                "scenarioType":"WATER_SUPPLY_LEAK","elapsedSimulationSeconds":600,
                "currentStage":"STABILIZING","leakStatus":"CONTAINED","serviceStatus":"INTERRUPTED",
                "riskScore":6,"estimatedLeakFlow":0,"pipelineFlow":0,"downstreamPressure":0,
                "suspectedSegments":[{"pipeline_id":"WS-003","score":.9}],
                "affectedBuildings":buildings,"interruptedBuildings":buildings,
                "valves":[{"id":"V-W-03","status":"closed"}],"events":events,
                "execution":{"id":"leak-execution","valves":["V-W-03"],"status":"applied"}}))
        for t,p,q,score,risk in [(0,.42,28,0,0),(30,.4,30,.36,20),(60,.3,45,.62,55),
                                (300,.22,50,.76,68),(600,0,0,0,6)]:
            db.add(PipelineLeakSnapshot(scenario_id=LEAK_ID,timestamp=stamp(t),simulation_time=t,
                pipeline_id="WS-003" if t>=60 else None,pressure=p,flow=q,
                leak_severity=.75 if t>=300 else .2,detection_score=score,risk_score=risk,
                top_suspects=[{"pipeline_id":"WS-003","score":.8}] if t>=60 else [],
                affected_count=2 if t>=60 else 0))
        db.add(PipelineLeakIsolation(id="m9-isolation",scenario_id=LEAK_ID,state_hash="a"*64,
            created_at=stamp(290),comparison_json={"id":"m9-isolation","scenarioId":LEAK_ID,
                "pipelineId":"WS-003","simulationTime":290,"comparedAt":stamp(290).isoformat(),
                "options":[{"id":"option-1","valves":["V-W-03"],"affectedBuildings":buildings}]},
            execution_json={"id":"leak-execution","comparisonId":"m9-isolation","optionId":"option-1",
                "valves":["V-W-03"],"status":"applied","timestamp":stamp(300).isoformat(),
                "affectedBuildings":buildings}))
        if emergency:
            comparison={"id":"m9-flood-comparison","scenario_id":FLOOD_ID,
                "baseline_simulation_time":300,"compared_at":stamp(300).isoformat(),
                "baseline":{"timeline":[{"risk_score":75,"water_level":20}]},
                "plans":{},"results":[]}
            db.add(EmergencyComparison(id=comparison['id'],scenario_id=FLOOD_ID,
                baseline_state_hash="b"*64,compared_at=stamp(300),horizon=30,results_json=comparison))
            execution={"id":"m9-flood-execution","scenario_id":FLOOD_ID,"plan_code":"FLOOD-B",
                "plan_name":"双泵排水","comparison_id":comparison['id'],"operator":"demo-user",
                "status":"completed","phase":"STABILIZING","started_at":stamp(305).isoformat(),
                "simulation_started_at":305,"initial_risk":75,"steps":[],
                "events":[{"sequence":1,"timestamp":stamp(305).isoformat(),"simulation_time":305,
                           "message":"FLOOD-B 已选择并确认","status":"pending","step":None},
                          {"sequence":2,"timestamp":stamp(600).isoformat(),"simulation_time":600,
                           "message":"风险回落，进入稳定阶段","status":"stabilizing","step":None}]}
            db.add(EmergencyExecution(id=execution['id'],scenario_id=FLOOD_ID,comparison_id=comparison['id'],
                plan_code="FLOOD-B",operator="demo-user",status="completed",started_at=stamp(305),state_json=execution))
        db.commit()


def services(factory):
    from app.services.incident_service import IncidentService
    from app.services.incident_replay_service import IncidentReplayService
    return IncidentService(factory), IncidentReplayService()


def sync(factory):
    from app.models.incident import Incident
    service,_=services(factory)
    with factory() as db:
        service.sync_sources(db);db.commit()
        return {r.incident_type:r.id for r in db.scalars(select(Incident))}


def count_archives(db):
    from app.models.incident import Incident, IncidentTimelineEvent
    return (db.scalar(select(func.count()).select_from(Incident)),
            db.scalar(select(func.count()).select_from(IncidentTimelineEvent)))


def test_flood_leak_aggregation_and_idempotent_backfill(isolated_storage):
    seed_sources(isolated_storage, emergency=True)
    ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        initial=count_archives(db)
        for _ in range(2):service.sync_sources(db);db.commit()
        assert count_archives(db)==initial and initial[0]==2
        flood=service.detail(db,ids['FLOOD']);leak=service.detail(db,ids['PIPELINE_LEAK'])
        assert flood['scenario_id']==FLOOD_ID and leak['source_event_id']=='event-m9-leak'
        assert flood['incident_code']!=leak['incident_code']
        assert flood['comparisons'] and flood['executions']
        assert leak['comparisons'] and leak['executions']
        assert flood['status']=='STABILIZING' and leak['status']=='STABILIZING'
        assert len(flood['work_orders'])==len(leak['work_orders'])==1


@pytest.mark.parametrize('source_status',['reset','interrupted'])
def test_reset_and_restart_backfill_are_aborted_not_closed(isolated_storage,source_status):
    seed_sources(isolated_storage,flood_status=source_status,leak_status=source_status,emergency=True)
    ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        for id in ids.values():
            item=service.detail(db,id)
            assert item['status']=='ABORTED' and item['closed_at'] is None
            assert not any(x['event_type']=='INCIDENT_CLOSED' for x in service.timeline(db,id)['items'])


def test_timeline_stable_sort_dedup_and_readonly(isolated_storage):
    seed_sources(isolated_storage,emergency=True);ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        initial=count_archives(db)
        for id in ids.values():
            first=service.timeline(db,id)['items'];second=service.timeline(db,id)['items']
            assert first==second and first
            keys=[(x['simulation_time'] if x['simulation_time'] is not None else float('inf'),x['event_time'],x['id']) for x in first]
            assert keys==sorted(keys)
            identities=[(x['incident_id'],x['event_type'],x['source_id']) for x in first]
            assert len(identities)==len(set(identities))
            assert any(x['event_type']=='SCENARIO_STARTED' for x in first)
        assert count_archives(db)==initial


def test_legacy_replay_never_backfills_terminal_state_into_old_frames(isolated_storage):
    seed_sources(isolated_storage);ids=sync(isolated_storage);_,replay=services(isolated_storage)
    with isolated_storage() as db:
        flood=replay.replay(db,ids['FLOOD']);leak=replay.replay(db,ids['PIPELINE_LEAK'])
        assert len(flood['snapshots'])==len(leak['snapshots'])==5
        first=flood['snapshots'][0]['scene_state']
        assert first['flood']['waterLevel']==1 and first['flood']['riskScore']==5
        assert not first.get('devices') and not first['flood'].get('entranceClosed')
        early=leak['snapshots'][0]
        assert early['scene_state']['leak']['pipelineFlow']==28
        assert early['scene_state']['leak'].get('estimatedLeakFlow') is None
        assert not early['scene_state'].get('valves')
        assert not early['scene_state']['leak'].get('interruptedBuildings')
        assert not early['scene_state']['leak'].get('affectedBuildings')
        assert not early['scene_state']['leak'].get('suspectedSegments')
        assert flood['metadata']['missing_fields'] and leak['metadata']['missing_fields']
        assert early['missing_fields']


def test_replay_gap_bounds_no_generated_points_and_bounded_downsample(isolated_storage):
    seed_sources(isolated_storage);ids=sync(isolated_storage);_,replay=services(isolated_storage)
    with isolated_storage() as db:
        for t in (5,10,15):
            db.add(FloodSnapshot(scenario_id=FLOOD_ID,timestamp=stamp(t),simulation_time=t,
                rainfall=5,water_level=1,water_area=50,inflow=.1,outflow=.03,
                pump_capacity=.03,risk_score=5,stage='LOW'))
        db.commit()
        original=replay.replay(db,ids['FLOOD'])
        assert original['metadata']['gaps']
        for gap in original['metadata']['gaps']:
            assert gap['duration_seconds']==gap['to_time']-gap['from_time']
        bounded=replay.replay(db,ids['FLOOD'],from_time=30,to_time=300,step_seconds=20)
        assert [s['simulation_time'] for s in bounded['snapshots']]==[30,60,300]
        for t in range(601,4701):
            db.add(FloodSnapshot(scenario_id=FLOOD_ID,timestamp=stamp(t),simulation_time=t,
                rainfall=20,water_level=15,water_area=750,inflow=.1,outflow=.09,
                pump_capacity=.09,risk_score=35,stage='LOW'))
        db.commit()
        sampled=replay.replay(db,ids['FLOOD'],step_seconds=.1)
        times=[s['simulation_time'] for s in sampled['snapshots']]
        assert len(times)<=2000 and times[0]==0 and times[-1]==4700
        assert len(times)==len(set(times)) and times==sorted(times)
        assert set(times)<=({0,5,10,15,30,60,300,600}|set(range(601,4701)))
        assert sampled['metadata']['source_snapshot_count']==4108
        assert sampled['metadata']['latency_ms']>=0


def test_replay_does_not_change_engine_devices_or_live_valves(isolated_storage):
    seed_sources(isolated_storage);ids=sync(isolated_storage);service,replay=services(isolated_storage)
    engine=SimulationEngine();before=engine.snapshot().model_dump()
    with isolated_storage() as db:
        valves={v.id:v.status for v in db.scalars(select(Valve))};counts=count_archives(db)
        for id in ids.values():
            replay.replay(db,id);service.metrics(db,id);service.detail(db,id)
        assert engine.snapshot().model_dump()==before
        assert {v.id:v.status for v in db.scalars(select(Valve))}==valves
        assert valves['V-W-03']=='open' and count_archives(db)==counts


def test_metrics_derive_peaks_from_persisted_samples_and_null_unknowns(isolated_storage):
    seed_sources(isolated_storage);ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        flood=service.metrics(db,ids['FLOOD']);leak=service.metrics(db,ids['PIPELINE_LEAK'])
        assert flood['peak_metrics']['peak_risk']==75
        assert flood['peak_metrics']['peak_water_level']==20
        assert flood['peak_metrics']['max_rainfall']==100
        assert flood['peak_metrics']['max_water_area']==1000
        assert flood['peak_metrics']['min_p03_efficiency'] is None
        assert leak['peak_metrics']['peak_risk']==68
        assert leak['peak_metrics']['max_detection_score']==.76
        assert leak['peak_metrics']['min_pressure']==0
        assert leak['peak_metrics']['max_flow']==50
        assert leak['peak_metrics']['max_affected_buildings']==2
        assert leak['response_metrics']['time_to_detect_seconds']==30
        assert leak['response_metrics']['time_to_confirm_seconds']==60
        assert leak['response_metrics']['time_to_response_seconds']==270
        assert leak['response_metrics']['time_to_stabilize_seconds']==600
        assert leak['response_metrics']['total_incident_duration_seconds']==600
        assert '最后真实采样' in leak['response_metrics']['basis']
        assert leak['prediction_review']['samples']==0


def test_prediction_review_only_evaluated_actuals_and_per_incident(isolated_storage):
    seed_sources(isolated_storage);ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        for i,status,water,risk in [(1,'evaluated',12,48),(2,'evaluated',14,54),
                                     (3,'pending',None,None),(4,'interrupted',999,999),(5,'evaluated',None,None)]:
            db.add(RiskPredictionRecord(id=f'm9-pred-{i}',scenario_id=FLOOD_ID,session_id='m9',
                generated_at=stamp(i),origin_time=i,target_time=i+600,horizon_minutes=10,
                model_version='m6-v1',predicted_water=10,predicted_risk=50,
                physical_water=11,physical_risk=49,agreement='high',evaluation_status=status,
                actual_water=water,actual_risk=risk,sample_span_seconds=1,
                water_error=water-10 if water is not None else None,
                risk_error=risk-50 if risk is not None else None,
                physical_water_error=water-11 if water is not None else None,
                physical_risk_error=risk-49 if risk is not None else None))
        db.commit();review=service.metrics(db,ids['FLOOD'])['prediction_review']
        assert review['label']=='本事件预测误差' and review['samples']==2
        assert review['water_mae']==3 and review['risk_mae']==3
        assert review['physical_water_mae']==2 and review['physical_risk_mae']==3
        assert len(review['items'])==2
        assert service.metrics(db,ids['PIPELINE_LEAK'])['prediction_review']['samples']==0


def test_report_uses_facts_preserves_environment_and_service_limits(isolated_storage):
    seed_sources(isolated_storage,emergency=True);ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        flood=service.generate_report(db,ids['FLOOD']);leak=service.generate_report(db,ids['PIPELINE_LEAK']);db.commit()
        assert flood['metrics']['peak_metrics']['peak_water_level']==20
        assert leak['metrics']['peak_metrics']['peak_risk']==68
        flood_text=' '.join(str(flood[x]) for x in ['summary','cause_analysis','response_analysis','impact_analysis'])
        leak_text=' '.join(str(leak[x]) for x in ['summary','cause_analysis','response_analysis','impact_analysis'])
        assert '降雨' in flood_text and any(word in flood_text for word in ['共同','同时','不能全部'])
        assert '供水' in leak_text and any(word in leak_text for word in ['未恢复','中断','仍','不等于供水恢复'])
        assert '样本不足' in flood['prediction_analysis']
        assert ('82.800 m³/h' in flood['response_analysis'] and '324.000 m³/h' in flood['response_analysis']) or ('0.023 m³/s' in flood['response_analysis'] and '0.090 m³/s' in flood['response_analysis'])
        assert all('建议' in x for x in flood['lessons']+leak['lessons'])


def test_work_order_unique_main_and_explicit_status_machine(isolated_storage):
    from app.schemas.incident import CreateWorkOrder, UpdateWorkOrder
    seed_sources(isolated_storage);ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        body=CreateWorkOrder(incident_id=ids['FLOOD'],title='排水检查',category='INSPECTION')
        order=service.create_work_order(db,body);db.commit()
        again=service.create_work_order(db,body);db.commit()
        assert again['id']==order['id'] and order['status']=='PENDING'
        with pytest.raises(HTTPException):
            service.update_work_order(db,order['id'],UpdateWorkOrder(status='COMPLETED',result='不可跳过处理'))
        with pytest.raises(HTTPException):
            service.update_work_order(db,order['id'],UpdateWorkOrder(status='ASSIGNED'))
        assigned=service.update_work_order(db,order['id'],UpdateWorkOrder(status='ASSIGNED',assignee='排水班组'));db.commit()
        assert assigned['assignee']=='排水班组' and assigned['accepted_at']
        running=service.update_work_order(db,order['id'],UpdateWorkOrder(status='IN_PROGRESS'));db.commit()
        assert running['status']=='IN_PROGRESS'
        with pytest.raises(HTTPException):
            service.update_work_order(db,order['id'],UpdateWorkOrder(status='COMPLETED',result=' '))
        done=service.update_work_order(db,order['id'],UpdateWorkOrder(status='COMPLETED',result='完成软件演练检查'));db.commit()
        assert done['completed_at'] and done['result']=='完成软件演练检查'
        with pytest.raises(HTTPException):
            service.update_work_order(db,order['id'],UpdateWorkOrder(status='IN_PROGRESS'))
        assert len([x for x in service.timeline(db,ids['FLOOD'])['items'] if x['event_type']=='WORK_ORDER_COMPLETED'])==1


@pytest.mark.parametrize('cancel_from',['PENDING','ASSIGNED','IN_PROGRESS'])
def test_work_order_cancel_is_terminal(isolated_storage,cancel_from):
    from app.schemas.incident import CreateWorkOrder, UpdateWorkOrder
    seed_sources(isolated_storage);ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        order=service.create_work_order(db,CreateWorkOrder(incident_id=ids['FLOOD'],title='巡检',category='CANCEL_TEST'))
        if cancel_from in ('ASSIGNED','IN_PROGRESS'):
            service.update_work_order(db,order['id'],UpdateWorkOrder(status='ASSIGNED',assignee='运维一组'))
        if cancel_from=='IN_PROGRESS':service.update_work_order(db,order['id'],UpdateWorkOrder(status='IN_PROGRESS'))
        cancelled=service.update_work_order(db,order['id'],UpdateWorkOrder(status='CANCELLED'));db.commit()
        assert cancelled['status']=='CANCELLED' and cancelled['completed_at'] is None
        with pytest.raises(HTTPException):
            service.update_work_order(db,order['id'],UpdateWorkOrder(status='ASSIGNED',assignee='另一组'))


def test_close_requires_confirmation_stabilizing_and_is_idempotent(isolated_storage):
    from app.schemas.incident import CloseIncident
    seed_sources(isolated_storage);ids=sync(isolated_storage);service,_=services(isolated_storage)
    with isolated_storage() as db:
        body=CloseIncident(result='已确认软件演练稳定，停水影响保留',operator='demo-user',confirmed=True)
        with pytest.raises(HTTPException) as exc:service.close_record(db,ids['FLOOD'],body)
        assert exc.value.status_code==409
        with pytest.raises(HTTPException):
            service.close_record(db,ids['PIPELINE_LEAK'],CloseIncident(result='test',confirmed=False))
        first=service.close_record(db,ids['PIPELINE_LEAK'],body,timestamp=stamp(610),simulation_time=600);db.commit()
        second=service.close_record(db,ids['PIPELINE_LEAK'],body,timestamp=stamp(620),simulation_time=600);db.commit()
        assert first['status']==second['status']=='CLOSED' and first['closed_at']==second['closed_at']
        assert len([x for x in service.timeline(db,ids['PIPELINE_LEAK'])['items'] if x['event_type']=='INCIDENT_CLOSED'])==1
        service.sync_sources(db);db.commit()
        assert service.detail(db,ids['PIPELINE_LEAK'])['status']=='CLOSED'
        service.abort_record(db,ids['PIPELINE_LEAK'],'开发重置不能覆盖已关闭状态');db.commit()
        assert service.detail(db,ids['PIPELINE_LEAK'])['status']=='CLOSED'
        assert db.scalar(select(func.count()).select_from(PipelineLeakSnapshot))==5
        assert db.get(PipelineLeakIsolation,'m9-isolation').execution_json['valves']==['V-W-03']


def test_new_capture_records_discrete_state_at_its_actual_time(isolated_storage):
    service,replay=services(isolated_storage)
    e=SimulationEngine();FloodService(e).start(FloodScenarioRequest(scenario='extreme_rain'),linked=True)
    initial=e.snapshot();incident_id=service.capture(initial);service.capture(initial)
    e.tick(5);e.set_device_state('P01','running');e._state.flood.entrance_closed=True
    next_state=e.snapshot();service.capture(next_state)
    with isolated_storage() as db:
        data=replay.replay(db,incident_id,step_seconds=.1)
        assert len(data['snapshots'])==2
        first,last=[x['scene_state'] for x in data['snapshots']]
        assert not first['flood']['entranceClosed'] and last['flood']['entranceClosed']
        assert next(x['status'] for x in first['devices'] if x['id']=='P01')=='standby'
        assert next(x['status'] for x in last['devices'] if x['id']=='P01')=='running'
        assert e.snapshot()==next_state


def test_empty_archive_has_null_peaks_not_terminal_summary_guesses(isolated_storage):
    from sqlalchemy import delete
    seed_sources(isolated_storage);ids=sync(isolated_storage);service,replay=services(isolated_storage)
    with isolated_storage() as db:
        db.execute(delete(FloodSnapshot));db.commit()
        values=service.metrics(db,ids['FLOOD'])
        assert values['snapshot_count']==0
        assert values['peak_metrics']['peak_risk'] is None and values['peak_metrics']['peak_water_level'] is None
        assert replay.replay(db,ids['FLOOD'])['snapshots']==[]


@async_test
async def test_review_api_validation_filters_and_readonly(isolated_storage):
    async with app.router.lifespan_context(app),httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test/api/v1') as client:
        seed_sources(isolated_storage);ids=sync(isolated_storage)
        all_rows=(await client.get('/incidents')).json()
        assert all_rows['total']==2
        only_flood=(await client.get('/incidents',params={'type':'FLOOD'})).json()
        assert only_flood['total']==1 and only_flood['items'][0]['id']==ids['FLOOD']
        assert (await client.get('/incidents',params={'keyword':'no-such-incident'})).json()['total']==0
        assert (await client.get('/incidents/no-such-id')).status_code==404
        assert (await client.get(f"/incidents/{ids['FLOOD']}/replay",params={'step_seconds':0})).status_code==422
        assert (await client.get(f"/incidents/{ids['FLOOD']}/replay",params={'from_time':400,'to_time':30})).status_code==422
        await app.state.realtime.engine.shutdown()
        app.state.realtime.engine.stop()
        before=app.state.realtime.engine.snapshot()
        for kind,id in ids.items():
            for suffix in ['', '/timeline', '/replay', '/metrics', '/review']:
                assert (await client.get(f'/incidents/{id}{suffix}')).status_code==200
        assert app.state.realtime.engine.snapshot()==before


@async_test
async def test_runtime_close_preserves_actual_valves_devices_and_history(isolated_storage):
    from app.models.incident import Incident
    from app.schemas.incident import CloseIncident
    from app.schemas.leak import LeakStart, IsolationExecute
    from app.services.realtime_service import RealtimeService
    with isolated_storage() as db:seed_pipelines(db)
    realtime=RealtimeService();engine=realtime.engine
    await realtime.leak.start_scenario(LeakStart());engine.set_speed(10)
    for _ in range(60):engine.tick(1)
    realtime.incidents.core.capture(engine.snapshot())
    comparison=await realtime.leak.compare('WS-003')
    execution_time=engine._state.leak.elapsed_simulation_seconds
    await realtime.leak.execute(IsolationExecute(comparison_id=comparison['id'],
        option_id=comparison['options'][0]['id'],confirmed_simulation=True))
    realtime.incidents.core.capture(engine.snapshot())
    for _ in range(30):engine.tick(1)
    assert engine._state.leak.current_stage=='STABILIZING'
    await realtime.leak.sample()
    realtime.incidents.observe(engine.snapshot());await realtime.incidents.flush(strict=True)
    with isolated_storage() as db:
        incident=db.scalar(select(Incident).where(Incident.scenario_id==engine._state.leak.scenario_id))
        assert incident is not None and incident.status=='STABILIZING'
        incident_id=incident.id
        before_valves={v.id:v.status for v in db.scalars(select(Valve))}
        for _ in range(2):realtime.incidents.core.sync_sources(db);db.commit()
        timeline=realtime.incidents.core.timeline(db,incident_id)['items']
        assert sum(event['event_type']=='RISK_STABILIZED' for event in timeline)==1
        closures=[event for event in timeline if event['event_type']=='VALVE_CLOSED']
        assert len(closures)==1 and closures[0]['simulation_time']==execution_time
    before=engine.snapshot()
    closed=await realtime.incidents.close(incident_id,CloseIncident(result='软件泄漏受控，供水中断保留',confirmed=True))
    after=engine.snapshot()
    assert closed['status']=='CLOSED' and not after.leak.scenario_id
    assert not after.running and after.devices==before.devices and after.pipelines==before.pipelines
    assert after.environment==before.environment and not after.flood.scenario_id
    leak_physical=('service_status','leak_status','affected_buildings','affected_nodes','affected_edges',
        'interrupted_buildings','estimated_service_loss','upstream_pressure','downstream_pressure','pipeline_flow',
        'estimated_leak_flow','leak_severity','suspected_segments','risk_score')
    assert {key:getattr(after.leak,key) for key in leak_physical}=={key:getattr(before.leak,key) for key in leak_physical}
    assert after.leak.service_status=='INTERRUPTED' and len(after.leak.interrupted_buildings)==2
    with isolated_storage() as db:
        assert {v.id:v.status for v in db.scalars(select(Valve))}==before_valves
        assert before_valves['V-W-03']=='closed'
        assert db.get(Incident,incident_id).status=='CLOSED'
        assert db.get(PipelineLeakIsolation,comparison['id']).execution_json
        assert db.scalar(select(func.count()).select_from(PipelineLeakSnapshot))>0
    again=await realtime.incidents.close(incident_id,CloseIncident(result='幂等重试',confirmed=True))
    assert again['closed_at']==closed['closed_at']


@async_test
async def test_closing_historical_incident_does_not_detach_another_live_incident(isolated_storage):
    from app.schemas.incident import CloseIncident
    from app.services.realtime_service import RealtimeService
    seed_sources(isolated_storage);ids=sync(isolated_storage)
    realtime=RealtimeService();FloodService(realtime.engine).start(FloodScenarioRequest(scenario='extreme_rain'),linked=True)
    before=realtime.engine.snapshot()
    result=await realtime.incidents.close(ids['PIPELINE_LEAK'],CloseIncident(result='关闭已稳定的历史事故',confirmed=True))
    assert result['status']=='CLOSED'
    assert realtime.engine.snapshot()==before
    assert realtime.engine._state.flood.scenario_id not in (None,FLOOD_ID)


@async_test
async def test_live_capture_then_backfill_does_not_duplicate_start_or_first_detection(isolated_storage):
    from app.schemas.leak import LeakStart
    from app.services.pipeline_leak_service import PipelineLeakService
    from app.services.flood_storage_service import FloodStorageService
    from app.websocket.manager import ConnectionManager
    service,_=services(isolated_storage)
    flood=SimulationEngine();FloodService(flood).start(FloodScenarioRequest(scenario='extreme_rain'),linked=True)
    flood.set_speed(10)
    for _ in range(90):flood.tick(1)
    flood_id=service.capture(flood.snapshot())
    FloodStorageService(flood,isolated_storage).persist(flood.snapshot())
    with isolated_storage() as db:seed_pipelines(db)
    leak=SimulationEngine();leak_service=PipelineLeakService(leak,isolated_storage,ConnectionManager())
    await leak_service.start_scenario(LeakStart());leak.set_speed(10)
    for _ in range(60):leak.tick(1)
    leak_id=service.capture(leak.snapshot());await leak_service.sample()
    with isolated_storage() as db:
        service.sync_sources(db);db.commit()
        for id in [flood_id,leak_id]:
            timeline=service.timeline(db,id)['items']
            assert sum(x['event_type']=='SCENARIO_STARTED' for x in timeline)==1
        flood_timeline=service.timeline(db,flood_id)['items']
        assert sum(x['event_type']=='ANOMALY_DETECTED' for x in flood_timeline)==1
        assert sum(x['event_type']=='ANOMALY_CONFIRMED' for x in flood_timeline)==1


@pytest.mark.parametrize('control',['valve','pump'])
def test_paused_same_time_discrete_boundaries_survive_downsample_and_timestamp_retry(isolated_storage,control):
    """Mid-history transitions must survive even if not the final point or an ACTION marker."""
    from app.services.pipeline_graph_service import PipelineGraphService
    from app.services.valve_service import ValveService
    service,replay=services(isolated_storage)
    with isolated_storage() as db:
        seed_pipelines(db);graph=PipelineGraphService(db).graph
    engine=SimulationEngine();engine.configure_pipelines(graph)
    FloodService(engine).start(FloodScenarioRequest(scenario='extreme_rain'),linked=True)
    def capture(wall):
        observation=engine.snapshot();observation.timestamp=stamp(wall)
        return service.capture(observation)
    incident_id=capture(0)
    engine.tick(5);engine.stop();capture(5)
    if control=='valve':
        with isolated_storage() as db:
            graph=ValveService.apply(db,{'V-W-03':'closed'});db.commit()
        engine.configure_pipelines(graph)
    else:engine.set_device_state('P01','running')
    capture(6);capture(6.5)  # Timestamp-only retry is not another physical observation.
    engine.start();engine.tick(5);capture(7)
    with isolated_storage() as db:
        all_points=replay.snapshots(db,incident_id)
        assert len(all_points)==4
        data=replay.replay(db,incident_id,step_seconds=3600)
        middle=[point for point in data['snapshots'] if point['simulation_time']==5]
        assert len(middle)==2 and middle[0]['timestamp']<middle[1]['timestamp']
        group,key='valves','V-W-03' if control=='valve' else 'P01'
        if control=='pump':group='devices'
        states=[next(item['status'] for item in point['scene_state'][group] if item['id']==key) for point in middle]
        assert states==(['open','closed'] if control=='valve' else ['standby','running'])
        assert data['snapshots'][0]['simulation_time']==0 and data['snapshots'][-1]['simulation_time']==10
        assert all(point['scene_state']['recordedAt']==point['timestamp'] for point in data['snapshots'])


def test_accelerated_normal_sampling_is_not_a_gap_but_missing_wall_interval_is(isolated_storage):
    from sqlalchemy import delete
    seed_sources(isolated_storage);ids=sync(isolated_storage);_,replay=services(isolated_storage)
    with isolated_storage() as db:
        db.execute(delete(FloodSnapshot))
        # A genuine 10× run: every five wall seconds advances fifty simulation seconds.
        for wall,sim in [(0,0),(5,50),(10,100),(15,150),(20,200)]:
            db.add(FloodSnapshot(scenario_id=FLOOD_ID,timestamp=stamp(wall),simulation_time=sim,
                rainfall=20,water_level=5,water_area=250,inflow=.1,outflow=.03,
                pump_capacity=.03,risk_score=30,stage='LOW'))
        db.commit()
        normal=replay.replay(db,ids['FLOOD'])
        assert normal['metadata']['gaps']==[]
        db.add(FloodSnapshot(scenario_id=FLOOD_ID,timestamp=stamp(80),simulation_time=800,
            rainfall=20,water_level=5,water_area=250,inflow=.1,outflow=.03,
            pump_capacity=.03,risk_score=30,stage='LOW'))
        db.commit()
        missing=replay.replay(db,ids['FLOOD'])
        assert len(missing['metadata']['gaps'])==1
        assert missing['metadata']['gaps'][0]['from_time']==200
        assert missing['metadata']['gaps'][0]['to_time']==800
        assert [p['simulation_time'] for p in missing['snapshots']]==[0,50,100,150,200,800]


@async_test
async def test_real_flood_c_close_keeps_water_closed_entrance_and_exposure(isolated_storage):
    from app.models.incident import Incident
    from app.schemas.incident import CloseIncident
    from app.schemas.emergency import ExecuteRequest
    from app.services.realtime_service import RealtimeService
    with isolated_storage() as db:seed_pipelines(db)
    realtime=RealtimeService();engine=realtime.engine;realtime.emergency.initialize()
    FloodService(engine).start(FloodScenarioRequest(scenario='extreme_rain',duration_minutes=60,rainfall_recession=True),linked=True)
    engine.set_speed(10)
    for _ in range(174):engine.tick(1)
    engine.stop();comparison=await realtime.emergency.compare(['FLOOD-C'])
    await realtime.emergency.execute(ExecuteRequest(plan_code='FLOOD-C',comparison_id=comparison['id'],confirmed_simulation=True))
    engine.start()
    for _ in range(76):engine.tick(1)
    assert engine._state.emergency.phase=='STABILIZING' and engine._state.flood.risk_score<60
    assert engine._state.flood.entrance_closed and engine._state.flood.people_count<32
    await realtime.flood_storage.sample();realtime.emergency.observe(engine.snapshot());await realtime.emergency.flush()
    realtime.incidents.observe(engine.snapshot());await realtime.incidents.flush(strict=True)
    with isolated_storage() as db:
        incident=db.scalar(select(Incident).where(Incident.scenario_id==engine._state.flood.scenario_id));incident_id=incident.id
        for _ in range(2):realtime.incidents.core.sync_sources(db);db.commit()
        timeline=realtime.incidents.core.timeline(db,incident_id)['items']
        assert sum(event['event_type']=='RISK_STABILIZED' for event in timeline)==1
    before=engine.snapshot()
    closed=await realtime.incidents.close(incident_id,CloseIncident(result='Plan C 稳定，入口仍封控，积水和人员暴露保留',confirmed=True))
    after=engine.snapshot()
    assert closed['status']=='CLOSED' and not after.flood.scenario_id and not after.running
    physical_fields=('water_level','water_area','flood_volume','effective_area','entrance_closed','people_count',
        'vehicle_count','vehicle_entry_rate','exposure_remaining','exposure_target','effective_pump_capacity','outflow','risk_score')
    assert {key:getattr(after.flood,key) for key in physical_fields}=={key:getattr(before.flood,key) for key in physical_fields}
    assert after.flood.entrance_closed and after.flood.water_level>0
    assert after.devices==before.devices and after.pipelines==before.pipelines and after.valves==before.valves
    assert after.environment==before.environment


def test_manual_reopen_then_close_creates_another_valve_event(isolated_storage):
    from app.services.pipeline_graph_service import PipelineGraphService
    from app.services.valve_service import ValveService
    with isolated_storage() as db:
        seed_pipelines(db);graph=PipelineGraphService(db).graph
    engine=SimulationEngine();engine.configure_pipelines(graph)
    FloodService(engine).start(FloodScenarioRequest(scenario='extreme_rain'),linked=True)
    service,_=services(isolated_storage);incident_id=service.capture(engine.snapshot())
    def set_valve(status):
        with isolated_storage() as db:
            changed=ValveService.apply(db,{'V-W-03':status});db.commit()
        engine.configure_pipelines(changed);service.capture(engine.snapshot())
    engine.tick(5);set_valve('closed')
    engine.tick(5);set_valve('open')
    engine.tick(5);set_valve('closed')
    with isolated_storage() as db:
        timeline=service.timeline(db,incident_id)['items']
        closures=[event for event in timeline if event['event_type']=='VALVE_CLOSED']
        assert [event['simulation_time'] for event in closures]==[5,15]
        assert len({event['source_id'] for event in closures})==2
        assert all(event['payload']['focus_target_id']=='V-W-03' for event in closures)


def test_explicit_reconcile_deduplicates_derived_events_preserving_all_original_sources(isolated_storage):
    from uuid import uuid4
    from app.models.incident import IncidentTimelineEvent
    seed_sources(isolated_storage,emergency=True);ids=sync(isolated_storage);service,_=services(isolated_storage)
    source_models=(FloodScenarioRecord,FloodSnapshot,PipelineLeakEvent,PipelineLeakSnapshot,
                   PipelineLeakIsolation,EmergencyComparison,EmergencyExecution)
    def originals(db):
        return {model.__tablename__:[{column.name:deepcopy(getattr(row,column.name)) for column in model.__table__.columns}
            for row in db.scalars(select(model).order_by(next(iter(model.__table__.primary_key.columns))))]
            for model in source_models}
    with isolated_storage() as db:
        original_rows=originals(db)
        for kind,id in ids.items():
            stable=next(event for event in service.timeline(db,id)['items'] if event['event_type']=='RISK_STABILIZED')
            db.add(IncidentTimelineEvent(id=str(uuid4()),incident_id=id,event_time=datetime.fromisoformat(stable['event_time']),
                simulation_time=stable['simulation_time'],event_type='RISK_STABILIZED',event_level='info',
                title='旧派生重复稳定',description='来自旧 live fallback 的重复节点',source='live_capture',
                source_id='first-stable',payload={'legacy_duplicate':True}))
        db.add(IncidentTimelineEvent(id=str(uuid4()),incident_id=ids['PIPELINE_LEAK'],event_time=stamp(300),
            simulation_time=300,event_type='VALVE_CLOSED',event_level='info',title='V-W-03 已关闭',
            description='旧 live capture 对同次隔离的重复记录',source='live_capture',source_id='V-W-03:300.0',
            payload={'focus_target_id':'V-W-03'}))
        db.commit()
        service.sync_sources(db);service.reconcile_derived_events(db);db.commit()
        after={id:service.timeline(db,id)['items'] for id in ids.values()}
        for timeline in after.values():
            stable=[event for event in timeline if event['event_type']=='RISK_STABILIZED']
            assert len(stable)==1 and stable[0]['payload'].get('merged_source_records')
        assert len([event for event in after[ids['PIPELINE_LEAK']] if event['event_type']=='VALVE_CLOSED'])==1
        assert originals(db)==original_rows
        service.sync_sources(db);service.reconcile_derived_events(db);db.commit()
        assert {id:service.timeline(db,id)['items'] for id in ids.values()}==after
        assert originals(db)==original_rows
