import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.database import SessionLocal
from app.services.seed_service import seed_devices
if __name__ == "__main__":
    with SessionLocal() as session:
        print(f"Seed complete: {seed_devices(session)} new devices; existing records preserved.")
