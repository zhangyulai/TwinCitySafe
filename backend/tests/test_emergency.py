import asyncio
from copy import deepcopy
from datetime import datetime, UTC
import pytest
from fastapi import HTTPException
import httpx
from functools import wraps
def async_test(fn):
    @wraps(fn)
    def run(*args,**kwargs):return asyncio.run(fn(*args,**kwargs))
    return run
from sqlalchemy import select
from app.main import app
from app.schemas.emergency import ExecuteRequest, EmergencyAction
from app.schemas.flood import FloodScenarioRequest
from app.services.emergency_service import EmergencyService
from app.services.emergency_plan_service import default_templates, EmergencyPlanMatchService, EmergencyPlanSimulationService, baseline_signature
from app.services.emergency_execution_service import EmergencyExecutionEngine
from app.services.flood_service import FloodService
from app.services.flood_forecast_service import FloodForecastService
from app.models.emergency import EmergencyExecution,EmergencyExecutionStep,EmergencyComparison
from app.websocket.manager import ConnectionManager
from simulator.engine import SimulationEngine
from algorithm.risk_prediction.simulation import SimulationCopy

def engine(recession=False):
    e=SimulationEngine();FloodService(e).start(FloodScenarioRequest(scenario="extreme_rain",duration_minutes=60,rainfall_recession=recession),linked=True)
    e.set_speed(10)
    for _ in range(174):e.tick(1)
    e.stop();return e

def service(e,factory):
    s=EmergencyService(e,factory,ConnectionManager());s.initialize();return s

def test_counterfactual_clones_baseline_actions_cost_and_exposure():
    e=engine(True);before=baseline_signature(e);base=SimulationCopy(e)
    baseline=EmergencyPlanSimulationService.rollout(base,None)
    a,b,c=[EmergencyPlanSimulationService.rollout(base,p) for p in default_templates()]
    assert baseline_signature(e)==before
    assert all(x["timeline"][0]==baseline["timeline"][0] for x in [a,b,c])
    assert len(c["timeline"])==31 and c["timeline"][-1]["minute"]==30
    assert b["final_pump_capacity"]>=a["final_pump_capacity"]>baseline["final_pump_capacity"]
    assert b["final_water_level"]<a["final_water_level"]<baseline["final_water_level"]
    assert c["final_water_level"]==b["final_water_level"]  # Entry closure never removes water.
    assert c["affected_people"]<b["affected_people"] and c["affected_vehicles"]==b["affected_vehicles"]
    assert c["resource_cost_score"]==pytest.approx(b["resource_cost_score"]+10)
    assert a["pump_runtime_minutes"]["P02"]==0 and b["pump_runtime_minutes"]["P02"]<30
    assert c["time_to_risk_below_60"] is not None
    assert all(0<=p["risk_score"]<=100 and p["water_level"]>=0 for p in c["timeline"])

def test_sustained_extreme_rain_is_not_faked_as_drainable():
    e=engine();r=EmergencyPlanSimulationService.rollout(SimulationCopy(e),default_templates()[1])
    assert r["final_water_level"]>e._state.flood.water_level
    assert r["time_to_risk_below_40"] is None

@pytest.mark.parametrize("case",["missing","offline","fault","conflict","inactive","entrance","valve","parameters"])
def test_plan_validation(case):
    e=engine();p=deepcopy(default_templates()[1])
    if case=="missing":e._state.devices=[d for d in e._state.devices if d.id!="P02"]
    if case=="offline":e.set_device_state("P02","offline")
    if case=="fault":e.set_fault("P02","overheat")
    if case=="conflict":p["actions"].append(EmergencyAction(action_type="STOP_PUMP",target_id="P01").model_dump())
    if case=="inactive":e.reset()
    if case=="entrance":p["actions"].append(EmergencyAction(action_type="CLOSE_ENTRANCE",target_id="MISSING").model_dump())
    if case=="valve":p["actions"].append(EmergencyAction(action_type="CLOSE_VALVE",target_id="V-W03").model_dump())
    if case=="parameters":p["actions"][0]["parameters"]={"water_level":0}
    assert EmergencyPlanMatchService.reasons(e,p)

