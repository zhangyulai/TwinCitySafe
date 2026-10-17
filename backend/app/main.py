import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from app.api.health import router as health_router
from app.api.devices import router as devices_router
from app.api.realtime import router as realtime_router, websocket_router
from app.services.realtime_service import RealtimeService
from app.core.config import get_settings
from app.core.database import check_database, engine

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await run_in_threadpool(check_database)
        logger.info("PostgreSQL connection verified")
    except SQLAlchemyError:
        # Do not log the connection URL or credentials.
        logger.warning("PostgreSQL unavailable. Check .env and run scripts/check-db.py. Health only checks API liveness.")
    realtime = RealtimeService()
    app.state.realtime = realtime
    await realtime.startup()
    try:
        yield
    finally:
        await realtime.shutdown()
        del app.state.realtime
        engine.dispose()

app = FastAPI(title="TwinCitySafe", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins,
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type", "Authorization"])
app.include_router(health_router, prefix="/api/v1")

app.include_router(realtime_router, prefix="/api/v1")
app.include_router(websocket_router)
app.include_router(devices_router, prefix="/api/v1")

from app.api.pipelines import router as pipelines_router
app.include_router(pipelines_router, prefix="/api/v1")

from app.api.flood import router as flood_router
app.include_router(flood_router, prefix="/api/v1")

from app.api.risk import router as risk_router
app.include_router(risk_router,prefix="/api/v1")

from app.api.emergency import router as emergency_router
app.include_router(emergency_router,prefix="/api/v1")

from app.api.leak import router as leak_router
app.include_router(leak_router,prefix="/api/v1")

from app.api.incidents import router as incidents_router
app.include_router(incidents_router,prefix='/api/v1')

from app.api.system import router as system_router
app.include_router(system_router, prefix="/api/v1")
