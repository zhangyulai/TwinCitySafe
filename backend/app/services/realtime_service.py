from pathlib import Path
from app.schemas.realtime import ParkRealtimeState
from app.websocket.manager import ConnectionManager
from app.websocket.messages import realtime_message
from simulator.engine import SimulationEngine
from app.services.operation_service import OperationService
from app.services.telemetry_service import TelemetrySamplingService
from app.core.config import get_settings


class RealtimeService:
    def __init__(self) -> None:
        self.engine = SimulationEngine()
        self.connections = ConnectionManager()
        settings = get_settings()
        if settings.anomaly_model_path:
            from app.services.anomaly_service import AnomalyDetectionService
            self.operation = OperationService(self.engine.devices, AnomalyDetectionService(Path(settings.anomaly_model_path)))
        else:
            self.operation = OperationService(self.engine.devices)
        self.engine.processor = self.operation.process
        self.telemetry = TelemetrySamplingService(self.engine, self.operation, get_settings().telemetry_sample_interval_seconds)
        from app.services.flood_service import FloodService
        from app.services.flood_storage_service import FloodStorageService
        self.flood=FloodService(self.engine)
        self.flood_storage=FloodStorageService(self.engine,self.telemetry.session_factory)
        from app.services.risk_prediction_service import RiskPredictionService
        self.risk=RiskPredictionService(self.engine,self.telemetry.session_factory,
            model_dir=Path(settings.risk_model_dir) if settings.risk_model_dir else None)
        from app.services.emergency_service import EmergencyService
        self.emergency=EmergencyService(self.engine,self.telemetry.session_factory,self.connections)
        from app.services.pipeline_leak_service import PipelineLeakService
        self.leak=PipelineLeakService(self.engine,self.telemetry.session_factory,self.connections)
        from app.services.incident_runtime_service import IncidentRuntimeService
        self.incidents=IncidentRuntimeService(self)

    def publish(self, state: ParkRealtimeState) -> None:
        self.risk.evaluation.observe(state)
        self.connections.broadcast(realtime_message(state))
        self.emergency.observe(state)
        self.leak.publish(state)
        self.incidents.observe(state)

    async def startup(self) -> None:
        await self.telemetry.start()
        from starlette.concurrency import run_in_threadpool
        from app.services.pipeline_graph_service import PipelineGraphService
        from sqlalchemy.exc import SQLAlchemyError
        import logging
        def load():
            with self.telemetry.session_factory() as session:
                return PipelineGraphService(session).graph
        try:
            graph = await run_in_threadpool(load)
            if graph.edges: self.engine.configure_pipelines(graph)
        except SQLAlchemyError:
            logging.getLogger("uvicorn.error").warning("Pipeline storage unavailable; run M4 migration and seed")
        def load_ratings():
            from sqlalchemy import select
            from app.models import Device
            with self.telemetry.session_factory() as session:
                return {d.id:d.rated_capacity for d in session.scalars(select(Device)) if d.device_type=="pump"}
        try:self.engine.flood.rated_capacities.update(await run_in_threadpool(load_ratings))
        except SQLAlchemyError:pass
        await self.flood_storage.start()
        self.operation.process(self.engine._state, 0)
        await self.risk.start()
        await self.emergency.start()
        await self.leak.startup()
        await self.incidents.start()
        self.engine.launch(self.publish)

    async def shutdown(self) -> None:
        await self.engine.shutdown()
        await self.incidents.shutdown()
        await self.leak.shutdown()
        await self.emergency.shutdown()
        await self.risk.shutdown()
        await self.telemetry.shutdown()
        await self.flood_storage.shutdown()
        await self.connections.shutdown()
