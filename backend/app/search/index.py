"""Keep the retrieval index in sync with candidate and job profiles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import CandidateRecord, CandidateSearchRecord, JobRecord, JobSearchRecord
from app.models import CandidateProfile, JobProfile

from .documents import candidate_text, job_text
from .embeddings import Embedder, get_embedder


def index_candidate(db: Session, candidate: CandidateRecord, embedder: Embedder | None = None) -> None:
    embedder = embedder or get_embedder()
    text = candidate_text(CandidateProfile.model_validate(candidate.profile))
    db.merge(
        CandidateSearchRecord(
            candidate_id=candidate.id, model=embedder.name, search_text=text, embedding=embedder.embed([text])[0]
        )
    )


def index_job(db: Session, job: JobRecord, embedder: Embedder | None = None) -> None:
    embedder = embedder or get_embedder()
    text = job_text(JobProfile.model_validate(job.profile))
    db.merge(JobSearchRecord(job_id=job.id, model=embedder.name, search_text=text, embedding=embedder.embed([text])[0]))


def reindex_all(db: Session, embedder: Embedder | None = None) -> dict[str, int]:
    """(Re)build the whole index, e.g. after changing the embedding model."""
    embedder = embedder or get_embedder()
    candidates = list(db.scalars(select(CandidateRecord)))
    jobs = list(db.scalars(select(JobRecord)))
    for candidate in candidates:
        index_candidate(db, candidate, embedder)
    for job in jobs:
        index_job(db, job, embedder)
    db.commit()
    return {"candidates": len(candidates), "jobs": len(jobs)}
