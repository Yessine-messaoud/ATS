"""Response and request bodies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db import CandidateRecord, JobRecord
from app.models import CandidateProfile, JobProfile


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
