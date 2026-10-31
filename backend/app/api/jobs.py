from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.db import JobRecord
from app.matching import ScoringWeights, engine_version
from app.models import JobProfile
from app.services.access import Scope
from app.services.matching import job_weights, rank_candidates, score, set_job_weights
from app.services.pipeline import job_applications
from app.services.profiles import create_job_from_text, validate_job_requirements

from .deps import AppSettings, DbSession, Llm, StaffScope, domain_errors, get_or_404, get_scope
from .schemas import ApplicationOut, JobIn, JobOut, JobStatusIn, RankedCandidateOut, RankingOut

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_scope)])


def _job(db: DbSession, scope: Scope, job_id: uuid.UUID) -> JobRecord:
    return get_or_404(lambda: scope.job(db, job_id), "job")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job(body: JobIn, db: DbSession, llm: Llm, settings: AppSettings, scope: StaffScope) -> JobOut:
    """Create a job from its description; the extracted requirement grid awaits recruiter validation."""
    if scope.organization_id is None:
        raise HTTPException(403, "jobs are posted by a company's recruiters")
    with domain_errors():
        record = create_job_from_text(
            db, llm, settings, text=body.text, organization_id=scope.organization_id, created_by_id=scope.user.id
        )
    return JobOut.from_record(record)


@router.get("")
def list_jobs(db: DbSession, scope: StaffScope, limit: int = Query(50, ge=1, le=200)) -> list[JobOut]:
    records = db.scalars(select(JobRecord).where(scope.jobs()).order_by(JobRecord.created_at.desc()).limit(limit))
    return [JobOut.from_record(record) for record in records]


@router.get("/{job_id}")
def get_job(job_id: uuid.UUID, db: DbSession, scope: StaffScope) -> JobOut:
    return JobOut.from_record(_job(db, scope, job_id))


@router.put("/{job_id}/requirements")
def put_job_requirements(job_id: uuid.UUID, profile: JobProfile, db: DbSession, scope: StaffScope) -> JobOut:
    """Replace the requirement grid with the recruiter-validated version."""
    record = _job(db, scope, job_id)
    return JobOut.from_record(validate_job_requirements(db, record, profile, actor=scope.actor))


@router.put("/{job_id}/weights")
def put_job_weights(job_id: uuid.UUID, weights: ScoringWeights, db: DbSession, scope: StaffScope) -> ScoringWeights:
    """Set this job's scoring weights (relative; normalized over the dimensions that apply)."""
    record = _job(db, scope, job_id)
    return job_weights(set_job_weights(db, record, weights, actor=scope.actor))


@router.get("/{job_id}/ranking")
def get_job_ranking(
    job_id: uuid.UUID,
    db: DbSession,
    settings: AppSettings,
    scope: StaffScope,
    limit: int = Query(20, ge=1, le=200),
    blind: bool = Query(False, description="Hide candidate names (blind screening)."),
) -> RankingOut:
    """Rank the candidates the company can see for a job. Knocked-out candidates are listed separately, never hidden."""
    record = _job(db, scope, job_id)
    run = rank_candidates(
        db,
        record,
        limit=limit,
        full_scoring_limit=settings.full_scoring_limit,
        retrieval_k=settings.retrieval_k,
        consent_required=settings.require_talent_pool_consent,
    )
    return RankingOut(
        job_id=record.id,
        engine_version=engine_version(),
        requirements_validated=record.requirements_validated,
        weights=job_weights(record),
        retrieval_mode=run.mode,
        pool_size=run.pool_size,
        scored=run.scored,
        ranked=[RankedCandidateOut.build(r, blind=blind) for r in run.passed],
        knocked_out=[RankedCandidateOut.build(r, blind=blind) for r in run.knocked_out],
    )


@router.patch("/{job_id}")
def set_job_status(job_id: uuid.UUID, body: JobStatusIn, db: DbSession, scope: StaffScope) -> JobOut:
    """Open or close a job (closed jobs leave the careers page and are not recommended to candidates)."""
    record = _job(db, scope, job_id)
    record.status = body.status
    db.commit()
    return JobOut.from_record(record)


@router.get("/{job_id}/applications")
def list_applications(
    job_id: uuid.UUID,
    db: DbSession,
    scope: StaffScope,
    blind: bool = Query(False, description="Hide candidate names."),
) -> list[ApplicationOut]:
    """The job's pipeline, with each candidate's current score."""
    record = _job(db, scope, job_id)
    return [
        ApplicationOut.build(a, blind=blind, result=score(a.candidate, record)) for a in job_applications(db, record)
    ]
