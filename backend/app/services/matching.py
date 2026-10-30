"""Score, rank and recommend using the deterministic engine; persist individual matches as history."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.db import ApplicationRecord, AuditLogRecord, CandidateRecord, JobRecord, MatchRecord
from app.extraction.llm import LLMClient
from app.matching import MatchResult, ScoringWeights, match
from app.matching.explain import explain
from app.models import CandidateProfile, JobProfile
from app.search.retrieval import retrieve_candidates


@dataclass
class Ranked:
    candidate: CandidateRecord
    result: MatchResult


@dataclass
class RecommendedJob:
    job: JobRecord
    result: MatchResult


def job_weights(job: JobRecord) -> ScoringWeights:
    return ScoringWeights.model_validate(job.scoring_weights) if job.scoring_weights else ScoringWeights()


def score(candidate: CandidateRecord, job: JobRecord) -> MatchResult:
    return match(
        CandidateProfile.model_validate(candidate.profile),
        JobProfile.model_validate(job.profile),
        weights=job_weights(job),
        requirements_validated=job.requirements_validated,
    )


def create_match(
    db: Session, candidate: CandidateRecord, job: JobRecord, *, llm: LLMClient | None, with_explanation: bool
) -> MatchRecord:
    result = score(candidate, job)
    if with_explanation:
        result.explanation = explain(result, llm)
    record = MatchRecord(
        candidate_id=candidate.id,
        job_id=job.id,
        overall_score=result.overall_score,
        passed_knockouts=result.passed_knockouts,
        factors=result.model_dump(mode="json"),
        explanation=result.explanation.summary if result.explanation else None,
        engine_version=result.engine_version,
    )
    db.add(record)
    db.flush()
    db.add(
        AuditLogRecord(
            actor="system",
            action="match.scored",
            entity_type="match",
            entity_id=record.id,
            details={
                "candidate_id": str(candidate.id),
                "job_id": str(job.id),
                "engine_version": result.engine_version,
                "score": result.overall_score,
            },
        )
    )
    db.commit()
    return record


@dataclass
class RankingRun:
    passed: list[Ranked]
    knocked_out: list[Ranked]
    mode: str
    """"all" (every candidate scored) or "hybrid" (shortlisted by retrieval, then scored)."""
    pool_size: int
    scored: int


def pool_condition(job: JobRecord, *, consent_required: bool) -> ColumnElement[bool]:
    """Who may be matched to a job: everyone, or (with consent required) the talent pool plus the job's applicants."""
    if not consent_required:
        return CandidateRecord.id.is_not(None)
    applicants = select(ApplicationRecord.candidate_id).where(ApplicationRecord.job_id == job.id)
    return or_(CandidateRecord.talent_pool_consent.is_(True), CandidateRecord.id.in_(applicants))


def rank_candidates(
    db: Session,
    job: JobRecord,
    *,
    limit: int,
    full_scoring_limit: int,
    retrieval_k: int,
    consent_required: bool = False,
) -> RankingRun:
    """Score the pool for a job; above `full_scoring_limit` candidates, score only the hybrid-retrieval shortlist."""
    in_pool = pool_condition(job, consent_required=consent_required)
    pool_size = db.scalar(select(func.count()).select_from(CandidateRecord).where(in_pool)) or 0
    if pool_size <= full_scoring_limit:
        mode, candidates = "all", list(db.scalars(select(CandidateRecord).where(in_pool)))
    else:
        shortlist = retrieve_candidates(db, JobProfile.model_validate(job.profile), k=retrieval_k)
        mode = "hybrid"
        candidates = list(
            db.scalars(
                select(CandidateRecord).where(in_pool, CandidateRecord.id.in_([r.candidate_id for r in shortlist]))
            )
        )
    scored = [Ranked(candidate, score(candidate, job)) for candidate in candidates]
    scored.sort(key=lambda r: -r.result.overall_score)
    return RankingRun(
        passed=[r for r in scored if r.result.passed_knockouts][:limit],
        knocked_out=[r for r in scored if not r.result.passed_knockouts][:limit],
        mode=mode,
        pool_size=pool_size,
        scored=len(scored),
    )


def recommend_jobs(
    db: Session, candidate: CandidateRecord, *, limit: int, consent_required: bool = False
) -> list[RecommendedJob]:
    query = select(JobRecord).where(JobRecord.status == "open")
    if consent_required and candidate.talent_pool_consent is not True:
        applied = select(ApplicationRecord.job_id).where(ApplicationRecord.candidate_id == candidate.id)
        query = query.where(JobRecord.id.in_(applied))
    jobs = db.scalars(query)
    recommended = [RecommendedJob(job, score(candidate, job)) for job in jobs]
    recommended.sort(key=lambda r: (not r.result.passed_knockouts, -r.result.overall_score))
    return recommended[:limit]


def set_job_weights(db: Session, job: JobRecord, weights: ScoringWeights, *, actor: str) -> JobRecord:
    job.scoring_weights = weights.model_dump()
    db.add(
        AuditLogRecord(
            actor=actor, action="job.weights_updated", entity_type="job", entity_id=job.id, details=job.scoring_weights
        )
    )
    db.commit()
    return job


def blind_label(candidate_id: uuid.UUID) -> str:
    return f"Candidate {str(candidate_id)[:8]}"
