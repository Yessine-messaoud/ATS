from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import CandidateRecord, JobRecord
from app.models import CandidateProfile, JobProfile
from app.search.documents import candidate_text
from app.search.embeddings import HashingEmbedder, cosine
from app.search.index import index_candidate
from app.search.retrieval import tsquery
from app.services.matching import rank_candidates
from eval.run_retrieval import run as run_retrieval
from tests.test_matching import CANDIDATE, JOB


def test_hashing_embedder_is_deterministic_normalized_and_surface_aware() -> None:
    embedder = HashingEmbedder()
    a, b, c = embedder.embed(["PostgreSQL databases", "Postgres database", "intensive care nursing"])

    assert embedder.embed(["PostgreSQL databases"])[0] == a
    assert abs(cosine(a, a) - 1) < 1e-9
    assert cosine(a, b) > cosine(a, c) + 0.2


def test_candidate_text_excludes_identity_and_unverified_skills_but_expands_implications() -> None:
    profile = CandidateProfile.model_validate(
        {
            **CANDIDATE,
            "skills": [*CANDIDATE["skills"], {"name": "Kubernetes", "evidence": "hidden", "verified": False}],
        }
    )

    text = candidate_text(profile)

    assert "Samira" not in text and "samira@example.com" not in text and "+216" not in text
    assert "kubernetes" not in text
    assert "sql" in text.split()  # implied by PostgreSQL


def test_tsquery_only_passes_safe_tokens() -> None:
    assert tsquery(["apache spark", "c++", "node.js", "'; drop table x; --"]) == (
        "(apache <-> spark) | (c) | (node <-> js) | (drop <-> table <-> x)"
    )
    assert tsquery(["!!!"]) is None


def test_hybrid_retrieval_recovers_relevant_candidates_from_a_large_pool(db: Session) -> None:
    summary = run_retrieval(db, distractors=150)["summary"]

    assert summary["mean_recall@20"] == 1
    assert summary["mean_recall@10"] >= 0.9


def test_large_pools_are_shortlisted_then_scored(db: Session) -> None:
    for name in ("Ana", "Ben", "Cyd"):
        record = CandidateRecord(profile={**CANDIDATE, "identity": {"full_name": name}}, schema_version="2")
        db.add(record)
        db.flush()
        index_candidate(db, record)
    job = JobRecord(
        title="Data Engineer", profile=JobProfile.model_validate(JOB).model_dump(mode="json"), schema_version="2"
    )
    db.add(job)
    db.flush()

    exhaustive = rank_candidates(db, job, limit=10, full_scoring_limit=10, retrieval_k=2)
    shortlisted = rank_candidates(db, job, limit=10, full_scoring_limit=2, retrieval_k=2)

    assert (exhaustive.mode, exhaustive.scored) == ("all", 3)
    assert (shortlisted.mode, shortlisted.pool_size, shortlisted.scored) == ("hybrid", 3, 2)
    assert len(db.scalars(select(CandidateRecord)).all()) == 3
