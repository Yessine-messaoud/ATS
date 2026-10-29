from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select

from app.db import CandidateRecord, DocumentRecord
from app.models import CandidateProfile
from app.services.matching import recommend_jobs
from app.services.profiles import correct_candidate_profile, create_candidate_from_upload

from .deps import AppSettings, DbSession, Llm, domain_errors, get_or_404
from .schemas import CandidateDocumentOut, CandidateOut, ProfileCorrectionOut, RecommendedJobOut

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
    candidate_id: uuid.UUID, db: DbSession, limit: int = Query(10, ge=1, le=100)
) -> list[RecommendedJobOut]:
    """Open jobs ranked for this candidate (jobs passing knock-outs first)."""
    record = get_or_404(lambda: db.get(CandidateRecord, candidate_id), "candidate")
    return [RecommendedJobOut.build(r) for r in recommend_jobs(db, record, limit=limit)]


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
    )


@router.get("/{candidate_id}/document/file", response_class=Response)
def get_document_file(candidate_id: uuid.UUID, db: DbSession) -> Response:
    _, document = _document(db, candidate_id)
    if document.content is None:
        raise HTTPException(404, "original file not stored")
    return Response(
        content=document.content,
        media_type=document.mime_type or "application/octet-stream",
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"},
    )
