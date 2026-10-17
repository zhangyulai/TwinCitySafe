from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.api.devices import storage_db
from app.api.realtime import service
from app.core.config import get_settings
from app.models.pipeline import Valve
from app.schemas.pipeline import PipelineType, PipelineStatus, ValveStateRequest
from app.services.pipeline_graph_service import PipelineGraphService
router=APIRouter()

def graph(session):return PipelineGraphService(session)
def require(g,id):
    if id not in g.graph.edges:raise HTTPException(404,"Pipeline not found")
def live(request,id):
    item=next((p for p in service(request).engine.snapshot().pipelines if p.id==id),None)
    if item is None:raise HTTPException(503,"Pipeline simulation unavailable; restart after migration/seed")
    return item

@router.get("/pipelines/topology/validate")
def validate(session:Session=Depends(storage_db)):
    return graph(session).graph.validate()

@router.get("/pipelines/network")
def network(session:Session=Depends(storage_db)):
    return graph(session).serialize()

@router.get("/pipelines/statistics")
def statistics(request:Request,session:Session=Depends(storage_db)):
    g=graph(session);states={p.id:p.status for p in service(request).engine.snapshot().pipelines}
    return {"totalLength":round(sum(e.length for e in g.edges),2),"edgeCount":len(g.edges),"valveCount":len(g.valves),
        "normalRate":sum(states.get(e.id,e.status)=="normal" for e in g.edges)/max(1,len(g.edges))*100}

@router.get("/pipelines")
def pipelines(request:Request,type:PipelineType|None=None,status:PipelineStatus|None=None,keyword:str=Query("",max_length=100),session:Session=Depends(storage_db)):
    items=graph(session).serialize()["edges"];states={p.id:p for p in service(request).engine.snapshot().pipelines}
    for e in items:
        p=states.get(e["id"]);e["status"]=p.status if p else e["status"]
    return [e for e in items if (type is None or e["pipelineType"]==type) and (status is None or e["status"]==status) and keyword.casefold() in (e["id"]+e["material"]).casefold()]

@router.get("/pipelines/{id}")
def detail(id:str,session:Session=Depends(storage_db)):
    g=graph(session);require(g,id)
    return next(e for e in g.serialize()["edges"] if e["id"]==id)

@router.get("/pipelines/{id}/realtime")
def realtime(id:str,request:Request,session:Session=Depends(storage_db)):
    require(graph(session),id);return live(request,id)

@router.get("/pipelines/{id}/topology")
def topology(id:str,session:Session=Depends(storage_db)):
    g=graph(session);require(g,id);data=g.serialize();kind=g.graph.edges[id].kind
    data["edges"]=[e for e in data["edges"] if e["pipelineType"]==kind]
    ids={n for e in data["edges"] for n in (e["startNodeId"],e["endNodeId"])}
    data["nodes"]=[n for n in data["nodes"] if n["id"] in ids];data["valves"]=[v for v in data["valves"] if v["nodeId"] in ids]
    return data

@router.get("/pipelines/{id}/upstream")
def upstream(id:str,session:Session=Depends(storage_db)):
    g=graph(session);require(g,id);return g.get_upstream(id)

@router.get("/pipelines/{id}/downstream")
def downstream(id:str,session:Session=Depends(storage_db)):
    g=graph(session);require(g,id);return g.get_downstream(id)

@router.get("/pipelines/{id}/affected-buildings")
def affected(id:str,session:Session=Depends(storage_db)):
    g=graph(session);require(g,id);return g.get_affected_buildings(id)

@router.get("/pipelines/{id}/valves")
def valves(id:str,session:Session=Depends(storage_db)):
    g=graph(session);require(g,id);return g.get_valves_for_edge(id)

@router.post("/pipelines/{id}/isolation-options")
def isolation(id:str,session:Session=Depends(storage_db)):
    g=graph(session);require(g,id);return {"options":g.find_isolation_options(id),"method":"bounded valve enumeration; physical supply connectivity; no hydraulic model","executed":False}

@router.post("/simulation/valve/{id}/state")
async def control(id:str,body:ValveStateRequest,request:Request,session:Session=Depends(storage_db)):
    if get_settings().app_env!="development":raise HTTPException(404,"Development control unavailable")
    from app.services.valve_service import ValveService
    async with service(request).flood.lock:
        updated=ValveService.apply(session,{id:body.status})
        session.commit()
        state=service(request).engine.configure_pipelines(updated)
    g=graph(session)
    service(request).publish(state)
    affected=[]
    for kind in ("water","drainage","fire"):
        used={n for e in g.graph.edges.values() if e.kind==kind for n in (e.start,e.end)}
        affected.extend(g.graph.buildings(used-g.get_connected_nodes(kind)))
    return {"state":state,"affectedBuildings":affected}
