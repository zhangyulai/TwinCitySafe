from typing import Literal
from pathlib import Path
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

PROJECT_ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")
    app_env: Literal["development", "production"] = "development"
    demo_mode: bool = False
    anomaly_model_path: str = ""
    risk_model_dir: str = ""
    frontend_port: int = Field(default=5173, ge=1, le=65535)
    telemetry_sample_interval_seconds: float = Field(default=5, ge=5, le=3600)
    database_url: str = ""
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5433, ge=1, le=65535)
    postgres_db: str = "twincitysafe"
    postgres_user: str = "twincity"
    postgres_password: str = ""
    backend_host: str = "127.0.0.1"
    backend_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def sqlalchemy_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        # URL.create safely handles special characters in database passwords.
        return URL.create("postgresql+psycopg", username=self.postgres_user, password=self.postgres_password,
                          host=self.postgres_host, port=self.postgres_port, database=self.postgres_db)

@lru_cache
def get_settings() -> Settings:
    return Settings()
