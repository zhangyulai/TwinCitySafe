#!/usr/bin/env python3
"""Offline, idempotent local preparation. Never train models, reset state or erase history."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import select
from app.core.database import SessionLocal, check_database, engine
from app.core.config import get_settings
from app.models.emergency import EmergencyPlanTemplate
from app.models.pipeline import Valve
from app.services.emergency_plan_service import default_templates
from app.services.seed_service import seed_devices
from app.services.pipeline_seed import seed_pipelines
from app.services.readiness_service import storage_readiness
from app.services.anomaly_service import AnomalyDetectionService
from algorithm.risk_prediction.inference import RiskModels


def inspect():
    config = Config(str(ROOT / "backend/alembic.ini"))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    database, graph = storage_readiness(SessionLocal)
    settings = get_settings()
    anomaly = AnomalyDetectionService(Path(settings.anomaly_model_path)) if settings.anomaly_model_path else AnomalyDetectionService()
    risk = RiskModels(Path(settings.risk_model_dir)) if settings.risk_model_dir else RiskModels()
    with SessionLocal() as db:
        valves = list(db.scalars(select(Valve)))
        templates = list(db.scalars(select(EmergencyPlanTemplate)))
    core = database["available"] and graph["available"] and current == expected and len(templates) >= 3
    return {"core_ready": bool(core), "ready": bool(core and anomaly.available and risk.available),
        "database": database, "pipeline_graph": graph,
        "migration": {"available": current == expected, "current": sorted(current), "expected": sorted(expected)},
        "models": {"anomaly_available": anomaly.available, "risk_available": risk.available,
                   "risk_model_count": len(risk.models), "dataset_size": risk.metadata.get("dataset_size")},
        "demo_state": {"valves_open": all(v.status == "open" for v in valves),
                       "valve_count": len(valves), "plan_count": len(templates),
                       "message": "只检查数据库资产；活动事故与实时设备请在页面执行系统自检。不会自动重置。"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Read-only checks; do not migrate or seed")
    parser.add_argument("--json", action="store_true", help="Print structured results")
    args = parser.parse_args()
    if not (ROOT / ".env").is_file():
        print("Missing .env. Copy .env.example to .env and configure the local database.", file=sys.stderr)
        return 1
    try:
        check_database()
        if not args.check_only:
            command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")
            with SessionLocal() as db:
                devices = seed_devices(db)
                pipelines = seed_pipelines(db)
                plans = 0
                for template in default_templates():
                    if db.get(EmergencyPlanTemplate, template["id"]) is None:
                        db.add(EmergencyPlanTemplate(**template)); plans += 1
                db.commit()
            if not args.json:
                print(f"Seed complete: {devices} new devices; {pipelines}; {plans} new plans. Existing assets/history preserved.")
        result = inspect()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("Database Ready" if result["database"]["available"] else "Database Unavailable")
            print("Migration Ready" if result["migration"]["available"] else "Migration Outdated: run ./prepare-demo.sh")
            print("Models Ready" if all(result["models"][key] for key in ("anomaly_available", "risk_available")) else
                  "Models Degraded: physical simulation remains available; restore the supplied model artifacts. No automatic training.")
            graph = result["pipeline_graph"]
            print(f"Assets: {graph.get('device_count', 0)} devices, {graph.get('node_count', 0)} nodes, {graph.get('edge_count', 0)} pipelines, {graph.get('valve_count', 0)} valves")
            if not result["demo_state"]["valves_open"]:
                print("Demo state retains closed valves. Use confirmed Demo Reset before a new presentation; history is retained.")
        return 0 if result["core_ready"] else 1
    except Exception as error:
        # Raw connection exception text may contain credentials.
        print(f"Preparation failed ({type(error).__name__}). Check database connectivity, dependencies and migration logs.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
