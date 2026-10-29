"""Hybrid retrieval: vector similarity + Postgres full-text search, fused with Reciprocal Rank Fusion.

Retrieval only decides which candidates get scored when the pool is large. The ranking itself always comes from
the deterministic matching engine.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import CandidateSearchRecord
from app.models import JobProfile

from .documents import job_keywords, job_text
from .embeddings import Embedder, get_embedder

RRF_K = 60
WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Retrieved:
    candidate_id: uuid.UUID
    score: float
    vector_rank: int | None
    text_rank: int | None


def tsquery(terms: list[str]) -> str | None:
    """OR of the terms; multi-word terms become phrases ("apache <-> spark"). Only [a-z0-9] reaches the query."""
    phrases = []
    for term in terms:
        words = WORD_RE.findall(term.lower())
        if words:
            phrases.append("(" + " <-> ".join(words) + ")")
    return " | ".join(dict.fromkeys(phrases)) or None


def retrieve_candidates(db: Session, job: JobProfile, *, k: int, embedder: Embedder | None = None) -> list[Retrieved]:
    embedder = embedder or get_embedder()
    query_vector = embedder.embed([job_text(job)])[0]
    vector_ids = list(
        db.scalars(
            select(CandidateSearchRecord.candidate_id)
            .order_by(CandidateSearchRecord.embedding.cosine_distance(query_vector))
            .limit(k)
        )
    )
    text_ids: list[uuid.UUID] = []
    query = tsquery(job_keywords(job))
    if query:
        ts_query = func.to_tsquery("simple", query)
        text_ids = list(
            db.scalars(
                select(CandidateSearchRecord.candidate_id)
                .where(CandidateSearchRecord.tsv.op("@@")(ts_query))
                .order_by(func.ts_rank_cd(CandidateSearchRecord.tsv, ts_query).desc())
                .limit(k)
            )
        )

    vector_rank = {cid: rank for rank, cid in enumerate(vector_ids, start=1)}
    text_rank = {cid: rank for rank, cid in enumerate(text_ids, start=1)}
    fused = [
        Retrieved(
            candidate_id=cid,
            score=sum(1 / (RRF_K + r) for r in (vector_rank.get(cid), text_rank.get(cid)) if r is not None),
            vector_rank=vector_rank.get(cid),
            text_rank=text_rank.get(cid),
        )
        for cid in dict.fromkeys(vector_ids + text_ids)
    ]
    fused.sort(key=lambda r: -r.score)
    return fused[:k]
