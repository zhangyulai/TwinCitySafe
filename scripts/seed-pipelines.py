import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.database import SessionLocal
from app.services.pipeline_seed import seed_pipelines
with SessionLocal() as session:
    print(seed_pipelines(session))
