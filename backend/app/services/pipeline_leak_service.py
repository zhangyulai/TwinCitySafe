import asyncio,json,time
from copy import deepcopy
from collections import OrderedDict
from contextlib import suppress
from datetime import datetime,UTC
from hashlib import sha256
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from app.schemas.leak import LeakState
from app.services.pipeline_graph_service import PipelineGraphService
from app.services.valve_service import ValveService
from app.services.leak_detection_service import LeakDetectionService,LeakLocalizationService,unit
from app.models.leak import PipelineLeakEvent,PipelineLeakSnapshot,PipelineLeakIsolation
from simulator.leak_config import RISK_WEIGHTS,DETECTION_THRESHOLDS

class PipelineLeakService:
    def __init__(self,engine,factory,connections):
        self.engine=engine;self.factory=factory;self.connections=connections
        self.baseline={};self.previous={};self.previous_time=0;self.graph_service=None
        self.comparisons=OrderedDict();self.original_valves={};self.changed_valves=set()
        self.task=None;self.pending=OrderedDict();self.storage_available=True;self.last_error="";self.sent=0;self.event_sequence=0;self.sample_lock=asyncio.Lock()
        self.engine.leak_processor=self.process
    def load_graph(self):
        with self.factory() as db:return PipelineGraphService(db)
    @staticmethod
    def graph_hash(graph):
        payload={"nodes":[vars(n) for n in graph.nodes.values()],"edges":[vars(e) for e in graph.edges.values()],"valves":[vars(v) for v in graph.valves.values()]}
        return sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    def event(self,state,message):
        f=state.leak
        self.event_sequence+=1
        f.events.append({"sequence":self.event_sequence,"timestamp":datetime.now(UTC).isoformat(),"simulationTime":f.elapsed_simulation_seconds,"stage":f.current_stage,"message":message})
        f.events=f.events[-200:]
    async def start_scenario(self,body):
        e=self.engine
        if e._state.flood.scenario_id or e._state.leak.scenario_id:raise HTTPException(409,"当前已有事故场景，请先重置后再启动泄漏")
        if len(self.pending)>=50:raise HTTPException(503,"历史采样待写入过多，请恢复存储")
        g=await run_in_threadpool(self.load_graph)
        edge=g.graph.edges.get(body.pipeline_id)
        if not edge or edge.kind!="water":raise HTTPException(422,"需选择现有给水管段")
        if body.pipeline_id not in g.get_connected_edges("water"):raise HTTPException(409,"目标管段未连通供水，请先恢复阀门")
        # Capture observations and graph before injecting faults. Localization never receives target.
        e.configure_pipelines(g.graph);self.graph_service=g
        self.baseline={p.id:(p.pressure,p.flow) for p in e._state.pipelines if p.type=="water"}
        self.previous={};self.previous_time=0;self.comparisons.clear();self.sent=0;self.event_sequence=0
        self.original_valves={v.id:v.status for v in g.valves};self.changed_valves.clear()
        e._state.leak=LeakState(scenario_id=str(uuid4()),event_id=str(uuid4()),target_pipeline_id=body.pipeline_id,target_severity=body.severity,status="running")
        values=list(self.baseline.values())
        e._state.leak.upstream_pressure=e._state.leak.downstream_pressure=sum(p for p,q in values)/max(1,len(values))
        e._state.leak.pipeline_flow=sum(q for p,q in values)/max(1,len(values))
        e.pipelines.configure_leak(body.pipeline_id)
        self.event(e._state,"软件泄漏场景启动，观察全网压力与流量；注入目标仅用于演示真值")
        e.start();state=e._touch();await self.sample(state);return state
    def process(self,state):
        f=state.leak
        if not f.scenario_id or self.graph_service is None:return
        dt=f.elapsed_simulation_seconds-self.previous_time
        if dt<=0:return
        start=time.perf_counter();rank=LeakLocalizationService.rank(state.pipelines,self.baseline,self.engine.pipelines.graph)
        f.localization_latency_ms=(time.perf_counter()-start)*1000
        scored={}
        for p in state.pipelines:
            if p.type=="water" and p.id in self.baseline and p.status not in ("isolated","offline"):
                scored[p.id]=LeakDetectionService.score(p,self.baseline[p.id],self.previous.get(p.id),dt)
        last_top=f.suspected_segments[0]["pipeline_id"] if f.suspected_segments else None
        isolated=bool(f.execution and last_top and last_top in self.engine.pipelines.isolated)
        if not isolated:
            top=rank[0]["pipeline_id"] if rank else None
            score,factors,dp,dq=scored.get(top,(0,{},0,0))
            f.detection_score=score;f.confidence=score;f.detection_breakdown=factors
            f.pressure_drop_rate=dp;f.flow_change_rate=dq
            # Normal noise must not invent a suspect ranking in the UI.
            f.suspected_segments=rank if score>=DETECTION_THRESHOLDS[0] else []
            stage="HIGH" if score>=DETECTION_THRESHOLDS[2] else "CONFIRMED" if score>=DETECTION_THRESHOLDS[1] else "SUSPECTED" if score>=DETECTION_THRESHOLDS[0] else "NORMAL"
            if stage!=f.current_stage:
                f.current_stage=stage
                self.event(state,f"多变量异常匹配进入 {stage}"+(f"，首位疑似 {top}" if stage!="NORMAL" else ""))
            if score>=DETECTION_THRESHOLDS[0] and not f.detected_at:f.detected_at=datetime.now(UTC).isoformat()
            if score>=DETECTION_THRESHOLDS[1] and not f.confirmed_at:f.confirmed_at=datetime.now(UTC).isoformat()
            if score>=DETECTION_THRESHOLDS[1] and top:
                f.affected_buildings=self.graph_service.get_affected_buildings(top)
                impact=self.graph_service.get_downstream(top)
                f.affected_nodes=impact["nodes"];f.affected_edges=impact["edges"]
        top=f.suspected_segments[0]["pipeline_id"] if f.suspected_segments else None
        observed=next((p for p in state.pipelines if p.id==top),None)
        if observed:
            f.upstream_pressure=observed.inlet_pressure;f.downstream_pressure=observed.outlet_pressure
            f.pipeline_flow=observed.flow;f.estimated_leak_flow=max(0,observed.inlet_flow-observed.outlet_flow)
        else:
            # Before suspicion show network-wide mean observations, not the hidden target.
            values=[p for p in state.pipelines if p.type=="water"]
            f.upstream_pressure=f.downstream_pressure=sum(p.pressure for p in values)/max(1,len(values))
            f.pipeline_flow=sum(p.flow for p in values)/max(1,len(values));f.estimated_leak_flow=0
        initial_nodes=self.graph_service.get_connected_nodes("water")
        connected=self.engine.pipelines.graph.connected("water")[0]
        f.interrupted_buildings=self.graph_service.graph.buildings(initial_nodes-connected)
        f.service_status="INTERRUPTED" if f.interrupted_buildings else "DEGRADED" if f.confirmed_at else "AVAILABLE"
        total=len(self.graph_service.graph.buildings(initial_nodes))
        f.estimated_service_loss=len(f.interrupted_buildings)/max(1,total)
        if not isolated and observed:f.estimated_service_loss=max(f.estimated_service_loss,unit((.42-observed.pressure)/.42)*len(f.affected_buildings)/max(1,total))
        active_flow=unit(f.estimated_leak_flow/25)
        values={"leak_flow":active_flow,"pressure_loss":unit((.42-f.downstream_pressure)/.25)*active_flow,
                "affected_buildings":unit(len(f.affected_buildings)/5)*active_flow,
                "service_disruption":unit(f.estimated_service_loss),"growth":unit(f.flow_change_rate/10)*active_flow if not isolated else 0}
        f.risk_breakdown=[{"key":k,"normalizedValue":v,"weight":RISK_WEIGHTS[k],"points":100*v*RISK_WEIGHTS[k]} for k,v in values.items()]
        f.risk_score=sum(x["points"] for x in f.risk_breakdown)
        f.risk_level=["low","general","elevated","high","extreme"][sum(f.risk_score>=n for n in (20,40,60,80))]
        f.peak_detection_score=max(f.peak_detection_score,f.detection_score);f.peak_risk=max(f.peak_risk,f.risk_score)
        if f.detected_at:
            f.alarm={"id":"LEAK-"+f.scenario_id,"type":"PIPELINE_LEAK_CONFIRMED" if f.confirmed_at else "PIPELINE_LEAK_SUSPECTED","status":"active",
                     "level":f.risk_level,"peakDetectionScore":f.peak_detection_score,"peakRisk":f.peak_risk}
        if isolated:
            f.detection_score=unit(f.estimated_leak_flow/25);f.confidence=f.detection_score
            f.detection_breakdown={"residual_flow":f.detection_score}
            previous=self.previous.get(top)
            f.pressure_drop_rate=(previous[0]-observed.pressure)*60/dt if previous and observed else 0
            f.flow_change_rate=(observed.flow-previous[1])*60/dt if previous and observed else 0
            if f.estimated_leak_flow<.25 and f.current_stage!="STABILIZING":
                f.current_stage="STABILIZING";f.leak_status="CONTAINED"
                self.event(state,"泄漏受控，仍保留停水影响；事件未关闭")
            elif f.current_stage!="STABILIZING":f.current_stage="ISOLATING";f.leak_status="ISOLATING"
        else:f.leak_status="DETECTED" if f.confirmed_at else "MONITORING"
        self.previous={p.id:(p.pressure,p.flow) for p in state.pipelines};self.previous_time=f.elapsed_simulation_seconds
    def publish(self,state):
        f=state.leak
        if not f.scenario_id:self.sent=0;return
        for event in f.events:
            if event["sequence"]<=self.sent:continue
            self.connections.broadcast(json.dumps({"type":"PIPELINE_LEAK_EVENT","timestamp":event["timestamp"],"data":{"event_id":f.event_id,"scenario_id":f.scenario_id,"pipeline_id":f.suspected_segments[0]["pipeline_id"] if f.suspected_segments else None,**event}},ensure_ascii=False))
        self.sent=f.events[-1]["sequence"] if f.events else 0
    async def compare(self,pipeline_id):
        f=self.engine._state.leak
        if not f.scenario_id or not f.confirmed_at:raise HTTPException(409,"需先确认活动管网异常")
        if f.execution:raise HTTPException(409,"本事件已执行隔离；继续观察，不重复隔离")
        if not f.suspected_segments or pipeline_id!=f.suspected_segments[0]["pipeline_id"]:raise HTTPException(409,"仅针对当前首位疑似管段比较")
        start=time.perf_counter();g=await run_in_threadpool(self.load_graph)
        captured=self.engine.snapshot();f=captured.leak
        options=g.find_isolation_options(pipeline_id)
        total=len(g.graph.buildings(g.get_connected_nodes("water")))
        for option in options:
            option["estimatedServiceLoss"]=len(option["affectedBuildings"])/max(1,total)
        observations=[p.model_dump(mode="json",by_alias=True) for p in captured.pipelines if p.type=="water"]
        signature=self.graph_hash(g.graph)
        digest=sha256(json.dumps({"graph":signature,"suspect":pipeline_id,"observations":observations,"scenario":f.scenario_id},sort_keys=True).encode()).hexdigest()
        result={"id":str(uuid4()),"scenarioId":f.scenario_id,"pipelineId":pipeline_id,"graphRevision":signature,"stateHash":digest,
                "simulationTime":f.elapsed_simulation_seconds,"comparedAt":datetime.now(UTC).isoformat(),"observations":observations,"options":options,
                "latencyMs":(time.perf_counter()-start)*1000,"method":"M4 拓扑阀门边界枚举；服务损失为连接建筑比例，非水力预测，无自动最优方案"}
        def save():
            with self.factory() as db:
                db.add(PipelineLeakIsolation(id=result["id"],scenario_id=f.scenario_id,state_hash=digest,created_at=datetime.now(UTC),comparison_json=result,execution_json=None));db.commit()
        await run_in_threadpool(save)
        self.comparisons[result["id"]]=result
        while len(self.comparisons)>30:self.comparisons.popitem(last=False)
        return deepcopy(result)
    def validate_comparison(self,c,graph):
        f=self.engine._state.leak
        top=f.suspected_segments[0]["pipeline_id"] if f.suspected_segments else None
        if f.scenario_id!=c["scenarioId"] or top!=c["pipelineId"] or self.graph_hash(graph)!=c["graphRevision"] or f.execution or f.elapsed_simulation_seconds-c["simulationTime"]>60:
            raise HTTPException(409,{"code":"STALE_ISOLATION","message":"事故、疑似位置、阀门、拓扑或时刻已变化，请重新比较"})
        old={p["id"]:p for p in c["observations"]}
        if any(abs(p.pressure-old[p.id]["pressure"])>.03 or abs(p.flow-old[p.id]["flow"])>5 for p in self.engine._state.pipelines if p.id in old):
            raise HTTPException(409,{"code":"STALE_ISOLATION","message":"压力/流量已明显变化，请重新比较"})
    async def execute(self,body):
        if not body.confirmed_simulation:raise HTTPException(422,"仅作用于软件仿真，不控制真实阀门。")
        c=self.comparisons.get(body.comparison_id)
        if c is None:raise HTTPException(409,{"code":"STALE_ISOLATION","message":"比较已过期或服务已重启"})
        # Short database transaction runs on the event loop under the shared control lock:
        # no engine tick or another valve control may interleave validation/commit/live apply.
        with self.factory() as db:
            g=PipelineGraphService(db);self.validate_comparison(c,g.graph)
            old=next((x for x in c["options"] if x["id"]==body.option_id),None)
            current=next((x for x in g.find_isolation_options(c["pipelineId"]) if old and x["valves"]==old["valves"] and x["isolatedEdges"]==old["isolatedEdges"]),None)
            if current is None:raise HTTPException(409,"隔离候选已失效")
            graph=ValveService.apply(db,{v:"closed" for v in current["valves"]})
            x={"id":str(uuid4()),"comparisonId":c["id"],"optionId":body.option_id,"valves":current["valves"],"status":"applied","operator":"demo-user","timestamp":datetime.now(UTC).isoformat(),"affectedBuildings":current["affectedBuildings"]}
            record=db.get(PipelineLeakIsolation,c["id"])
            if record is None:raise HTTPException(409,"比较记录不存在")
            record.execution_json=x;db.commit()
        e=self.engine;e.configure_pipelines(graph);f=e._state.leak
        self.changed_valves.update(current["valves"]);f.execution=x;f.current_stage="ISOLATING";f.leak_status="ISOLATING"
        self.event(e._state,"用户确认软件隔离，已关闭 "+", ".join(current["valves"])+"；等待管内压力和泄漏流量衰减")
        return e._touch()
    async def reset(self):
        e=self.engine
        if e._state.leak.scenario_id:
            e.stop();await self.sample(e.snapshot(),"reset")
            with self.factory() as db:
                graph=ValveService.apply(db,{id:self.original_valves[id] for id in self.changed_valves})
                db.commit()
            e.configure_pipelines(graph)
        self.changed_valves.clear();self.comparisons.clear();self.baseline={};self.previous={};self.graph_service=None
        e.reset();e.start();return e.snapshot()
    def persist(self,state,status=None):
        f=state.leak
        if not f.scenario_id:return
        with self.factory() as db:
            r=db.get(PipelineLeakEvent,f.event_id)
            values=dict(scenario_id=f.scenario_id,pipeline_id=f.suspected_segments[0]["pipeline_id"] if f.suspected_segments else None,
                        detected_at=datetime.fromisoformat(f.detected_at) if f.detected_at else None,confirmed_at=datetime.fromisoformat(f.confirmed_at) if f.confirmed_at else None,
                        peak_detection_score=f.peak_detection_score,peak_risk=f.peak_risk,status=status or f.current_stage,state_json=f.model_dump(mode="json",by_alias=True))
            if r is None:db.add(PipelineLeakEvent(id=f.event_id,**values))
            else:
                for k,v in values.items():setattr(r,k,v)
            exists=db.scalar(select(PipelineLeakSnapshot.id).where(PipelineLeakSnapshot.scenario_id==f.scenario_id,PipelineLeakSnapshot.simulation_time==f.elapsed_simulation_seconds))
            if exists is None:db.add(PipelineLeakSnapshot(scenario_id=f.scenario_id,timestamp=state.timestamp,simulation_time=f.elapsed_simulation_seconds,pipeline_id=values["pipeline_id"],pressure=f.downstream_pressure,flow=f.pipeline_flow,leak_severity=f.leak_severity,detection_score=f.detection_score,risk_score=f.risk_score,top_suspects=f.suspected_segments,affected_count=len(f.affected_buildings)))
            db.commit()
    async def sample(self,state=None,status=None):
        async with self.sample_lock:
            await self._sample(state,status)
    async def _sample(self,state=None,status=None):
        state=state or self.engine.snapshot()
        if state.leak.scenario_id:self.pending[state.leak.scenario_id]=(state,status)
        for id,item in list(self.pending.items()):
            try:await run_in_threadpool(self.persist,*item)
            except Exception:self.storage_available=False;self.last_error="泄漏采样存储暂不可用，保留最新状态重试";return
            if self.pending.get(id) is item:self.pending.pop(id,None)
        self.storage_available=True;self.last_error=""
    async def startup(self):
        def interrupt():
            with self.factory() as db:
                for r in db.scalars(select(PipelineLeakEvent).where(PipelineLeakEvent.status.not_in(["reset","interrupted"]))):r.status="interrupted"
                db.commit()
        try:await run_in_threadpool(interrupt)
        except Exception:self.storage_available=False;self.last_error="请先执行 M8 migration"
        self.task=asyncio.create_task(self._run(),name="pipeline-leak-sampler")
    async def _run(self):
        while True:await asyncio.sleep(5);await self.sample()
    async def shutdown(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):await self.task
        await self.sample(status="interrupted")
