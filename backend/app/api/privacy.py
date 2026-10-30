"""Facts the candidate transparency notice is built from, taken from the running configuration."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.matching import engine_version
from app.security.crypto import get_cipher

from .deps import AppSettings

router = APIRouter(prefix="/privacy", tags=["privacy"])


class PrivacyPolicyOut(BaseModel):
    document_retention_days: int
    candidate_retention_days: int
    talent_pool_consent_required: bool
    documents_encrypted: bool
    ai_provider: Literal["ollama", "anthropic"]
    ai_runs_locally: bool
    scoring_engine: str


@router.get("/policy")
def policy(settings: AppSettings) -> PrivacyPolicyOut:
    return PrivacyPolicyOut(
        document_retention_days=settings.document_retention_days,
        candidate_retention_days=settings.candidate_retention_days,
        talent_pool_consent_required=settings.require_talent_pool_consent,
        documents_encrypted=get_cipher().enabled,
        ai_provider=settings.llm_provider,
        ai_runs_locally=settings.llm_provider == "ollama",
        scoring_engine=engine_version(),
    )