def test_offline_matching_disables_b_and_c():
    e=engine();e.set_device_state("P02","offline")
    matches=EmergencyPlanMatchService.match(e,default_templates())
    assert [p["available"] for p in matches]==[True,False,False]

@async_test
async def test_compare_storage_stale_and_confirmation(isolated_storage):
    e=engine();s=service(e,isolated_storage);before=e.snapshot()
    c=await s.compare(["FLOOD-A","FLOOD-B","FLOOD-C"])
    assert e.snapshot()==before
    with isolated_storage() as db:assert db.get(EmergencyComparison,c["id"]).baseline_state_hash==c["baseline_state_hash"]
    with pytest.raises(HTTPException) as invalid:await s.execute(ExecuteRequest(plan_code="FLOOD-B",comparison_id=c["id"]))
    assert invalid.value.status_code==422
    e._state.weather.rainfall-=10
    with pytest.raises(HTTPException) as stale:await s.execute(ExecuteRequest(plan_code="FLOOD-B",comparison_id=c["id"],confirmed_simulation=True))
    assert stale.value.detail["code"]=="STALE_COMPARISON"
    assert e._state.emergency is None
    with pytest.raises(HTTPException):await s.compare(["BASELINE"])

@async_test
async def test_execute_gradual_pumps_risk_forecast_and_durable_steps(isolated_storage):
    e=engine(True);s=service(e,isolated_storage);c=await s.compare(["FLOOD-B"])
    before=e.snapshot();old=FloodForecastService.forecast(e,[30])
    x=await s.execute(ExecuteRequest(plan_code="FLOOD-B",comparison_id=c["id"],confirmed_simulation=True))
    assert e._state.flood==before.flood and e._state.devices==before.devices  # Pending until next live tick.
    e.start();e.set_speed(1);e.tick(.25)
    assert 0<e._state.devices[0].startup_progress<.01
    assert e._state.devices[1].status=="standby"
    assert e._state.flood.effective_pump_capacity<before.flood.effective_pump_capacity+.001
    new=FloodForecastService.forecast(e,[30]);assert new.points[0].water_level<old.points[0].water_level
    risks=[];e.set_speed(10)
    for _ in range(100):
        state=e.tick(1);risks.append(state.flood.risk_score);s.observe(state)
    assert e._state.emergency.status=="completed" and e._state.emergency.phase=="STABILIZING"
    assert e._state.flood.risk_score<before.flood.risk_score and e._state.flood.growth_rate<0
    assert max(abs(a-b) for a,b in zip(risks,risks[1:]))<5
    assert e._state.flood.alarm.id==before.flood.alarm.id and e._state.flood.alarm.status=="active"
    await s.flush()
    with isolated_storage() as db:
        assert db.get(EmergencyExecution,x["id"]).status=="completed"
        assert len(list(db.scalars(select(EmergencyExecutionStep))))==2

@async_test
async def test_cancel_pending_preserves_applied_actions_and_reset_history(isolated_storage):
    e=engine();s=service(e,isolated_storage);c=await s.compare(["FLOOD-C"])
    x=await s.execute(ExecuteRequest(plan_code="FLOOD-C",comparison_id=c["id"],confirmed_simulation=True))
    e.start();e.set_speed(1);s.observe(e.tick(1));await s.cancel(x["id"]);s.observe(e.snapshot())
    for _ in range(20):e.tick(5)
    assert e._state.devices[0].status=="running" and e._state.devices[1].status=="standby"
    assert not e._state.flood.entrance_closed
    assert [t.status for t in e._state.emergency.steps][1:]==["cancelled","cancelled"]
    await s.flush();e.reset();s.observe(e.snapshot());await s.flush()
    assert (await s.get_execution(x["id"]))["status"]=="cancelled"

