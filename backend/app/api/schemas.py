"""Response and request bodies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.db import (
    ApplicationRecord,
    ApplicationStage,
    CandidateRecord,
    JobRecord,
    OrganizationRecord,
    OrganizationStatus,
    Role,
    UserRecord,
)
from app.matching import Knockout, MatchResult, ScoringWeights
from app.models import CandidateProfile, JobProfile
from app.services.matching import Ranked, RecommendedJob, blind_label


class CandidateOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    profile: CandidateProfile
    extraction: dict[str, Any]
    talent_pool_consent: bool | None = Field(description="Consent to be matched to other jobs; null = not asked.")
    consent_updated_at: datetime | None
    source: Literal["company", "portal"] = Field(
        "company", description="Uploaded by the company, or applied through the portal (the candidate owns it)."
    )

    @classmethod
    def from_record(cls, record: CandidateRecord) -> CandidateOut:
        return cls(
            id=record.id,
            created_at=record.created_at,
            profile=CandidateProfile.model_validate(record.profile),
            extraction=record.extraction_meta,
            talent_pool_consent=record.talent_pool_consent,
            consent_updated_at=record.consent_updated_at,
            source="portal" if record.user_id is not None else "company",
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
    organization_id: uuid.UUID | None = None
    organization_name: str | None = None

    @classmethod
    def from_record(cls, record: JobRecord) -> JobOut:
        return cls(
            id=record.id,
            created_at=record.created_at,
            status=record.status,
            requirements_validated=record.requirements_validated,
            profile=JobProfile.model_validate(record.profile),
            extraction=record.extraction_meta,
            organization_id=record.organization_id,
            organization_name=record.organization.name if record.organization else None,
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
    retrieval_mode: Literal["all", "hybrid"] = Field(
        description="all: every candidate was scored; hybrid: a retrieval shortlist was scored."
    )
    pool_size: int
    scored: int
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
    purge_after: datetime | None
    purged_at: datetime | None


class ConsentIn(BaseModel):
    consent: bool


class ErasureOut(BaseModel):
    candidate_id: uuid.UUID
    documents: int
    applications: int
    matches: int
    conversations: int
    audit_entries_redacted: int


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor: str
    actor_name: str | None = Field(None, description="The staff member's name, for `user:<id>` actors.")
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    details: dict[str, Any]


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
    source: str = "recruiter"

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
            source=application.source,
        )


class DuplicateOut(BaseModel):
    candidate_id: uuid.UUID
    display_name: str
    professional_title: str | None
    created_at: datetime
    reasons: list[str]

    @classmethod
    def build(cls, record: CandidateRecord, reasons: list[str]) -> DuplicateOut:
        profile = CandidateProfile.model_validate(record.profile)
        return cls(
            candidate_id=record.id,
            display_name=profile.identity.full_name or blind_label(record.id),
            professional_title=profile.professional_title,
            created_at=record.created_at,
            reasons=reasons,
        )


class MergeIn(BaseModel):
    duplicate_id: uuid.UUID


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    status: OrganizationStatus
    website: str | None
    industry: str | None
    size: str | None
    city: str | None
    description: str | None
    created_at: datetime

    @classmethod
    def from_record(cls, record: OrganizationRecord) -> OrganizationOut:
        return cls.model_validate(record, from_attributes=True)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    organization: OrganizationOut | None
    job_title: str | None
    phone: str | None
    locale: str
    preferences: dict[str, Any]
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    @classmethod
    def from_record(cls, record: UserRecord) -> UserOut:
        return cls(
            id=record.id,
            email=record.email,
            full_name=record.full_name,
            role=record.role,
            organization=OrganizationOut.from_record(record.organization) if record.organization else None,
            job_title=record.job_title,
            phone=record.phone,
            locale=record.locale,
            preferences=record.preferences,
            is_active=record.is_active,
            last_login_at=record.last_login_at,
            created_at=record.created_at,
        )


class SessionOut(BaseModel):
    token: str = Field(description="Send as `Authorization: Bearer <token>`. Shown once; only its hash is stored.")
    expires_at: datetime
    user: UserOut


class CreatedUserOut(BaseModel):
    user: UserOut
    temporary_password: str = Field(description="Shown once: give it to the person, who changes it after signing in.")
