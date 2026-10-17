"""Every test uses an isolated database; never mutate the running demo's PostgreSQL."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.models import Base
from app.services.seed_service import seed_devices
from app.services.telemetry_service import TelemetrySamplingService
from app.api.devices import storage_db
from app.main import app

@pytest.fixture(autouse=True)
def isolated_storage(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)  # Test-only ephemeral storage; production uses Alembic.
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed_devices(session)
    original = TelemetrySamplingService.__init__
    def init(self, *args, **kwargs):
        kwargs["session_factory"] = factory
        original(self, *args, **kwargs)
    monkeypatch.setattr(TelemetrySamplingService, "__init__", init)
    monkeypatch.setattr("app.main.check_database", lambda: None)
    def get_session():
        with factory() as session:
            yield session
    app.dependency_overrides[storage_db] = get_session
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()
