from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.db import CandidateRecord
from app.services.profiles import create_candidate_from_upload

from .deps import AppSettings, DbSession, Llm, domain_errors, get_or_404
from .schemas import CandidateOut

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
