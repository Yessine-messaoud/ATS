"""Environment-based application settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ATS Recruitment API"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    # Credentials come only from the environment / .env (see .env.example); never hard-code them here.
    database_url: str = "postgresql+psycopg://localhost:5432/ats_db"
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
