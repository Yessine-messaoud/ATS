"""Retrieval eval: can hybrid retrieval shortlist the relevant candidates from a large pool?

The 6 labelled fixture candidates are hidden among synthetic distractors; for each fixture job we measure
recall@K of the candidates labelled relevant (>= 1), for vector-only, text-only and hybrid (RRF) retrieval.

Usage (from backend/):  uv run python -m eval.run_retrieval
Needs Postgres. Everything runs inside a transaction that is rolled back: no data is left behind.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db import CandidateRecord, get_engine
from app.models import CandidateProfile
from app.search.embeddings import get_embedder
from app.search.index import index_candidate
from app.search.retrieval import RRF_K, retrieve_candidates

from .distractors import distractor_profiles
from .run_matching import RESULTS, load

DISTRACTORS = 300
KS = (10, 20, 50)


def _insert(db: Session, profile: CandidateProfile) -> CandidateRecord:
    record = CandidateRecord(profile=profile.model_dump(mode="json"), schema_version=profile.schema_version)
    db.add(record)
    db.flush()
    index_candidate(db, record)
    return record


def run(db: Session, distractors: int = DISTRACTORS) -> dict[str, Any]:
    candidates, jobs, labels = load()
    ids = {name: _insert(db, profile).id for name, profile in candidates.items()}
    for profile in distractor_profiles(distractors):
        _insert(db, profile)
    db.flush()

    per_job = []
    for job_name, job in jobs.items():
        relevant = {ids[name] for name, label in labels[job_name].items() if label >= 1}
        hybrid = retrieve_candidates(db, job, k=max(KS))
        row: dict[str, Any] = {"job": job_name, "relevant": len(relevant)}
        for k in KS:
            top = hybrid[:k]
            row[f"recall@{k}"] = round(len(relevant & {r.candidate_id for r in top}) / len(relevant), 3)
            row[f"vector_recall@{k}"] = round(
                len(relevant & {r.candidate_id for r in hybrid if r.vector_rank and r.vector_rank <= k})
                / len(relevant),
                3,
            )
            row[f"text_recall@{k}"] = round(
                len(relevant & {r.candidate_id for r in hybrid if r.text_rank and r.text_rank <= k}) / len(relevant), 3
            )
        row["relevant_ranks"] = sorted(i + 1 for i, r in enumerate(hybrid) if r.candidate_id in relevant)
        per_job.append(row)

    def mean(key: str) -> float:
        return round(sum(float(j[key]) for j in per_job) / len(per_job), 3)

    return {
        "summary": {
            "pool": len(candidates) + distractors,
            **{f"mean_{kind}recall@{k}": mean(f"{kind}recall@{k}") for kind in ("", "vector_", "text_") for k in KS},
        },
        "jobs": per_job,
        "config": {"embedder": get_embedder().name, "rrf_k": RRF_K, "distractors": distractors},
    }


def main() -> int:
    with Session(get_engine()) as db:
        db.begin()
        try:
            report = run(db)
        finally:
            db.rollback()
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"retrieval-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for job in report["jobs"]:
        print(f"{job['job']}: relevant candidates at hybrid ranks {job['relevant_ranks']}")
    print(f"\nFull report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
