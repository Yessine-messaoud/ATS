"""Response and request bodies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.db import ApplicationRecord, ApplicationStage, CandidateRecord, JobRecord
from app.matching import Knockout, MatchResult, ScoringWeights
from app.models import CandidateProfile, JobProfile
from app.services.matching import Ranked, RecommendedJob, blind_label


class CandidateOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    profile: CandidateProfile
    extraction: dict[str, Any]

    @classmethod
    def from_record(cls, record: CandidateRecord) -> CandidateOut:
        return cls(
            id=record.id,
            created_at=record.created_at,
            profile=CandidateProfile.model_validate(record.profile),
            extraction=record.extraction_meta,
        )


class JobIn(BaseModel):
    text: str = Field(min_length=50, max_length=50_000, description="Full job description text.")


class JobOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    status: str
    requirements_validated: bool
    profile: JobProfile
    extraction: dict[str, Any]

    @classmethod
    def from_record(cls, record: JobRecord) -> JobOut:
        return cls(
            id=record.id,
            created_at=record.created_at,
            status=record.status,
            requirements_validated=record.requirements_validated,
            profile=JobProfile.model_validate(record.profile),
            extraction=record.extraction_meta,
        )


class RankedCandidateOut(BaseModel):
    candidate_id: uuid.UUID
    display_name: str
    overall_score: float
    passed_knockouts: bool
    matched_required: list[str]
    missing_required: list[str]
    knockouts: list[Knockout]

    @classmethod
    def build(cls, ranked: Ranked, *, blind: bool) -> RankedCandidateOut:
        name = CandidateProfile.model_validate(ranked.candidate.profile).identity.full_name
        return cls(
            candidate_id=ranked.candidate.id,
            display_name=blind_label(ranked.candidate.id) if blind or not name else name,
            overall_score=ranked.result.overall_score,
            passed_knockouts=ranked.result.passed_knockouts,
            matched_required=ranked.result.matched_required,
            missing_required=ranked.result.missing_required,
            knockouts=[k for k in ranked.result.knockouts if k.status != "pass"],
        )


class RankingOut(BaseModel):
    job_id: uuid.UUID
    engine_version: str
    requirements_validated: bool
    weights: ScoringWeights
    ranked: list[RankedCandidateOut]
    knocked_out: list[RankedCandidateOut]


class RecommendedJobOut(BaseModel):
    job_id: uuid.UUID
    title: str
    overall_score: float
    passed_knockouts: bool
    missing_required: list[str]

    @classmethod
    def build(cls, recommended: RecommendedJob) -> RecommendedJobOut:
        return cls(
            job_id=recommended.job.id,
            title=recommended.job.title,
            overall_score=recommended.result.overall_score,
            passed_knockouts=recommended.result.passed_knockouts,
            missing_required=recommended.result.missing_required,
        )


class ProfileCorrectionOut(BaseModel):
    candidate: CandidateOut
    changed_paths: list[str]


class CandidateDocumentOut(BaseModel):
    filename: str | None
    kind: str
    mime_type: str | None
    flags: list[str]
    raw_text: str | None
    hidden_text: list[str]
    injection_snippets: list[str]


class JobStatusIn(BaseModel):
    status: Literal["open", "closed"]


class ApplicationIn(BaseModel):
    candidate_id: uuid.UUID
    job_id: uuid.UUID


class StageIn(BaseModel):
    stage: ApplicationStage
    reason: str | None = Field(default=None, max_length=500, description="Optional note recorded with the decision.")


class ApplicationOut(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    stage: ApplicationStage
    created_at: datetime
    updated_at: datetime
    display_name: str
    overall_score: float | None = None
    passed_knockouts: bool | None = None

    @classmethod
    def build(
        cls, application: ApplicationRecord, *, blind: bool = False, result: MatchResult | None = None
    ) -> ApplicationOut:
        name = CandidateProfile.model_validate(application.candidate.profile).identity.full_name
        return cls(
            id=application.id,
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            stage=application.stage,
            created_at=application.created_at,
            updated_at=application.updated_at,
            display_name=blind_label(application.candidate_id) if blind or not name else name,
            overall_score=result.overall_score if result else None,
            passed_knockouts=result.passed_knockouts if result else None,
        )
