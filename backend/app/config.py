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

    # Which LLM backs extraction, explanations and the assistant: a local model served by Ollama (no API key), or
    # Claude. Local inference is free and keeps CVs on the machine; Claude extracts more accurately and faster.
    llm_provider: Literal["ollama", "anthropic"] = "ollama"

    # Ollama. The model must support tool calling for the assistant (`ollama show <model>` lists "tools").
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    ollama_num_ctx: int = 8192
    # Layers offloaded to the GPU; 99 = all. Empty lets Ollama decide (it keeps some layers on the CPU of 6 GB GPUs).
    ollama_num_gpu: int | None = 99
    # Assistant tool calling: "structured" (router + schema-constrained arguments; any model) or "native".
    ollama_tool_mode: Literal["structured", "native"] = "structured"
    ollama_keep_alive: str = "30m"
    ollama_timeout_s: float = 600.0

    # Claude. Credentials are resolved by the Anthropic SDK (ANTHROPIC_API_KEY or an `ant auth login` profile).
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_max_tokens: int = 16000
    extraction_max_repairs: int = 2

    # Ingestion limits.
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 20
    min_text_chars_per_page: int = 50
    ocr_languages: str = "eng+fra"
    document_retention_days: int = 180

    # Privacy. Comma-separated Fernet keys; the first encrypts, all decrypt (rotation). Generate one with
    # `python -m app.security.crypto`. Required in production.
    document_encryption_keys: str | None = None
    # Candidates with no activity for this long, and without talent-pool consent, are erased by the retention job.
    candidate_retention_days: int = 730
    # When on, a job's ranking only includes candidates who consented to the talent pool or applied to that job.
    require_talent_pool_consent: bool = False

    # Retrieval: pools up to this size are scored exhaustively; larger pools are shortlisted by hybrid retrieval.
    full_scoring_limit: int = 500
    retrieval_k: int = 200

    def production_problems(self) -> list[str]:
        """Settings that are acceptable in development but not with real candidate data."""
        problems = []
        if not self.document_encryption_keys:
            problems.append("DOCUMENT_ENCRYPTION_KEYS is not set: documents would be stored unencrypted")
        if self.debug:
            problems.append("DEBUG is on")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
