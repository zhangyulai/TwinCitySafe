from fastapi import APIRouter
from app.schemas.health import HealthResponse
from app.services.health_service import get_health

router = APIRouter()

@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    # Liveness endpoint; database readiness is checked by scripts/check-db.py.
    return get_health()
