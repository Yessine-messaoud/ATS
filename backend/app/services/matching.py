"""Score, rank and recommend using the deterministic engine; persist individual matches as history."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import AuditLogRecord, CandidateRecord, JobRecord, MatchRecord
from app.extraction.llm import LLMClient
from app.matching import MatchResult, ScoringWeights, match
from app.matching.explain import explain
from app.models import CandidateProfile, JobProfile


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


def rank_candidates(db: Session, job: JobRecord, *, limit: int) -> tuple[list[Ranked], list[Ranked]]:
    """(candidates passing knock-outs, knocked-out candidates), each by descending score."""
    scored = [Ranked(candidate, score(candidate, job)) for candidate in db.scalars(select(CandidateRecord))]
    scored.sort(key=lambda r: -r.result.overall_score)
    passed = [r for r in scored if r.result.passed_knockouts]
    knocked_out = [r for r in scored if not r.result.passed_knockouts]
    return passed[:limit], knocked_out[:limit]


def recommend_jobs(db: Session, candidate: CandidateRecord, *, limit: int) -> list[RecommendedJob]:
    jobs = db.scalars(select(JobRecord).where(JobRecord.status == "open"))
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
