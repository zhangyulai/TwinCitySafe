"""Read-only checks. A running publisher is not a client WebSocket handshake."""
from datetime import UTC, datetime
from sqlalchemy import select, text, func
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import get_settings
from app.models import Device
from app.services.pipeline_graph_service import PipelineGraphService


def component(available, message, **details):
    return {"available": bool(available), "status": "ready" if available else "unavailable",
            "message": message, **details}


def storage_readiness(factory):
    database = component(False, "数据库连接不可用，请检查本地 PostgreSQL")
    graph = component(False, "管网资产不可用，请执行 prepare-demo.sh")
    try:
        with factory() as db:
            db.execute(text("SELECT 1"))
            database = component(True, "数据库只读检查通过")
            asset = PipelineGraphService(db)
            validation = asset.graph.validate()
            valid = bool(asset.nodes and asset.edges and asset.valves) and not any(
                validation[key] for key in ("invalidEdges", "duplicateIds", "isolatedNodes"))
            graph = component(valid, "数据库管网拓扑有效" if valid else "管网资产缺失或拓扑无效",
                node_count=len(asset.nodes), edge_count=len(asset.edges), valve_count=len(asset.valves),
                device_count=db.scalar(select(func.count()).select_from(Device)), validation=validation)
    except SQLAlchemyError:
        pass  # Never expose connection URLs, credentials or raw DB exceptions.
    return database, graph


def system_readiness(realtime):
    settings = get_settings()
    if realtime is None:
        checks = {name: component(False, "实时服务尚未启动") for name in (
            "database", "websocket", "anomaly_model", "risk_model", "pipeline_graph")}
    else:
        database, graph = storage_readiness(realtime.telemetry.session_factory)
        task = realtime.engine._task
        publisher = bool(task and not task.done())
        anomaly, risk = realtime.operation.anomaly, realtime.risk.models
        loaded_graph = realtime.engine.pipelines.graph
        graph["runtime_loaded"] = bool(loaded_graph and loaded_graph.edges)
        if not graph["runtime_loaded"]:
            graph.update(available=False, status="unavailable", message="数据库管网或实时图尚未加载")
        checks = {
            "database": database,
            "websocket": component(publisher, "服务端实时发布任务运行中；浏览器连接须由客户端确认" if publisher else "实时发布任务未运行",
                active_connections=realtime.connections.connection_count, publisher_running=publisher, path="/ws/realtime"),
            "anomaly_model": component(anomaly.available, "设备异常模型已加载" if anomaly.available else "设备异常模型不可用；设备观测与健康规则保留",
                model="Isolation Forest", version=anomaly.artifact.get("version") if anomaly.available else None),
            "risk_model": component(risk.available, "六个风险模型已加载并校验" if risk.available else "机器学习预测不可用；暴雨物理预测仍可运行",
                model="XGBoost", model_count=len(risk.models), dataset_size=risk.metadata.get("dataset_size")),
            "pipeline_graph": graph,
        }
    checks["backend"] = component(True, "API 已响应", version="1.0.0")
    core_ready = all(checks[name]["available"] for name in ("backend", "database", "websocket", "pipeline_graph"))
    ready = all(value["available"] for value in checks.values())
    return {"ready": ready, "core_ready": core_ready, "degraded": core_ready and not ready,
        "demo_enabled": settings.app_env == "development" or settings.demo_mode,
        "checked_at": datetime.now(UTC).isoformat(), **checks}
