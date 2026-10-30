"""Data-subject rights and retention: export (GDPR art. 15/20), erasure (art. 17), consent, and the purge job.

Erasure removes everything that identifies the candidate: the candidate record, its documents (including those of
merged duplicates), applications, match history, search index entries and the assistant conversations that
mention them (tool results quote their profile). Audit entries are kept as proof of processing, but they hold
ids only: free-text reasons attached to the candidate's applications are blanked, and an erasure entry is
written that contains no personal data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import (
    AgentConversationRecord,
    ApplicationRecord,
    AuditLogRecord,
    CandidateRecord,
    DocumentRecord,
    JobRecord,
    MatchRecord,
)

EXPORT_FORMAT = "ats-candidate-export-v1"
ERASED = "[erased]"


def _document_ids(candidate: CandidateRecord) -> list[uuid.UUID]:
    ids = [candidate.source_document_id] if candidate.source_document_id else []
    for value in candidate.extraction_meta.get("merged_documents", []):
        try:
            ids.append(uuid.UUID(value))
        except ValueError:
            continue
    return ids


def _mentions(candidate_id: uuid.UUID) -> Any:
    return cast(AgentConversationRecord.messages, String).contains(str(candidate_id))


def _audit_entries(db: Session, candidate_id: uuid.UUID, application_ids: list[uuid.UUID]) -> list[AuditLogRecord]:
    return list(
        db.scalars(
            select(AuditLogRecord)
            .where(
                or_(
                    AuditLogRecord.entity_id == candidate_id,
                    AuditLogRecord.entity_id.in_(application_ids),
                    AuditLogRecord.details["candidate_id"].astext == str(candidate_id),
                    AuditLogRecord.details["merged_id"].astext == str(candidate_id),
                )
            )
            .order_by(AuditLogRecord.created_at)
        )
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def export_candidate(db: Session, candidate: CandidateRecord, settings: Settings) -> dict[str, Any]:
    """Everything held about a candidate, in a machine-readable form."""
    applications = list(db.scalars(select(ApplicationRecord).where(ApplicationRecord.candidate_id == candidate.id)))
    job_titles = {job_id: title for job_id, title in db.execute(select(JobRecord.id, JobRecord.title))}
    documents = [doc for doc in (db.get(DocumentRecord, i) for i in _document_ids(candidate)) if doc is not None]
    matches = db.scalars(
        select(MatchRecord).where(MatchRecord.candidate_id == candidate.id).order_by(MatchRecord.created_at)
    )
    conversations = db.scalar(select(func.count()).select_from(AgentConversationRecord).where(_mentions(candidate.id)))
    return {
        "format": EXPORT_FORMAT,
        "exported_at": datetime.now(UTC).isoformat(),
        "candidate": {
            "id": str(candidate.id),
            "created_at": _iso(candidate.created_at),
            "updated_at": _iso(candidate.updated_at),
            "profile": candidate.profile,
            "talent_pool_consent": candidate.talent_pool_consent,
            "consent_updated_at": _iso(candidate.consent_updated_at),
            "corrections": candidate.extraction_meta.get("corrections", []),
            "extracted_profile_before_corrections": candidate.extraction_meta.get("extracted_profile"),
        },
        "documents": [
            {
                "id": str(doc.id),
                "kind": doc.kind,
                "filename": doc.filename,
                "mime_type": doc.mime_type,
                "size_bytes": doc.size_bytes,
                "received_at": _iso(doc.created_at),
                "purge_after": _iso(doc.purge_after),
                "purged_at": _iso(doc.purged_at),
                "flags": doc.flags,
                "extracted_text": doc.raw_text,
            }
            for doc in documents
        ],
        "applications": [
            {
                "job_id": str(a.job_id),
                "job_title": job_titles.get(a.job_id),
                "stage": a.stage.value,
                "created_at": _iso(a.created_at),
                "updated_at": _iso(a.updated_at),
            }
            for a in applications
        ],
        "automated_assessments": [
            {
                "job_id": str(m.job_id),
                "job_title": job_titles.get(m.job_id),
                "scored_at": _iso(m.created_at),
                "engine_version": m.engine_version,
                "overall_score": m.overall_score,
                "passed_mandatory_criteria": m.passed_knockouts,
                "factors": m.factors,
                "explanation": m.explanation,
            }
            for m in matches
        ],
        "processing_log": [
            {"at": _iso(e.created_at), "actor": e.actor, "action": e.action, "details": e.details}
            for e in _audit_entries(db, candidate.id, [a.id for a in applications])
        ],
        "assistant_conversations_mentioning_candidate": conversations or 0,
        "retention": {
            "documents_days": settings.document_retention_days,
            "profile_days_without_activity_unless_consented": settings.candidate_retention_days,
        },
    }


@dataclass
class ErasureReport:
    candidate_id: uuid.UUID
    documents: int = 0
    applications: int = 0
    matches: int = 0
    conversations: int = 0
    audit_entries_redacted: int = 0

    def as_details(self) -> dict[str, Any]:
        return {
            "documents": self.documents,
            "applications": self.applications,
            "matches": self.matches,
            "conversations": self.conversations,
            "audit_entries_redacted": self.audit_entries_redacted,
        }


def erase_candidate(db: Session, candidate: CandidateRecord, *, actor: str, reason: str) -> ErasureReport:
    report = ErasureReport(candidate_id=candidate.id)
    application_ids = list(
        db.scalars(select(ApplicationRecord.id).where(ApplicationRecord.candidate_id == candidate.id))
    )
    for entry in _audit_entries(db, candidate.id, application_ids):
        if entry.details.get("reason"):
            entry.details = {**entry.details, "reason": ERASED}
            report.audit_entries_redacted += 1

    document_ids = _document_ids(candidate)
    report.applications = len(application_ids)
    report.matches = (
        db.scalar(select(func.count()).select_from(MatchRecord).where(MatchRecord.candidate_id == candidate.id)) or 0
    )
    conversations = delete(AgentConversationRecord).where(_mentions(candidate.id)).returning(AgentConversationRecord.id)
    report.conversations = len(db.scalars(conversations).all())
    db.execute(delete(ApplicationRecord).where(ApplicationRecord.candidate_id == candidate.id))
    db.delete(candidate)  # matches and the search entry go with it (ON DELETE CASCADE)
    db.flush()
    documents = delete(DocumentRecord).where(DocumentRecord.id.in_(document_ids)).returning(DocumentRecord.id)
    report.documents = len(db.scalars(documents).all())
    db.add(
        AuditLogRecord(
            actor=actor,
            action="candidate.erased",
            entity_type="candidate",
            entity_id=candidate.id,
            details={"reason": reason, **report.as_details()},
        )
    )
    db.commit()
    return report


def set_consent(db: Session, candidate: CandidateRecord, consent: bool, *, actor: str) -> CandidateRecord:
    if candidate.talent_pool_consent is consent:
        return candidate
    previous = candidate.talent_pool_consent
    candidate.talent_pool_consent = consent
    candidate.consent_updated_at = datetime.now(UTC)
    db.add(
        AuditLogRecord(
            actor=actor,
            action="candidate.consent_updated",
            entity_type="candidate",
            entity_id=candidate.id,
            details={"from": previous, "to": consent},
        )
    )
    db.commit()
    return candidate


@dataclass
class RetentionReport:
    documents_purged: int = 0
    candidates_erased: list[str] = field(default_factory=list)


def run_retention(
    db: Session, settings: Settings, *, now: datetime | None = None, dry_run: bool = False
) -> RetentionReport:
    """Purge expired document content, and erase inactive candidates who did not consent to the talent pool.

    A candidate is inactive when neither their record nor any of their applications changed during
    `candidate_retention_days`. Purged documents keep their metadata (hash, flags) so duplicates are still detected.
    """
    now = now or datetime.now(UTC)
    report = RetentionReport()
    expired = list(
        db.scalars(select(DocumentRecord).where(DocumentRecord.purge_after <= now, DocumentRecord.purged_at.is_(None)))
    )
    report.documents_purged = len(expired)

    cutoff = now - timedelta(days=settings.candidate_retention_days)
    last_application = (
        select(func.max(ApplicationRecord.updated_at))
        .where(ApplicationRecord.candidate_id == CandidateRecord.id)
        .scalar_subquery()
    )
    inactive = list(
        db.scalars(
            select(CandidateRecord).where(
                CandidateRecord.talent_pool_consent.is_not(True),
                CandidateRecord.updated_at < cutoff,
                or_(last_application.is_(None), last_application < cutoff),
            )
        )
    )
    report.candidates_erased = [str(c.id) for c in inactive]
    if dry_run:
        return report

    for document in expired:
        document.content = None
        document.raw_text = None
        document.purged_at = now
        db.add(AuditLogRecord(actor="system", action="document.purged", entity_type="document", entity_id=document.id))
    db.commit()
    for candidate in inactive:
        erase_candidate(db, candidate, actor="system", reason="retention period elapsed")
    return report
