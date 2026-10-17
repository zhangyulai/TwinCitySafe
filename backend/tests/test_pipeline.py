import pytest
import asyncio
import httpx
from app.main import app
from app.services.pipeline_seed import seed_pipelines
from app.services.pipeline_graph_service import PipelineGraphService
from app.models.pipeline import PipelineEdge, Valve as ValveModel
from algorithm.graph_search.graph import PipelineGraph
from algorithm.graph_search.types import Node, Edge, Valve
from algorithm.graph_search.traversal import trace, affected
from algorithm.graph_search.isolation import isolation_options
from simulator.engine import SimulationEngine

@pytest.fixture
def assets(isolated_storage):
    with isolated_storage() as session:
        assert seed_pipelines(session)=={"nodes":34,"edges":32,"valves":10}
        yield session

def test_seed_idempotent_and_validation(assets):
    assert seed_pipelines(assets)=={"nodes":0,"edges":0,"valves":0}
    g=PipelineGraphService(assets)
    check=g.graph.validate()
    assert check["nodeCount"]==34 and check["edgeCount"]==32
    assert not any(check[k] for k in ("isolatedNodes","invalidEdges","duplicateIds"))
    assert len(g.valves)==10
    assert len(g.graph.connected("drainage")[1])==11

def test_trace_valves_affected_and_options(assets):
    g=PipelineGraphService(assets)
    up=g.get_upstream("WS-003");down=g.get_downstream("WS-003")
    assert "WS-SOURCE-01" in up["sources"]
    assert "WS-SOURCE-01" in g.get_upstream("WS-J-03")["sources"]
    assert set(up["valves"])=={"V-W-01","V-W-02","V-W-03"}
    assert {b["buildingName"] for b in down["buildings"]}=={"科研楼 B","实验楼 C"}
    assert g.get_affected_buildings("WS-003")==down["buildings"]
    assert g.get_valves_for_edge("WS-003")["upstream"]==["V-W-03"]
    options=g.find_isolation_options("WS-003")
    assert len(options)==3
    assert [o["estimatedScope"]["buildingCount"] for o in options]==[2,4,5]
    for o in options:
        nodes,_=g.graph.connected("water",closed=o["valves"],physical=True)
        e=g.graph.edges["WS-003"]
        assert e.start not in nodes and e.end not in nodes
    assert len({tuple(o["isolatedEdges"]) for o in options})==3

def test_asset_update_query_preserves_seed(assets):
    e=assets.get(PipelineEdge,"WS-003");e.material="检修材质";assets.commit();seed_pipelines(assets)
    assert assets.get(PipelineEdge,"WS-003").material=="检修材质"

def test_smooth_close_reopen_and_reset(assets):
    engine=SimulationEngine();engine.configure_pipelines(PipelineGraphService(assets).graph)
    initial=next(p for p in engine.snapshot().pipelines if p.id=="WS-003").flow
    valve=assets.get(ValveModel,"V-W-02");valve.status="closed";assets.commit()
    engine.configure_pipelines(PipelineGraphService(assets).graph)
    immediate=next(p for p in engine.snapshot().pipelines if p.id=="WS-003")
    assert immediate.status=="isolated" and immediate.flow==initial
    values=[]
    for _ in range(90):values.append(next(p for p in engine.tick().pipelines if p.id=="WS-003").flow)
    assert all(b<a for a,b in zip(values,values[1:])) and values[-1]<.2
    assert len(engine.reset().pipelines)==32
    assert next(p for p in engine.snapshot().pipelines if p.id=="WS-003").status=="isolated"
    valve.status="open";assets.commit();engine.configure_pipelines(PipelineGraphService(assets).graph)
    assert next(p for p in engine.tick().pipelines if p.id=="WS-003").status=="normal"

def small(edges=None,valves=None):
    return PipelineGraph([Node("s","source"),Node("v","valve"),Node("a","junction"),Node("b","building_connection","B","Building"),Node("x","junction")],
        edges or [Edge("1","s","v","water"),Edge("2","v","a","water"),Edge("3","a","b","water")],valves or [Valve("V","v")])

def test_simple_path_and_disconnected_graph():
    g=small();assert g.connected("water")[0]=={"s","v","a","b"}
    assert g.validate()["isolatedNodes"]==["x"]
    assert trace(g,"2","upstream")["sources"]==["s"]
    assert len(affected(g,"3"))==1

def test_branch_duplicate_path_and_cycle():
    g=small([Edge("1","s","v","water"),Edge("2","v","a","water"),Edge("3","a","b","water"),Edge("4","v","b","water"),Edge("5","b","a","water")])
    assert len(g.connected("water")[1])==5
    assert not affected(g,"3")
    assert len(trace(g,"2","downstream")["edges"])==3
    assert len(isolation_options(g,"3"))==1

def test_closed_valve_source_loss_and_invalid_graph():
    g=small(valves=[Valve("V","v","closed")]);assert g.connected("water")[0]=={"s"}
    g=PipelineGraph([Node("a","junction"),Node("b","building_connection","B")],[Edge("1","a","b","water")],[])
    assert g.connected("water")== (set(),set()) and isolation_options(g,"1")==[]
    bad=PipelineGraph([Node("a","source"),Node("a","source")],[Edge("bad","a","missing","water")],[])
    assert bad.validate()["duplicateIds"]==["a"] and bad.validate()["invalidEdges"]==["bad"]

def test_multiple_sources_require_multiple_valves():
    g=PipelineGraph([Node("s1","source"),Node("s2","source"),Node("v1","valve"),Node("v2","valve"),Node("a","junction"),Node("b","building_connection","B")],
       [Edge("1","s1","v1","water"),Edge("2","v1","a","water"),Edge("3","s2","v2","water"),Edge("4","v2","a","water"),Edge("target","a","b","water")],
       [Valve("V1","v1"),Valve("V2","v2")])
    options=isolation_options(g,"target");assert len(options)==1 and options[0]["valves"]==["V1","V2"]

def test_api_and_development_valve(assets,monkeypatch):
    async def exercise():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
                assert len((await client.get("/api/v1/pipelines")).json())==32
                assert len((await client.get("/api/v1/pipelines?type=water&keyword=WS-003")).json())==1
                assert (await client.get("/api/v1/pipelines?type=gas")).status_code==422
                for suffix in ("", "/realtime", "/topology", "/upstream", "/downstream", "/valves", "/affected-buildings"):
                    assert (await client.get("/api/v1/pipelines/WS-003"+suffix)).status_code==200
                assert (await client.get("/api/v1/pipelines/missing")).status_code==404
                assert (await client.get("/api/v1/pipelines/topology/validate")).json()["nodeCount"]==34
                assert len((await client.post("/api/v1/pipelines/WS-003/isolation-options")).json()["options"])==3
                result=await client.post("/api/v1/simulation/valve/V-W-02/state",json={"status":"closed"})
                assert result.status_code==200 and len(result.json()["affectedBuildings"])==4
                assert any(p["status"]=="isolated" for p in result.json()["state"]["pipelines"])
                assert (await client.get("/api/v1/pipelines?status=isolated")).json()
                assert (await client.post("/api/v1/simulation/valve/V-W-02/state",json={"status":"open"})).status_code==200
                assert (await client.post("/api/v1/simulation/valve/V-W-02/state",json={"status":"broken"})).status_code==422
                from app.core.config import get_settings
                monkeypatch.setattr(get_settings(),"app_env","production")
                assert (await client.post("/api/v1/simulation/valve/V-W-02/state",json={"status":"closed"})).status_code==404
    asyncio.run(exercise())
