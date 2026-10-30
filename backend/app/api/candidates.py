from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.db import AuditLogRecord, CandidateRecord, DocumentRecord
from app.models import CandidateProfile
from app.services.dedup import MergeConflict, find_duplicates, merge_candidates
from app.services.matching import recommend_jobs
from app.services.privacy import erase_candidate, export_candidate, set_consent
from app.services.profiles import correct_candidate_profile, create_candidate_from_upload

from .deps import AppSettings, DbSession, Llm, domain_errors, get_or_404
from .schemas import (
    CandidateDocumentOut,
    CandidateOut,
    ConsentIn,
    DuplicateOut,
    ErasureOut,
    MergeIn,
    ProfileCorrectionOut,
    RecommendedJobOut,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_candidate(file: UploadFile, db: DbSession, llm: Llm, settings: AppSettings) -> CandidateOut:
    """Upload a CV (PDF, DOCX, text) or an application email (.eml) and extract the candidate profile."""
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"file exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit")
    with domain_errors():
        record = create_candidate_from_upload(db, llm, settings, data=data, filename=file.filename)
    return CandidateOut.from_record(record)


@router.get("")
def list_candidates(db: DbSession, limit: int = Query(50, ge=1, le=200)) -> list[CandidateOut]:
    records = db.scalars(select(CandidateRecord).order_by(CandidateRecord.created_at.desc()).limit(limit))
    return [CandidateOut.from_record(record) for record in records]


@router.get("/{candidate_id}")
def get_candidate(candidate_id: uuid.UUID, db: DbSession) -> CandidateOut:
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    return CandidateOut.from_record(record)


@router.get("/{candidate_id}/recommendations")
def get_recommendations(
    candidate_id: uuid.UUID, db: DbSession, settings: AppSettings, limit: int = Query(10, ge=1, le=100)
) -> list[RecommendedJobOut]:
    """Open jobs ranked for this candidate (jobs passing knock-outs first)."""
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    consent_required = settings.require_talent_pool_consent
    return [
        RecommendedJobOut.build(r) for r in recommend_jobs(db, record, limit=limit, consent_required=consent_required)
    ]


@router.put("/{candidate_id}/profile")
def correct_profile(candidate_id: uuid.UUID, profile: CandidateProfile, db: DbSession) -> ProfileCorrectionOut:
    """Save the recruiter-reviewed profile (corrections, confirmed or removed items).

    The original extraction is kept for evaluation; the audit log records which fields changed, not their values.
    """
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    # TODO(phase-3): use the authenticated recruiter as actor once auth exists.
    changed = correct_candidate_profile(db, record, profile, actor="recruiter")
    return ProfileCorrectionOut(candidate=CandidateOut.from_record(record), changed_paths=changed)


def _document(db: DbSession, candidate_id: uuid.UUID) -> tuple[CandidateRecord, DocumentRecord]:
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    document = get_or_404(
        lambda: db.get(DocumentRecord, record.source_document_id) if record.source_document_id else None, "document"
    )
    return record, document


@router.get("/{candidate_id}/document")
def get_document(candidate_id: uuid.UUID, db: DbSession) -> CandidateDocumentOut:
    """Source document metadata, extracted text and security flags, for side-by-side review."""
    record, document = _document(db, candidate_id)
    return CandidateDocumentOut(
        filename=document.filename,
        kind=document.kind,
        mime_type=document.mime_type,
        flags=document.flags,
        raw_text=document.raw_text,
        hidden_text=record.extraction_meta.get("hidden_text", []),
        injection_snippets=record.extraction_meta.get("injection_snippets", []),
        purge_after=document.purge_after,
        purged_at=document.purged_at,
    )


@router.get("/{candidate_id}/document/file", response_class=Response)
def get_document_file(candidate_id: uuid.UUID, db: DbSession) -> Response:
    _, document = _document(db, candidate_id)
    if document.content is None:
        detail = "original file purged under the retention policy" if document.purged_at else "original file not stored"
        raise HTTPException(404, detail)
    return Response(
        content=document.content,
        media_type=document.mime_type or "application/octet-stream",
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{candidate_id}/duplicates")
def get_duplicates(candidate_id: uuid.UUID, db: DbSession) -> list[DuplicateOut]:
    """Possible duplicates of this candidate (same email or phone, or same person with a near-identical profile)."""
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    found = []
    for duplicate in find_duplicates(db, record):
        other = db.get(CandidateRecord, duplicate.candidate_id)
        if other is not None:
            found.append(DuplicateOut.build(other, duplicate.reasons))
    return found


@router.post("/{candidate_id}/merge")
def merge(candidate_id: uuid.UUID, body: MergeIn, db: DbSession) -> CandidateOut:
    """Merge `duplicate_id` into this candidate (recruiter-confirmed). The duplicate record is deleted."""
    keep = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    duplicate = get_or_404(lambda: db.get(CandidateRecord, body.duplicate_id), "duplicate candidate")
    try:
        # TODO(phase-3): use the authenticated recruiter as actor once auth exists.
        merged = merge_candidates(db, keep, duplicate, actor="recruiter")
    except MergeConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return CandidateOut.from_record(merged)


@router.put("/{candidate_id}/consent")
def update_consent(candidate_id: uuid.UUID, body: ConsentIn, db: DbSession) -> CandidateOut:
    """Record the candidate's talent-pool consent (to be matched to jobs they did not apply to)."""
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    return CandidateOut.from_record(set_consent(db, record, body.consent, actor="recruiter"))


@router.get("/{candidate_id}/export")
def export_data(candidate_id: uuid.UUID, db: DbSession, settings: AppSettings) -> JSONResponse:
    """Everything held about the candidate (GDPR access and portability), as a JSON download."""
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    data = export_candidate(db, record, settings)
    db.add(AuditLogRecord(actor="recruiter", action="candidate.exported", entity_type="candidate", entity_id=record.id))
    db.commit()
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="candidate-{candidate_id}.json"'})


@router.delete("/{candidate_id}")
def erase(
    candidate_id: uuid.UUID,
    db: DbSession,
    reason: str = Query("candidate request", max_length=200, description="Why the data is erased (audit log)."),
) -> ErasureOut:
    """Erase the candidate and all their personal data (GDPR right to erasure). Irreversible."""
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    report = erase_candidate(db, record, actor="recruiter", reason=reason)
    return ErasureOut(candidate_id=report.candidate_id, **report.as_details())
