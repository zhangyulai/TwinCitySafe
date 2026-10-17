#!/usr/bin/env python3
"""Production build demo runtime: one worker, no reload, explicit demo controls."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ["APP_ENV"] = "production"
os.environ["DEMO_MODE"] = "true"
import uvicorn
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.backend_host, port=settings.backend_port, workers=1, reload=False)
