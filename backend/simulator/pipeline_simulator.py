from math import sin, sqrt
from simulator import leak_config as leak_cfg

from app.schemas.realtime import PipelineState
from simulator.config import relax


class PipelineSimulator:
    def __init__(self):
        self.graph = None
        self.isolated = set()
        self.asset_status = {}
        self.leak_upstream=set();self.leak_downstream=set();self.leak_target=None

    def configure(self, graph):
        self.graph = graph
        self.asset_status = {e.id:e.status for e in graph.edges.values()}
        self.recalculate()

    def recalculate(self):
        if self.graph is None: return
        connected=set()
        for kind in ("water", "drainage", "fire"):
            connected.update(self.graph.connected(kind)[1])
        self.isolated=set(self.graph.edges)-connected

    def configure_leak(self,target):
        from algorithm.graph_search.traversal import trace
        self.leak_target=target
        self.leak_upstream=set(trace(self.graph,target,"upstream")["edges"]) if target else set()
        self.leak_downstream=set(trace(self.graph,target,"downstream")["edges"]) if target else set()

    def tick(self, pipelines: list[PipelineState], rainfall: float, pump_capacity: float, time: float, dt: float, leak=None) -> None:
        active=bool(leak and leak.scenario_id)
        if active:
            leak.elapsed_simulation_seconds+=dt
            leak.leak_severity=leak.target_severity*min(1,max(0,(leak.elapsed_simulation_seconds-leak_cfg.WARMUP_SECONDS)/leak_cfg.RAMP_SECONDS))
            leak.leak_coefficient=leak_cfg.LEAK_COEFFICIENT*leak.leak_severity
        target=next((p for p in pipelines if p.id==self.leak_target),None)
        leak_flow=leak.leak_coefficient*sqrt(max(target.pressure,0)) if active and target else 0
        for pipeline in pipelines:
            if pipeline.type == "water":
                pressure, flow = 0.42 + 0.006 * sin(time / 36), 28 + 0.8 * sin(time / 44)
            elif pipeline.type == "drain":
                pressure = 0.08 + 0.002 * sin(time / 42)
                flow = 20 + rainfall * 0.25 + (pump_capacity - 1) * 2.2 + 0.3 * sin(time / 51)
            else:
                pressure, flow = 0.48 + 0.004 * sin(time / 40), 2 + 0.05 * sin(time / 39)
            inlet_pressure=pressure;outlet_pressure=pressure;inlet_flow=flow;outlet_flow=flow
            if active and pipeline.type=="water" and self.leak_target not in self.isolated:
                severity=leak.leak_severity
                if pipeline.id==self.leak_target:
                    inlet_pressure=pressure*(1-.25*severity);outlet_pressure=pressure*(1-.65*severity)
                    outlet_flow=flow*(1-.3*severity);inlet_flow=outlet_flow+leak_flow
                    pressure=outlet_pressure;flow=inlet_flow
                elif pipeline.id in self.leak_downstream:
                    pressure*=1-.5*severity;flow*=1-.3*severity
                    inlet_pressure=outlet_pressure=pressure;inlet_flow=outlet_flow=flow
                elif pipeline.id in self.leak_upstream:
                    pressure*=1-.15*severity;flow+=leak_flow*.8
                    inlet_pressure=outlet_pressure=pressure;inlet_flow=outlet_flow=flow
            if pipeline.id in self.isolated:
                pressure=flow=inlet_pressure=outlet_pressure=inlet_flow=outlet_flow=0
            pipeline.inlet_pressure=relax(pipeline.inlet_pressure,inlet_pressure,dt,16)
            pipeline.outlet_pressure=relax(pipeline.outlet_pressure,outlet_pressure,dt,16)
            pipeline.inlet_flow=relax(pipeline.inlet_flow,inlet_flow,dt,16)
            pipeline.outlet_flow=relax(pipeline.outlet_flow,outlet_flow,dt,16)
            pipeline.status = self.asset_status.get(pipeline.id, "normal")
            if pipeline.status == "normal" and pipeline.id in self.isolated: pipeline.status = "isolated"
            pipeline.pressure = relax(pipeline.pressure, pressure, dt, 16)
            pipeline.flow = relax(pipeline.flow, flow, dt, 16)
