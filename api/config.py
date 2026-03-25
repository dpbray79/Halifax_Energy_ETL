"""
config.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy Forecasting API — Configuration Module
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Loads configuration from environment variables using Pydantic Settings
"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables"""

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Halifax Energy Forecasting API"
    app_version: str = "1.0.0"
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_reload: bool = Field(default=True, alias="API_RELOAD")

    # ── Database ──────────────────────────────────────────────────────────────
    # Uses Supabase PostgreSQL — set DATABASE_URL in environment/Vercel settings
    # Format: postgresql://postgres.[project]:[password]@[host]:6543/postgres
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:password@localhost:5432/halifaxenergy",
        alias="DATABASE_URL"
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        alias="CORS_ORIGINS"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # ── Scheduler ─────────────────────────────────────────────────────────────
    ccei_poll_time: str = Field(default="06:00", alias="CCEI_POLL_TIME")
    model_retrain_cron: str = Field(default="0 4 * * *", alias="MODEL_RETRAIN_CRON")

    # ── R Model ───────────────────────────────────────────────────────────────
    r_script_path: str = Field(default="./model/HalifaxEnergy_Model.R", alias="R_SCRIPT_PATH")
    rscript_bin: str = Field(default="Rscript", alias="RSCRIPT_BIN")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="./logs/halifaxenergy.log", alias="LOG_FILE")

    # ── GeoJSON ───────────────────────────────────────────────────────────────
    geojson_zones_path: str = Field(
        default="./data/geojson/halifax_zones.geojson",
        alias="GEOJSON_ZONES_PATH"
    )

    # ── Model Config ─────────────────────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()


# ── Path Helpers ──────────────────────────────────────────────────────────────

def get_project_root() -> Path:
    """Get project root directory (parent of api/)"""
    return Path(__file__).parent.parent


def get_logs_dir() -> Path:
    """Get logs directory, create if doesn't exist"""
    logs_dir = get_project_root() / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


def get_model_artifacts_dir() -> Path:
    """Get model artifacts directory"""
    artifacts_dir = get_project_root() / "model" / "model_artifacts"
    artifacts_dir.mkdir(exist_ok=True, parents=True)
    return artifacts_dir
