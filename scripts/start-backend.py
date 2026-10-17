import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import uvicorn
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.backend_host, port=settings.backend_port,
                reload=True, reload_dirs=[str(Path(__file__).resolve().parents[1] / "backend" / folder) for folder in ("app", "simulator")])
