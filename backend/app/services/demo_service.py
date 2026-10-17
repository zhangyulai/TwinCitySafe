"""Competition controls reuse the M3–M9 services; never select a response plan."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from app.models.pipeline import Valve
from app.schemas.flood import FloodScenarioRequest
from app.schemas.leak import LeakStart
from app.services.pipeline_graph_service import PipelineGraphService

DEMO_VALVE_IDS = tuple(f"V-{kind}-{i:02}" for kind, count in (("W", 3), ("D", 3), ("F", 4)) for i in range(1, count + 1))


class DemoService:
    def __init__(self, realtime):
        self.rt = realtime

    def inspect_assets(self):
        with self.rt.telemetry.session_factory() as db:
            graph = PipelineGraphService(db)
            if not graph.edges or not set(DEMO_VALVE_IDS).issubset(graph.graph.valves):
                raise HTTPException(503, "演示管网资产不完整，请执行 prepare-demo.sh")
            return graph.graph

    def open_demo_valves(self):
        with self.rt.telemetry.session_factory() as db:
            for valve in db.scalars(select(Valve).where(Valve.id.in_(DEMO_VALVE_IDS))):
                valve.status = "open"
                valve.open_percentage = 100
            db.flush()
            graph = PipelineGraphService(db).graph
            db.commit()
            return graph

    async def _reset_locked(self):
        rt, engine = self.rt, self.rt.engine
        try:
            await run_in_threadpool(self.inspect_assets)
        except SQLAlchemyError:
            raise HTTPException(503, "数据库不可用，演示状态未重置") from None
        engine.stop()
        if engine._state.flood.scenario_id:
            await rt.flood_storage.archive(reset=True)
            rt.emergency.observe(engine.snapshot())
            await rt.emergency.flush()
            await rt.risk.flush()
        if engine._state.leak.scenario_id:
            await rt.leak.sample(engine.snapshot(), "reset")
        await rt.incidents.abort_current("比赛演示重置，历史档案保留，未正式关闭")
        await rt.incidents.flush(strict=True)
        try:
            graph = await run_in_threadpool(self.open_demo_valves)
        except SQLAlchemyError:
            raise HTTPException(503, "阀门恢复未完成，演示已暂停；请恢复数据库后重试") from None
        # M9 close retains physical effects; only this explicitly confirmed reset restores them.
        rt.leak.changed_valves.clear()
        rt.leak.comparisons.clear()
        rt.leak.baseline.clear()
        rt.leak.previous.clear()
        rt.leak.graph_service = None
        engine.configure_pipelines(graph)
        engine.reset()
        engine.set_speed(1)
        state = engine.start()
        rt.publish(state)
        await rt.risk.flush()
        return state

    async def reset(self):
        async with self.rt.flood.lock:
            return await self._reset_locked()

    async def start(self, scenario):
        rt = self.rt
        async with rt.flood.lock:
            if rt.engine._state.flood.scenario_id or rt.engine._state.leak.scenario_id:
                raise HTTPException(409, "当前已有活动事故，请先完成关闭或确认重置；不能同时演示两个事故")
            await self._reset_locked()
            if scenario == "flood":
                state = rt.flood.start(FloodScenarioRequest(scenario="extreme_rain", duration_minutes=60,
                                                           rainfall_recession=True), linked=True)
                await rt.flood_storage.sample(state)
            else:
                state = await rt.leak.start_scenario(LeakStart())
            state = rt.engine.set_speed(10)
            rt.publish(state)
            await rt.incidents.flush(strict=True)
            return state
