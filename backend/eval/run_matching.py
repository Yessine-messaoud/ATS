"""Matching eval: rank the fixture candidates for each fixture job and compare with human relevance labels.

Usage (from backend/):  uv run python -m eval.run_matching
Deterministic and free: no LLM call. The evaluation date is fixed so results are reproducible.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.matching import ENGINE_VERSION, MatchResult, match
from app.models import CandidateProfile, JobProfile

from .ranking_metrics import ndcg_at_k, spearman

DATA = Path(__file__).parent / "data" / "matching"
RESULTS = Path(__file__).parent / "results"
EVAL_DATE = date(2026, 10, 29)
RELEVANT = 2  # labels >= 2 count as relevant for precision@k


def ranking_order(results: dict[str, MatchResult]) -> list[str]:
    """The order shown to recruiters: candidates passing knock-outs first, each group by descending score."""
    return sorted(results, key=lambda name: (not results[name].passed_knockouts, -results[name].overall_score))


def load() -> tuple[dict[str, CandidateProfile], dict[str, JobProfile], dict[str, dict[str, int]]]:
    candidates = {
        p.stem: CandidateProfile.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted((DATA / "candidates").glob("*.json"))
    }
    jobs = {
        p.stem: JobProfile.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted((DATA / "jobs").glob("*.json"))
    }
    labels = json.loads((DATA / "relevance.json").read_text(encoding="utf-8"))
    return candidates, jobs, {k: v for k, v in labels.items() if not k.startswith("_")}


def run() -> dict[str, Any]:
    candidates, jobs, labels = load()
    per_job: list[dict[str, Any]] = []
    for job_name, job in jobs.items():
        results = {name: match(profile, job, today=EVAL_DATE) for name, profile in candidates.items()}
        order = ranking_order(results)
        ranked_labels = [labels[job_name][name] for name in order]
        per_job.append(
            {
                "job": job_name,
                "ndcg@3": round(ndcg_at_k(ranked_labels, 3), 3),
                "ndcg@all": round(ndcg_at_k(ranked_labels, len(order)), 3),
                "spearman": round(
                    spearman([results[n].overall_score for n in order], [labels[job_name][n] for n in order]), 3
                ),
                "top1_is_best": labels[job_name][order[0]] == max(labels[job_name].values()),
                "precision@1": float(ranked_labels[0] >= RELEVANT),
                "ranking": [
                    {
                        "candidate": name,
                        "label": labels[job_name][name],
                        "score": results[name].overall_score,
                        "passed_knockouts": results[name].passed_knockouts,
                        "missing_required": results[name].missing_required,
                    }
                    for name in order
                ],
            }
        )

    def mean(key: str) -> float:
        return round(sum(float(j[key]) for j in per_job) / len(per_job), 3)

    return {
        "summary": {
            "jobs": len(per_job),
            "candidates": len(candidates),
            "mean_ndcg@3": mean("ndcg@3"),
            "mean_ndcg@all": mean("ndcg@all"),
            "mean_spearman": mean("spearman"),
            "top1_accuracy": mean("top1_is_best"),
            "mean_precision@1": mean("precision@1"),
        },
        "jobs": per_job,
        "config": {"engine_version": ENGINE_VERSION, "eval_date": EVAL_DATE.isoformat()},
    }


def main() -> int:
    report = run()
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"matching-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for job in report["jobs"]:
        print(f"\n{job['job']}  ndcg@3={job['ndcg@3']}  spearman={job['spearman']}")
        for row in job["ranking"]:
            knocked = "" if row["passed_knockouts"] else "  [knocked out]"
            print(f"  {row['score']:5.1f}  label={row['label']}  {row['candidate']}{knocked}")
    print(f"\nFull report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
