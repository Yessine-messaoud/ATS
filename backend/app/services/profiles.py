"""Create candidate and job records from documents."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import AuditLogRecord, CandidateRecord, DocumentRecord, JobRecord
from app.extraction import CANDIDATE_TARGET, JOB_TARGET, LLMClient, extract
from app.ingestion import FileKind, ingest_document
from app.ingestion.injection import detect_prompt_injection
from app.ingestion.pipeline import DocumentFlag
from app.models import CandidateProfile, JobProfile, SourceType

SOURCE_TYPES = {FileKind.EMAIL: SourceType.EMAIL}


class DuplicateDocument(Exception):
    def __init__(self, existing_id: uuid.UUID) -> None:
        super().__init__(f"this document was already processed (record {existing_id})")
        self.existing_id = existing_id


def _purge_after(settings: Settings) -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.document_retention_days)


def _audit(db: Session, action: str, entity_type: str, entity_id: uuid.UUID, **details: object) -> None:
    db.add(AuditLogRecord(actor="system", action=action, entity_type=entity_type, entity_id=entity_id, details=details))


def create_candidate_from_upload(
    db: Session, llm: LLMClient, settings: Settings, *, data: bytes, filename: str | None
) -> CandidateRecord:
    """Ingest a candidate document, extract its profile and persist both. Raises DuplicateDocument."""
    document = ingest_document(data, settings)
    existing = db.scalar(
        select(CandidateRecord.id)
        .join(DocumentRecord, CandidateRecord.source_document_id == DocumentRecord.id)
        .where(DocumentRecord.sha256 == document.file.sha256)
    )
    if existing is not None:
        raise DuplicateDocument(existing)

    result = extract(llm, CANDIDATE_TARGET, document.text, max_repairs=settings.extraction_max_repairs)
    profile = result.profile
    profile.source_type = SOURCE_TYPES.get(document.file.kind, SourceType.CV)

    document_record = DocumentRecord(
        kind=document.file.kind.value,
        filename=filename,
        mime_type=document.file.mime_type,
        size_bytes=document.file.size_bytes,
        sha256=document.file.sha256,
        content=data,
        raw_text=document.text,
        flags=[flag.value for flag in document.flags],
        purge_after=_purge_after(settings),
    )
    db.add(document_record)
    db.flush()
    candidate = CandidateRecord(
        profile=profile.model_dump(mode="json"),
        schema_version=profile.schema_version,
        email=profile.identity.email,
        source_document_id=document_record.id,
        extraction_meta={
            **result.summary(),
            "document_flags": document_record.flags,
            "hidden_text": document.hidden_text,
            "injection_snippets": document.injection_snippets,
        },
    )
    db.add(candidate)
    db.flush()
    _audit(
        db,
        "candidate.extracted",
        "candidate",
        candidate.id,
        document_id=str(document_record.id),
        prompt_version=result.meta["prompt_version"],
        model=result.meta["model"],
        flags=document_record.flags,
    )
    db.commit()
    return candidate


def create_job_from_text(db: Session, llm: LLMClient, settings: Settings, *, text: str) -> JobRecord:
    sha256 = hashlib.sha256(text.encode()).hexdigest()
    existing = db.scalar(
        select(JobRecord.id)
        .join(DocumentRecord, JobRecord.source_document_id == DocumentRecord.id)
        .where(DocumentRecord.sha256 == sha256)
    )
    if existing is not None:
        raise DuplicateDocument(existing)

    result = extract(llm, JOB_TARGET, text, max_repairs=settings.extraction_max_repairs)
    flags = [DocumentFlag.POSSIBLE_PROMPT_INJECTION.value] if detect_prompt_injection(text) else []
    document_record = DocumentRecord(
        kind="job_description",
        mime_type="text/plain",
        size_bytes=len(text.encode()),
        sha256=sha256,
        raw_text=text,
        flags=flags,
    )
    db.add(document_record)
    db.flush()
    job = JobRecord(
        title=result.profile.title,
        profile=result.profile.model_dump(mode="json"),
        schema_version=result.profile.schema_version,
        source_document_id=document_record.id,
        extraction_meta={**result.summary(), "document_flags": flags},
    )
    db.add(job)
    db.flush()
    _audit(db, "job.extracted", "job", job.id, prompt_version=result.meta["prompt_version"], model=result.meta["model"])
    db.commit()
    return job


def validate_job_requirements(db: Session, job: JobRecord, profile: JobProfile, *, actor: str) -> JobRecord:
    """Store the recruiter-validated requirement grid; it becomes the reference for matching."""
    job.profile = profile.model_dump(mode="json")
    job.title = profile.title
    job.requirements_validated = True
    db.add(AuditLogRecord(actor=actor, action="job.requirements_validated", entity_type="job", entity_id=job.id))
    db.commit()
    return job


def _changed_paths(before: object, after: object, path: str = "") -> list[str]:
    """Paths whose values differ (values themselves are never returned: they may be personal data)."""
    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(before.keys() | after.keys())
        return [p for key in keys for p in _changed_paths(before.get(key), after.get(key), f"{path}.{key}".lstrip("."))]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [
            p for i, (b, a) in enumerate(zip(before, after, strict=True)) for p in _changed_paths(b, a, f"{path}[{i}]")
        ]
    return [] if before == after else [path or "<root>"]


def correct_candidate_profile(
    db: Session, candidate: CandidateRecord, profile: CandidateProfile, *, actor: str
) -> list[str]:
    """Store the recruiter-corrected profile. The first extraction is kept as feedback data for evaluation."""
    corrected = profile.model_dump(mode="json")
    changed = _changed_paths(candidate.profile, corrected)
    if not changed:
        return []
    meta = dict(candidate.extraction_meta)
    meta.setdefault("extracted_profile", candidate.profile)
    meta["corrections"] = [*meta.get("corrections", []), {"actor": actor, "changed_paths": changed}]
    candidate.extraction_meta = meta
    candidate.profile = corrected
    candidate.email = profile.identity.email
    db.add(
        AuditLogRecord(
            actor=actor,
            action="candidate.profile_corrected",
            entity_type="candidate",
            entity_id=candidate.id,
            details={"changed_paths": changed},
        )
    )
    db.commit()
    return changed
