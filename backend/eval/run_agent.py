"""Agent eval: tool selection, confirmation gating, completion, cost and latency on 30 recruiter requests.

Usage (from backend/):  uv run python -m eval.run_agent [--only fairness] [--effort medium]
Needs Postgres and an LLM: local Ollama by default (free), or Claude with LLM_PROVIDER=anthropic, which costs real
API money (one conversation per case, several model calls each).
Runs on the demo seed inside a transaction that is rolled back. Proposed actions are never confirmed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agent.model import AgentModel
from app.agent.prompts import AGENT_PROMPT_VERSION
from app.agent.runtime import send_message
from app.agent.tools import ToolContext
from app.config import Settings
from app.db import AgentConversationRecord, get_engine
from app.extraction import LLMError
from app.providers import make_agent_model, model_label
from scripts.seed_demo import seed

CASES = Path(__file__).parent / "data" / "agent" / "cases.json"
RESULTS = Path(__file__).parent / "results"
PRICE_INPUT, PRICE_OUTPUT = 4.00, 20.00  # USD per million tokens, claude-opus-5-5; local models cost nothing


def load_cases(only: str | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    return [c for c in cases if not only or c["id"].startswith(only) or c["category"] == only]


def called_tools(conversation: AgentConversationRecord) -> list[str]:
    return [
        block["name"]
        for message in conversation.messages
        if message["role"] == "assistant"
        for block in message["content"]
        if block.get("type") == "tool_use"
    ]


def final_text(conversation: AgentConversationRecord) -> str:
    for message in reversed(conversation.messages):
        if message["role"] == "assistant":
            texts = [b["text"] for b in message["content"] if b.get("type") == "text"]
            if texts:
                return "\n".join(texts)
    return ""


def grade(case: dict[str, Any], conversation: AgentConversationRecord, error: str | None) -> dict[str, Any]:
    tools = called_tools(conversation)
    pending = sorted(a["name"] for a in (conversation.pending or {}).get("actions", []))
    checks = {
        "completed": error is None,
        "tool_selection": set(case["must_call"]) <= set(tools),
        "no_forbidden_tool": not set(case["must_not_call"]) & set(tools),
        "confirmation_gating": pending == sorted(case["expect_pending"]),
    }
    usage = conversation.usage or {}
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": all(checks.values()),
        "checks": checks,
        "tools_called": tools,
        "pending_actions": pending,
        "reply": final_text(conversation),
        "manual_review": case.get("manual_review", False),
        "error": error,
        "model_calls": usage.get("calls", 0),
        "latency_ms": usage.get("latency_ms", 0),
        "cost_usd": 0.0
        if str(usage.get("model", "")).startswith("ollama/")
        else round(
            (usage.get("input_tokens", 0) * PRICE_INPUT + usage.get("output_tokens", 0) * PRICE_OUTPUT) / 1e6, 4
        ),
    }


def run(db: Session, model: AgentModel, cases: list[dict[str, Any]], settings: Settings) -> dict[str, Any]:
    seed(db)
    rows = []
    for index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        conversation = AgentConversationRecord(blind=False, messages=[], usage={})
        db.add(conversation)
        db.flush()
        context = ToolContext(
            db=db, blind=False, full_scoring_limit=settings.full_scoring_limit, retrieval_k=settings.retrieval_k
        )
        error = None
        try:
            send_message(db, model, context, conversation, case["request"])
        except LLMError as exc:
            error = str(exc)
        rows.append(grade(case, conversation, error))
        status = "pass" if rows[-1]["passed"] else "FAIL"
        elapsed = time.perf_counter() - started
        print(f"[{index}/{len(cases)}] {status} {case['id']} ({elapsed:.0f}s)", file=sys.stderr, flush=True)

    def rate(key: str) -> float:
        return round(sum(r["checks"][key] for r in rows) / len(rows), 3) if rows else 0.0

    return {
        "summary": {
            "cases": len(rows),
            "passed": sum(r["passed"] for r in rows),
            "completion_rate": rate("completed"),
            "tool_selection_accuracy": rate("tool_selection"),
            "no_forbidden_tool_rate": rate("no_forbidden_tool"),
            "confirmation_gating_accuracy": rate("confirmation_gating"),
            "mean_model_calls": round(sum(r["model_calls"] for r in rows) / max(len(rows), 1), 2),
            "mean_latency_ms": round(sum(r["latency_ms"] for r in rows) / max(len(rows), 1)),
            "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
            "to_review_manually": [r["id"] for r in rows if r["manual_review"]],
        },
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="case id prefix or category")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args()
    settings = Settings()
    effort = args.effort or settings.llm_effort if settings.llm_provider == "anthropic" else None
    model = make_agent_model(settings, effort=args.effort)

    with get_engine().connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            report = run(db, model, load_cases(args.only), settings)
        finally:
            db.close()
            transaction.rollback()
    report["config"] = {
        "model": model_label(settings),
        "effort": effort,
        "prompt_version": AGENT_PROMPT_VERSION,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"agent-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    for row in report["cases"]:
        if not row["passed"]:
            print(
                f"FAIL {row['id']}: {row['checks']} tools={row['tools_called']} pending={row['pending_actions']}",
                file=sys.stderr,
            )
    print(f"\nFull report (replies for manual review included): {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
