"""Database records.

Validated domain profiles (`app.models`) are stored as JSONB together with their schema version.
Raw source text lives only on `DocumentRecord` so that it can be purged under the retention policy
without touching the structured profiles. The original file and its text are encrypted at rest.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin
from .types import EncryptedBytes, EncryptedText


class ApplicationStage(StrEnum):
    NEW = "new"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Role(StrEnum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    CANDIDATE = "candidate"


class OrganizationStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


def _enum(enum: type[StrEnum], name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda e: [m.value for m in e])


class OrganizationRecord(IdMixin, TimestampMixin, Base):
    """A hiring company. Its recruiters see only its jobs, its own candidates and the people who applied to it."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[OrganizationStatus] = mapped_column(
        _enum(OrganizationStatus, "organization_status"), default=OrganizationStatus.PENDING
    )
    website: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(128))
    size: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)

    users: Mapped[list[UserRecord]] = relationship(back_populates="organization")


class UserRecord(IdMixin, TimestampMixin, Base):
    """A person who signs in: a platform admin, a company recruiter, or a candidate."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role, "user_role"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    job_title: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(64))
    locale: Mapped[str] = mapped_column(String(8), default="en")
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[OrganizationRecord | None] = relationship(back_populates="users")

    @property
    def actor(self) -> str:
        """How this user appears in the audit log (an id, never a name or an email)."""
        return f"user:{self.id}"


class SessionRecord(IdMixin, Base):
    """A sign-in session. Only a hash of the token is stored, so a database leak does not leak sessions."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[UserRecord] = relationship()


class DocumentRecord(IdMixin, TimestampMixin, Base):
    """An uploaded source document (CV, email, job description) and its extracted text."""

    __tablename__ = "documents"

    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(127))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[bytes | None] = mapped_column(EncryptedBytes)
    raw_text: Mapped[str | None] = mapped_column(EncryptedText)
    flags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "candidates"

    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
    schema_version: Mapped[str] = mapped_column(String(8))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    extraction_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Consent to be kept in the talent pool and matched to other jobs. None = not asked yet.
    talent_pool_consent: Mapped[bool | None] = mapped_column()
    consent_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The company that uploaded the CV (its private pool), or None when the candidate came through the portal.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # The candidate's own account (portal candidates): they own this profile and correct it themselves.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), unique=True)

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
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    applications: Mapped[list[ApplicationRecord]] = relationship(back_populates="job")
    organization: Mapped[OrganizationRecord | None] = relationship()


class ApplicationRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id"),)

    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(ApplicationStage, name="application_stage", values_callable=lambda e: [m.value for m in e]),
        default=ApplicationStage.NEW,
    )
    # "recruiter" (added from a ranking or by the assistant) or "portal" (the candidate applied).
    source: Mapped[str] = mapped_column(String(16), default="recruiter", server_default="recruiter")

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
    # The company the entry belongs to, so that each company sees only its own log (see app.db.scope).
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )


EMBEDDING_DIM = 384


class _SearchIndex:
    """Retrieval representation of a profile: text for full-text search and an embedding for vector search."""

    model: Mapped[str] = mapped_column(String(64))
    search_text: Mapped[str] = mapped_column(Text)
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('simple', search_text)", persisted=True))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CandidateSearchRecord(_SearchIndex, Base):
    __tablename__ = "candidate_search"
    __table_args__ = (
        Index("ix_candidate_search_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_candidate_search_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True)


class JobSearchRecord(_SearchIndex, Base):
    __tablename__ = "job_search"
    __table_args__ = (
        Index(
            "ix_job_search_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)


class TaxonomySkillRecord(Base):
    """One ESCO skill concept (imported with scripts/import_esco.py)."""

    __tablename__ = "taxonomy_skills"

    uri: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[str] = mapped_column(String(32))
    label_en: Mapped[str | None] = mapped_column(Text)
    label_fr: Mapped[str | None] = mapped_column(Text)
    alt_labels: Mapped[list[str]] = mapped_column(JSONB, default=list)
    skill_type: Mapped[str | None] = mapped_column(String(64))


class TaxonomyBroaderRecord(Base):
    __tablename__ = "taxonomy_broader"

    narrower_uri: Mapped[str] = mapped_column(String(255), primary_key=True)
    broader_uri: Mapped[str] = mapped_column(String(255), primary_key=True)


class AgentConversationRecord(IdMixin, TimestampMixin, Base):
    """An assistant conversation: the full API message history (replayed unchanged) and any pending actions."""

    __tablename__ = "agent_conversations"

    blind: Mapped[bool] = mapped_column(default=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    pending: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class IngestionTaskRecord(IdMixin, TimestampMixin, Base):
    """A CV waiting to be read in the background (portal applications), and the application to create after."""

    __tablename__ = "ingestion_tasks"

    status: Mapped[TaskStatus] = mapped_column(_enum(TaskStatus, "task_status"), default=TaskStatus.QUEUED, index=True)
    filename: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[bytes | None] = mapped_column(EncryptedBytes)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("candidates.id", ondelete="SET NULL"))
    talent_pool_consent: Mapped[bool | None] = mapped_column()
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
