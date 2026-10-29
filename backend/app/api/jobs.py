from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.db import JobRecord
from app.models import JobProfile
from app.services.profiles import create_job_from_text, validate_job_requirements

from .deps import AppSettings, DbSession, Llm, domain_errors, get_or_404
from .schemas import JobIn, JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job(body: JobIn, db: DbSession, llm: Llm, settings: AppSettings) -> JobOut:
    """Create a job from its description; the extracted requirement grid awaits recruiter validation."""
    with domain_errors():
        record = create_job_from_text(db, llm, settings, text=body.text)
    return JobOut.from_record(record)


@router.get("")
def list_jobs(db: DbSession, limit: int = Query(50, ge=1, le=200)) -> list[JobOut]:
    records = db.scalars(select(JobRecord).order_by(JobRecord.created_at.desc()).limit(limit))
    return [JobOut.from_record(record) for record in records]


@router.get("/{job_id}")
def get_job(job_id: uuid.UUID, db: DbSession) -> JobOut:
    return JobOut.from_record(get_or_404(lambda: db.get(JobRecord, job_id), "job"))


@router.put("/{job_id}/requirements")
def put_job_requirements(job_id: uuid.UUID, profile: JobProfile, db: DbSession) -> JobOut:
    """Replace the requirement grid with the recruiter-validated version."""
    record = get_or_404(lambda: db.get(JobRecord, job_id), "job")
    # TODO(phase-3): use the authenticated recruiter as actor once auth exists.
    return JobOut.from_record(validate_job_requirements(db, record, profile, actor="recruiter"))
