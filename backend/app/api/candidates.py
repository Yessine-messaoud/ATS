from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.db import AuditLogRecord, CandidateRecord, DocumentRecord
from app.models import CandidateProfile
from app.services.access import Scope
from app.services.dedup import MergeConflict, find_duplicates, merge_candidates
from app.services.matching import recommend_jobs
from app.services.privacy import erase_candidate, export_candidate, set_consent
from app.services.profiles import correct_candidate_profile, create_candidate_from_upload

from .deps import AppSettings, DbSession, Llm, StaffScope, domain_errors, get_or_404, get_scope
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

router = APIRouter(prefix="/candidates", tags=["candidates"], dependencies=[Depends(get_scope)])


def _visible(db: DbSession, scope: Scope, candidate_id: uuid.UUID) -> CandidateRecord:
    return get_or_404(lambda: scope.candidate(db, candidate_id), "candidate")


def _managed(db: DbSession, scope: Scope, candidate_id: uuid.UUID) -> CandidateRecord:
    """A candidate the company uploaded itself. Portal candidates manage their own profile and data."""
    record = _visible(db, scope, candidate_id)
    if not scope.manages(record):
        raise HTTPException(403, "this candidate applied through the portal and manages their own profile and data")
    return record


@router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_candidate(
    file: UploadFile, db: DbSession, llm: Llm, settings: AppSettings, scope: StaffScope
) -> CandidateOut:
    """Upload a CV (PDF, DOCX, text) or an application email (.eml) and extract the candidate profile."""
    if scope.organization_id is None:
        raise HTTPException(403, "CVs are uploaded by a company's recruiters")
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"file exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit")
    with domain_errors():
        record = create_candidate_from_upload(
            db, llm, settings, data=data, filename=file.filename, organization_id=scope.organization_id
        )
    return CandidateOut.from_record(record)


@router.get("")
def list_candidates(db: DbSession, scope: StaffScope, limit: int = Query(50, ge=1, le=200)) -> list[CandidateOut]:
    query = select(CandidateRecord).where(scope.candidates()).order_by(CandidateRecord.created_at.desc())
    records = db.scalars(query.limit(limit))
    return [CandidateOut.from_record(record) for record in records]


@router.get("/{candidate_id}")
def get_candidate(candidate_id: uuid.UUID, db: DbSession, scope: StaffScope) -> CandidateOut:
    record = _visible(db, scope, candidate_id)
    return CandidateOut.from_record(record)


@router.get("/{candidate_id}/recommendations")
def get_recommendations(
    candidate_id: uuid.UUID,
    db: DbSession,
    settings: AppSettings,
    scope: StaffScope,
    limit: int = Query(10, ge=1, le=100),
) -> list[RecommendedJobOut]:
    """The company's open jobs ranked for this candidate (jobs passing knock-outs first)."""
    record = _visible(db, scope, candidate_id)
    consent_required = settings.require_talent_pool_consent
    found = recommend_jobs(db, record, limit=limit, consent_required=consent_required, jobs=scope.jobs())
    return [RecommendedJobOut.build(r) for r in found]


@router.put("/{candidate_id}/profile")
def correct_profile(
    candidate_id: uuid.UUID, profile: CandidateProfile, db: DbSession, scope: StaffScope
) -> ProfileCorrectionOut:
    """Save the recruiter-reviewed profile (corrections, confirmed or removed items).

    The original extraction is kept for evaluation; the audit log records which fields changed, not their values.
    """
    record = _managed(db, scope, candidate_id)
    changed = correct_candidate_profile(db, record, profile, actor=scope.actor)
    return ProfileCorrectionOut(candidate=CandidateOut.from_record(record), changed_paths=changed)


def _document(db: DbSession, scope: Scope, candidate_id: uuid.UUID) -> tuple[CandidateRecord, DocumentRecord]:
    record = _visible(db, scope, candidate_id)
    document = get_or_404(
        lambda: db.get(DocumentRecord, record.source_document_id) if record.source_document_id else None, "document"
    )
    return record, document


@router.get("/{candidate_id}/document")
def get_document(candidate_id: uuid.UUID, db: DbSession, scope: StaffScope) -> CandidateDocumentOut:
    """Source document metadata, extracted text and security flags, for side-by-side review."""
    record, document = _document(db, scope, candidate_id)
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
def get_document_file(candidate_id: uuid.UUID, db: DbSession, scope: StaffScope) -> Response:
    _, document = _document(db, scope, candidate_id)
    if document.content is None:
        detail = "original file purged under the retention policy" if document.purged_at else "original file not stored"
        raise HTTPException(404, detail)
    return Response(
        content=document.content,
        media_type=document.mime_type or "application/octet-stream",
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{candidate_id}/duplicates")
def get_duplicates(candidate_id: uuid.UUID, db: DbSession, scope: StaffScope) -> list[DuplicateOut]:
    """Possible duplicates among the company's own candidates (same email or phone, or a near-identical profile)."""
    record = _visible(db, scope, candidate_id)
    if not scope.manages(record):
        return []
    found = []
    for duplicate in find_duplicates(db, record):
        other = scope.candidate(db, duplicate.candidate_id)
        if other is not None:
            found.append(DuplicateOut.build(other, duplicate.reasons))
    return found


@router.post("/{candidate_id}/merge")
def merge(candidate_id: uuid.UUID, body: MergeIn, db: DbSession, scope: StaffScope) -> CandidateOut:
    """Merge `duplicate_id` into this candidate (recruiter-confirmed). The duplicate record is deleted."""
    keep = _managed(db, scope, candidate_id)
    duplicate = _managed(db, scope, body.duplicate_id)
    try:
        merged = merge_candidates(db, keep, duplicate, actor=scope.actor)
    except MergeConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return CandidateOut.from_record(merged)


@router.put("/{candidate_id}/consent")
def update_consent(candidate_id: uuid.UUID, body: ConsentIn, db: DbSession, scope: StaffScope) -> CandidateOut:
    """Record the candidate's talent-pool consent (to be matched to jobs they did not apply to)."""
    record = _managed(db, scope, candidate_id)
    return CandidateOut.from_record(set_consent(db, record, body.consent, actor=scope.actor))


@router.get("/{candidate_id}/export")
def export_data(candidate_id: uuid.UUID, db: DbSession, settings: AppSettings, scope: StaffScope) -> JSONResponse:
    """Everything held about the candidate (GDPR access and portability), as a JSON download."""
    record = _managed(db, scope, candidate_id)
    data = export_candidate(db, record, settings)
    db.add(AuditLogRecord(actor=scope.actor, action="candidate.exported", entity_type="candidate", entity_id=record.id))
    db.commit()
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="candidate-{candidate_id}.json"'})


@router.delete("/{candidate_id}")
def erase(
    candidate_id: uuid.UUID,
    db: DbSession,
    scope: StaffScope,
    reason: str = Query("candidate request", max_length=200, description="Why the data is erased (audit log)."),
) -> ErasureOut:
    """Erase the candidate and all their personal data (GDPR right to erasure). Irreversible."""
    record = _managed(db, scope, candidate_id)
    report = erase_candidate(db, record, actor=scope.actor, reason=reason)
    return ErasureOut(candidate_id=report.candidate_id, **report.as_details())
