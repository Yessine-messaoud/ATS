"""Database records.

Validated domain profiles (`app.models`) are stored as JSONB together with their schema version.
Raw source text lives only on `DocumentRecord` so that it can be purged under the retention policy
without touching the structured profiles.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin


class ApplicationStage(StrEnum):
    NEW = "new"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class DocumentRecord(IdMixin, TimestampMixin, Base):
    """An uploaded source document (CV, email, job description) and its extracted text."""

    __tablename__ = "documents"

    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(127))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    raw_text: Mapped[str | None] = mapped_column(Text)
    flags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "candidates"

    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
    schema_version: Mapped[str] = mapped_column(String(8))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    extraction_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    applications: Mapped[list[ApplicationRecord]] = relationship(back_populates="candidate")


class JobRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="open")
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
    schema_version: Mapped[str] = mapped_column(String(8))
    requirements_validated: Mapped[bool] = mapped_column(default=False)
    scoring_weights: Mapped[dict[str, float] | None] = mapped_column(JSONB)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    extraction_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    applications: Mapped[list[ApplicationRecord]] = relationship(back_populates="job")


class ApplicationRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id"),)

    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(ApplicationStage, name="application_stage", values_callable=lambda e: [m.value for m in e]),
        default=ApplicationStage.NEW,
    )

    candidate: Mapped[CandidateRecord] = relationship(back_populates="applications")
    job: Mapped[JobRecord] = relationship(back_populates="applications")


class MatchRecord(IdMixin, TimestampMixin, Base):
    """One scoring run of a candidate against a job; kept as history, never overwritten."""

    __tablename__ = "matches"

    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    overall_score: Mapped[float] = mapped_column(Float)
    passed_knockouts: Mapped[bool] = mapped_column()
    factors: Mapped[dict[str, Any]] = mapped_column(JSONB)
    explanation: Mapped[str | None] = mapped_column(Text)
    engine_version: Mapped[str] = mapped_column(String(32))


class AuditLogRecord(IdMixin, Base):
    """Append-only log of human and system actions. Must not contain personal data."""

    __tablename__ = "audit_log"

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
