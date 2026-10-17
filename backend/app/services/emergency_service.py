"""Bounded comparisons, durable action logs and one shared realtime event channel."""
import asyncio, json, time, logging
from collections import OrderedDict, deque
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, UTC
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from app.models.emergency import EmergencyPlanTemplate, EmergencyComparison, EmergencyExecution, EmergencyExecutionStep
from app.schemas.emergency import EmergencyExecutionState
from app.services.emergency_execution_service import EmergencyExecutionEngine
from app.services.emergency_plan_service import default_templates, EmergencyPlanMatchService, EmergencyPlanSimulationService, key_state, baseline_signature

class EmergencyService:
    def __init__(self,engine,factory,connections):
        self.engine=engine;self.factory=factory;self.connections=connections
        self.comparisons=OrderedDict();self.dirty=OrderedDict();self.last=None;self.sent={};self.task=None
        self.lock=asyncio.Lock();self.compare_lock=asyncio.Lock();self.latencies=deque(maxlen=100)
        self.storage_available=True;self.last_error=""
    def load_templates(self):
        with self.factory() as db:
            return [{"id":r.id,"plan_code":r.plan_code,"name":r.name,"description":r.description,
                     "scenario_type":r.scenario_type,"actions":deepcopy(r.actions),"enabled":r.enabled}
                    for r in db.scalars(select(EmergencyPlanTemplate).order_by(EmergencyPlanTemplate.plan_code))]
    def initialize(self):
        with self.factory() as db:
            for p in default_templates():
                if db.get(EmergencyPlanTemplate,p["id"]) is None:db.add(EmergencyPlanTemplate(**p))
            for r in db.scalars(select(EmergencyExecution).where(EmergencyExecution.status.in_(["pending","executing"]))):
                x=deepcopy(r.state_json);x["status"]="failed";x["phase"]="FAILED"
                for st in x["steps"]:
                    if st["status"] in ("pending","executing"):st["status"]="cancelled";st["message"]="服务重启中断；不自动重新控制"
                x["events"].append({"sequence":len(x["events"])+1,"timestamp":datetime.now(UTC).isoformat(),"simulation_time":None,"message":"服务重启，执行中断","step":None,"status":"failed"})
                r.state_json=x;r.status="failed"
                for st in x["steps"]:
                    row=db.get(EmergencyExecutionStep,f"{r.id}:{st['index']}")
                    if row:row.status=st["status"];row.state_json=st
            db.commit()
    async def start(self):
        try:await run_in_threadpool(self.initialize)
        except Exception:self.storage_available=False;self.last_error="应急存储未就绪，请执行迁移"
        self.task=asyncio.create_task(self._run(),name="emergency-log-writer")
    async def shutdown(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):await self.task
        await self.flush()
    async def plans(self,scenario_type="flood"):
        try:plans=await run_in_threadpool(self.load_templates)
        except Exception:raise HTTPException(503,"应急模板存储不可用") from None
        return EmergencyPlanMatchService.match(self.engine,[p for p in plans if p["scenario_type"]==scenario_type])
    def assert_valid(self,frame,plan):
        reasons=EmergencyPlanMatchService.reasons(frame,plan)
        if reasons:raise HTTPException(409,{"code":"PLAN_UNAVAILABLE","reasons":reasons})
    async def compare(self,codes,horizon=30):
        if len(set(codes))!=len(codes):raise HTTPException(422,"方案代码不能重复")
        async with self.compare_lock:
            templates={p["plan_code"]:p for p in await self.plans()}
            if any(c not in templates for c in codes):raise HTTPException(404,"方案不存在，Baseline 不可执行")
            from algorithm.risk_prediction.simulation import SimulationCopy
            base=SimulationCopy(self.engine)
            for c in codes:self.assert_valid(base,templates[c])
            started=time.perf_counter();captured=datetime.now(UTC)
            def calculate():
                baseline=EmergencyPlanSimulationService.rollout(base,None,horizon)
                results=[EmergencyPlanSimulationService.rollout(base,templates[c],horizon) for c in codes]
                for r in results:
                    r["risk_reduction"]=baseline["final_risk_score"]-r["final_risk_score"]
                    r["water_reduction"]=baseline["final_water_level"]-r["final_water_level"]
                return baseline,results
            baseline,results=await run_in_threadpool(calculate)
            data={"id":str(uuid4()),"scenario_id":base._state.flood.scenario_id,"session_id":base._state.session_id,
                  "compared_at":captured.isoformat(),"baseline_timestamp":base._state.timestamp.isoformat(),
                  "baseline_simulation_time":base._state.flood.elapsed_simulation_seconds,"baseline_state_hash":baseline_signature(base),
                  "based_on_revision":base._state.revision,"horizon_minutes":horizon,"baseline":baseline,"results":results,
                  "key_state":key_state(base),"rainfall":base._state.weather.rainfall,"water_level":base._state.flood.water_level,
                  "plans":{c:templates[c] for c in codes},"compare_latency_ms":(time.perf_counter()-started)*1000,
                  "assumption":"同一基线、同一降雨计划；维持当前泵和故障演化。封控仅降低人员暴露、不移除现有车辆或水量。",
                  "rainfall_plan":"30–35 min 雨势从 100 回落到 20 mm/h" if base._state.flood.rainfall_recession else "原 M5 降雨计划，极端雨持续 100 mm/h",
                  "cost_definition":"P01/P02 每运行仿真分钟各 1 指数（含启动），新增入口封控 10 固定指数；不是金额。",
                  "response_definition":"首次严格低于阈值的时间，5 仿真秒采样；起点已低于阈值为 0，30 min 内未达为 null。"}
            def save():
                with self.factory() as db:
                    db.add(EmergencyComparison(id=data["id"],scenario_id=data["scenario_id"],baseline_state_hash=data["baseline_state_hash"],compared_at=captured,horizon=horizon,results_json=data));db.commit()
            try:await run_in_threadpool(save)
            except Exception:raise HTTPException(503,"推演已计算但保存失败，请重试") from None
            self.comparisons[data["id"]]=data
            while len(self.comparisons)>30:self.comparisons.popitem(last=False)
            self.latencies.append(data["compare_latency_ms"])
            return {**deepcopy(data),"stale":self.is_stale(data)}
    def is_stale(self,data):
        f=self.engine._state.flood
        age=f.elapsed_simulation_seconds-data["baseline_simulation_time"]
        return (key_state(self.engine)!=data["key_state"] or age<0 or age>30 or
                abs(self.engine._state.weather.rainfall-data["rainfall"])>5 or abs(f.water_level-data["water_level"])>.5)
    def save_execution(self,x):
        data=x.model_dump(mode="json")
        with self.factory() as db:
            r=db.get(EmergencyExecution,x.id)
            if r is None:
                r=EmergencyExecution(id=x.id,scenario_id=x.scenario_id,comparison_id=x.comparison_id,plan_code=x.plan_code,operator=x.operator,status=x.status,started_at=x.started_at,state_json=data);db.add(r);db.flush()
            else:r.status=x.status;r.state_json=data
            for st in x.steps:
                row=db.get(EmergencyExecutionStep,f"{x.id}:{st.index}")
                if row is None:db.add(EmergencyExecutionStep(id=f"{x.id}:{st.index}",execution_id=x.id,step_index=st.index,status=st.status,state_json=st.model_dump(mode="json")))
                else:row.status=st.status;row.state_json=st.model_dump(mode="json")
            db.commit()
    async def execute(self,body):
        if not body.confirmed_simulation:raise HTTPException(422,"需确认：当前操作仅作用于软件仿真环境，不控制真实设备。")
        async with self.lock:
            data=self.comparisons.get(body.comparison_id)
            if data is None:raise HTTPException(409,{"code":"STALE_COMPARISON","message":"推演已过期或服务已重启，请重新推演。"})
            templates={p["plan_code"]:p for p in await self.plans()}
            plan=templates.get(body.plan_code)
            if not plan or body.plan_code not in data["plans"]:raise HTTPException(404,"方案不属于本次推演")
            if plan!=data["plans"][body.plan_code] or self.is_stale(data):raise HTTPException(409,{"code":"STALE_COMPARISON","message":"当前状态已变化，建议重新推演。"})
            self.assert_valid(self.engine,plan)
            if len(self.dirty)>=100:raise HTTPException(503,"执行日志待写入过多，请恢复存储后重试")
            x=EmergencyExecutionEngine.create(self.engine._state,plan,data["id"])
            x.events.append({"sequence":1,"timestamp":data["compared_at"],"simulation_time":data["baseline_simulation_time"],
                "message":f"推演基线风险 {data['baseline']['timeline'][0]['risk_score']:.1f}，候选方案已生成（比较 {data['id'][:8]}）", "step":None,"status":"plan_generated"})
            EmergencyExecutionEngine.event(x,self.engine._state,f"{body.plan_code} 已选择并确认，等待仿真时钟执行")
            try:await run_in_threadpool(self.save_execution,x)
            except Exception:raise HTTPException(503,"执行记录保存失败，未施加动作") from None
            # Storage await can yield to the engine; validate again immediately before committing live state.
            if self.is_stale(data):
                EmergencyExecutionEngine.cancel(x,self.engine._state,"保存期间状态变化，取消未施加的动作");self.dirty[x.id]=x
                raise HTTPException(409,{"code":"STALE_COMPARISON","message":"保存期间状态变化，请重新推演"})
            try:self.assert_valid(self.engine,plan)
            except HTTPException:
                EmergencyExecutionEngine.cancel(x,self.engine._state,"保存期间资源变化，未施加动作")
                self.dirty[x.id]=x
                raise
            x.simulation_started_at=self.engine._state.flood.elapsed_simulation_seconds
            self.engine._state.emergency=x
            self.engine._touch()
            return x.model_dump(mode="json")
    def observe(self,state):
        current=state.emergency
        if self.last and (not current or current.id!=self.last.id):
            if self.last.status in ("pending","executing"):
                EmergencyExecutionEngine.cancel(self.last,state,"场景重置或替换，未完成动作中断；历史保留")
            self.dirty[self.last.id]=self.last.model_copy(deep=True)
            self.sent.pop(self.last.id,None)
        if current:
            previous=self.sent.get(current.id,0)
            for event in current.events[previous:]:
                self.connections.broadcast(json.dumps({"type":"EMERGENCY_EVENT","timestamp":event["timestamp"],"data":{
                    "execution_id":current.id,"scenario_id":current.scenario_id,"plan_code":current.plan_code,**event}},ensure_ascii=False))
            self.sent[current.id]=len(current.events)
            if self.last is None or current!=self.last:self.dirty[current.id]=current.model_copy(deep=True)
            if state.flood.status=="completed" and current.status in ("pending","executing"):
                EmergencyExecutionEngine.cancel(self.engine._state.emergency,state,"演示时长已结束，未完成步骤中断")
                self.dirty[current.id]=self.engine._state.emergency.model_copy(deep=True)
        self.last=current.model_copy(deep=True) if current else None
    async def flush(self):
        for id,x in list(self.dirty.items()):
            try:await run_in_threadpool(self.save_execution,x)
            except Exception:
                self.storage_available=False;self.last_error="日志存储暂不可用，保留有界待写记录";return
            if self.dirty.get(id)==x:self.dirty.pop(id,None)
        self.storage_available=True;self.last_error=""
    async def _run(self):
        while True:
            await asyncio.sleep(1);await self.flush()
    async def get_execution(self,id):
        x=self.engine._state.emergency
        if x and x.id==id:return x.model_dump(mode="json")
        if id in self.dirty:return self.dirty[id].model_dump(mode="json")
        def load():
            with self.factory() as db:
                r=db.get(EmergencyExecution,id);return deepcopy(r.state_json) if r else None
        data=await run_in_threadpool(load)
        if data is None:raise HTTPException(404,"执行记录不存在")
        return data
    async def cancel(self,id):
        async with self.lock:
            x=self.engine._state.emergency
            if not x or x.id!=id:raise HTTPException(404,"没有对应的活动执行")
            if x.status not in ("pending","executing"):raise HTTPException(409,"该执行已结束")
            EmergencyExecutionEngine.cancel(x,self.engine._state)
            self.engine._touch();return x.model_dump(mode="json")