@async_test
async def test_fault_during_pending_step_fails_without_starting_it(isolated_storage):
    e=engine();s=service(e,isolated_storage);c=await s.compare(["FLOOD-B"])
    await s.execute(ExecuteRequest(plan_code="FLOOD-B",comparison_id=c["id"],confirmed_simulation=True))
    e.set_fault("P02","overheat");e.start()
    e.tick(2)
    assert e._state.emergency.status=="failed" and e._state.devices[1].status=="standby"

@async_test
async def test_restart_marks_pending_execution_failed(isolated_storage):
    e=engine();s=service(e,isolated_storage);c=await s.compare(["FLOOD-A"])
    x=await s.execute(ExecuteRequest(plan_code="FLOOD-A",comparison_id=c["id"],confirmed_simulation=True))
    replacement=service(SimulationEngine(),isolated_storage)
    assert (await replacement.get_execution(x["id"]))["status"]=="failed"
    assert replacement.engine._state.emergency is None

@async_test
async def test_emergency_api_real_schema_and_no_action_preview():
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        assert (await client.get('/api/v1/emergency/plans')).status_code==200
        assert (await client.post('/api/v1/emergency/compare',json={})).status_code==409
        await client.post('/api/v1/simulation/flood/emergency-demo-start')
        await client.post('/api/v1/simulation/flood/stop')
        before=(await client.get('/api/v1/realtime/state')).json()
        r=await client.post('/api/v1/emergency/preview',json={"plan_code":"FLOOD-C"})
        assert r.status_code==200,r.text
        after=(await client.get('/api/v1/realtime/state')).json()
        assert before['devices']==after['devices'] and before['flood']==after['flood']
        assert (await client.post('/api/v1/emergency/compare',json={"horizon_minutes":20})).status_code==422
        assert (await client.post('/api/v1/emergency/execute',json={"plan_code":"FLOOD-C"})).status_code==422

@async_test
async def test_stale_simulation_age_and_heartbeat_revision(isolated_storage):
    e=engine();s=service(e,isolated_storage);c=await s.compare(["FLOOD-A"])
    for _ in range(4):e.tick(1)
    assert not s.is_stale(c)
    e._state.flood.elapsed_simulation_seconds+=31
    assert s.is_stale(c)

@async_test
async def test_storage_failure_prevents_live_execution(isolated_storage,monkeypatch):
    e=engine();s=service(e,isolated_storage);c=await s.compare(["FLOOD-B"]);before=e.snapshot()
    def fail(_):raise OSError("test storage unavailable")
    monkeypatch.setattr(s,"save_execution",fail)
    with pytest.raises(HTTPException) as error:
        await s.execute(ExecuteRequest(plan_code="FLOOD-B",comparison_id=c["id"],confirmed_simulation=True))
    assert error.value.status_code==503 and e.snapshot()==before

@async_test
async def test_resource_change_during_persistence_cancels_intent(isolated_storage,monkeypatch):
    e=engine();s=service(e,isolated_storage);c=await s.compare(["FLOOD-B"]);save=s.save_execution
    def changed(x):
        save(x)
        e.set_device_state("P02","offline")
    monkeypatch.setattr(s,"save_execution",changed)
    with pytest.raises(HTTPException):await s.execute(ExecuteRequest(plan_code="FLOOD-B",comparison_id=c["id"],confirmed_simulation=True))
    assert e._state.emergency is None and e._state.devices[0].status=="standby"
    monkeypatch.setattr(s,"save_execution",save);await s.flush()
    with isolated_storage() as db:
        records=list(db.scalars(select(EmergencyExecution)))
        assert len(records)==1 and records[0].status=="cancelled"
        assert all(step["status"]=="cancelled" for step in records[0].state_json["steps"])

def test_entrance_reopen_stops_exposure_decay_without_restoring_people():
    e=engine();f=e._state.flood
    FloodService.set_entrance(f,True);initial=f.people_count;water=f.water_level
    assert f.people_count==initial and f.water_level==water
    e.start();e.tick(5);assert f.people_count<initial
    FloodService.set_entrance(f,False);count=f.people_count
    e.tick(5);assert f.people_count==count and not f.entrance_closed
