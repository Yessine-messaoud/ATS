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

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
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
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    pending: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
