"""Run the extraction eval against the real LLM and write a dated report to eval/results/.

Usage (from backend/):  uv run python -m eval.run_extraction [--only en-01] [--effort medium]
Costs real API money: roughly one LLM call per document, more when a correction round is needed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from app.extraction import CANDIDATE_TARGET, JOB_TARGET, ExtractionFailed, LLMError, extract
from app.extraction.anthropic_client import AnthropicLLM
from app.ingestion import ingest_document

from .metrics import SetScore, score_candidate, score_job
from .render import render_pdf

DATA = Path(__file__).parent / "data"
RESULTS = Path(__file__).parent / "results"
# USD per million tokens for the default model (claude-opus-5-5); update when changing models.
PRICE_INPUT, PRICE_OUTPUT = 4.00, 20.00


def _cases(kind: str, only: str | None) -> list[tuple[str, str, dict[str, Any]]]:
    cases = []
    for text_file in sorted((DATA / kind).glob("*.txt")):
        if only and not text_file.stem.startswith(only):
            continue
        gold = json.loads(text_file.with_suffix(".gold.json").read_text(encoding="utf-8"))
        cases.append((text_file.stem, text_file.read_text(encoding="utf-8"), gold))
    return cases


def _cost(meta: dict[str, Any]) -> float:
    return float(meta["input_tokens"] * PRICE_INPUT + meta["output_tokens"] * PRICE_OUTPUT) / 1_000_000


def run(llm: AnthropicLLM, settings: Settings, only: str | None) -> dict[str, Any]:
    totals: dict[str, SetScore] = {}
    report: dict[str, Any] = {"cases": [], "errors": []}
    unverified = items = 0
    cost = latency = 0.0

    def accumulate(name: str, case_scores: dict[str, Any], meta: dict[str, Any], evidence: dict[str, Any]) -> None:
        nonlocal unverified, items, cost, latency
        for field_name, value in case_scores.items():
            if isinstance(value, SetScore):
                totals.setdefault(field_name, SetScore()).add(value)
        unverified += evidence["unverified"]
        items += evidence["items"]
        cost += _cost(meta)
        latency += meta["latency_ms"]
        report["cases"].append(
            {
                "case": name,
                **{k: v.as_dict() if isinstance(v, SetScore) else v for k, v in case_scores.items()},
                "evidence": evidence,
                "llm_calls": meta["llm_calls"],
                "latency_ms": meta["latency_ms"],
                "cost_usd": round(_cost(meta), 4),
            }
        )

    for name, text, gold in _cases("cvs", only):
        try:
            document = ingest_document(render_pdf(text, hidden_lines=gold.get("hidden_text")), settings)
            candidate = extract(llm, CANDIDATE_TARGET, document.text, max_repairs=settings.extraction_max_repairs)
        except (ExtractionFailed, LLMError) as exc:
            report["errors"].append({"case": name, "error": str(exc)})
            continue
        scores = score_candidate(candidate.profile, gold)
        scores["flags"] = [flag.value for flag in document.flags]
        scores["missing_flags"] = [f for f in gold.get("expect_flags", []) if f not in scores["flags"]]
        accumulate(name, scores, candidate.meta, candidate.summary()["evidence"])

    for name, text, gold in _cases("jobs", only):
        try:
            job = extract(llm, JOB_TARGET, text, max_repairs=settings.extraction_max_repairs)
        except (ExtractionFailed, LLMError) as exc:
            report["errors"].append({"case": name, "error": str(exc)})
            continue
        accumulate(name, score_job(job.profile, gold), job.meta, job.summary()["evidence"])

    cases = report["cases"]
    report["summary"] = {
        "documents": len(cases),
        "errors": len(report["errors"]),
        **{f"{name}_f1": round(score.f1, 3) for name, score in sorted(totals.items())},
        **{f"{name}_precision": round(score.precision, 3) for name, score in sorted(totals.items())},
        **{f"{name}_recall": round(score.recall, 3) for name, score in sorted(totals.items())},
        "unverified_rate": round(unverified / items, 3) if items else 0.0,
        "sensitive_leaks": sum(len(c.get("sensitive_leaks", [])) for c in cases),
        "missing_security_flags": sum(len(c.get("missing_flags", [])) for c in cases),
        "scalar_accuracy": round(
            sum(sum(c["scalars"].values()) for c in cases) / max(sum(len(c["scalars"]) for c in cases), 1), 3
        ),
        "mean_latency_ms": round(latency / len(cases)) if cases else 0,
        "total_cost_usd": round(cost, 4),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="run only cases whose name starts with this prefix")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args()

    settings = Settings()
    llm = AnthropicLLM(
        model=settings.llm_model, effort=args.effort or settings.llm_effort, max_tokens=settings.llm_max_tokens
    )
    report = run(llm, settings, args.only)
    report["config"] = {
        "model": settings.llm_model,
        "effort": args.effort or settings.llm_effort,
        "prompt_versions": [CANDIDATE_TARGET.prompt_version, JOB_TARGET.prompt_version],
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"extraction-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for error in report["errors"]:
        print(f"ERROR {error['case']}: {error['error']}", file=sys.stderr)
    print(f"\nFull report: {out}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
