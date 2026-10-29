"""Explanations generated only from score factors, with a deterministic faithfulness check.

The LLM sees the factors (no CV text, no personal data) and must cite factor ids for every claim. Claims citing
unknown factors, citing a factor with the wrong polarity, or stating numbers that do not appear in the cited
factors are dropped. Without an LLM, a template explanation is produced from the same factors.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.extraction.llm import LLMClient, LLMError, ToolSpec

from .results import (
    NEGATIVE_STATUSES,
    POSITIVE_STATUSES,
    Claim,
    Explanation,
    Factor,
    FactorStatus,
    InterviewQuestion,
    KnockoutStatus,
    MatchResult,
)

EXPLANATION_PROMPT_VERSION = "explain-v1"
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
MAX_ITEMS = 5

SYSTEM_PROMPT = """\
You explain a candidate-job match score to a recruiter. The score was computed by a deterministic engine; you do not \
change it or judge the candidate yourself. You receive only the scoring factors, each with an id, a status and a \
detail. Call the `record_match_explanation` tool once.

Rules:
- Every strength, gap and interview question cites the ids of the factors it is based on (`factor_ids`).
- Strengths cite factors with status met or partial; gaps cite factors with status partial, missing, unknown or \
unverified; failed or unknown knock-outs are always mentioned as gaps.
- Use only numbers that appear in the cited factors. Do not invent facts, skills or years.
- Interview questions help the recruiter verify gaps or unknowns; they are open, job-related and never ask about \
age, family, origin, religion, health or other protected characteristics.
- Be concise: a two-sentence summary, at most five strengths, five gaps and four questions. Write in the language \
requested."""


class _Draft(BaseModel):
    summary: str
    strengths: list[Claim] = Field(default_factory=list)
    gaps: list[Claim] = Field(default_factory=list)
    interview_questions: list[InterviewQuestion] = Field(default_factory=list)


TOOL = ToolSpec(
    name="record_match_explanation",
    description="Record the explanation of the match score, citing factor ids for every claim.",
    input_schema=_Draft.model_json_schema(),
)


def _factor_payload(result: MatchResult) -> list[dict[str, Any]]:
    return [
        {"id": f.id, "label": f.label, "status": f.status.value, "detail": f.detail, "value": f.value}
        for f in result.factors().values()
    ]


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in NUMBER_RE.findall(text)}


def _allowed_numbers(factors: list[Factor]) -> set[str]:
    allowed: set[str] = set()
    for factor in factors:
        allowed |= _numbers(f"{factor.label} {factor.detail}")
        if factor.value is not None:
            allowed |= {f"{factor.value:g}", str(round(factor.value)), str(round(factor.value * 100))}
    return allowed


def _faithful(text: str, ids: list[str], factors: dict[str, Factor]) -> str | None:
    """None when the claim is supported, else the reason it is not."""
    cited = [factors[i] for i in ids if i in factors]
    if len(cited) != len(ids):
        return f"cites unknown factor(s): {sorted(set(ids) - factors.keys())}"
    unsupported = _numbers(text) - _allowed_numbers(cited) - _allowed_numbers([factors["overall"]])
    if unsupported:
        return f"numbers not in the cited factors: {sorted(unsupported)}"
    return None


def check_faithfulness(draft: _Draft, result: MatchResult) -> Explanation:
    factors = result.factors()
    dropped: list[str] = []

    def keep(claims: list[Claim], polarity: set[FactorStatus]) -> list[Claim]:
        kept = []
        for claim in claims:
            reason = _faithful(claim.text, claim.factor_ids, factors)
            if reason is None and not any(factors[i].status in polarity for i in claim.factor_ids):
                reason = "cited factors have the opposite status"
            if reason is None:
                kept.append(claim)
            else:
                dropped.append(f"{claim.text} ({reason})")
        return kept[:MAX_ITEMS]

    questions = []
    for question in draft.interview_questions:
        reason = _faithful(question.question, question.factor_ids, factors)
        if reason is None:
            questions.append(question)
        else:
            dropped.append(f"{question.question} ({reason})")

    summary = draft.summary
    if _numbers(summary) - _allowed_numbers(list(factors.values())):
        dropped.append(f"{summary} (summary states numbers not in the factors)")
        summary = template_explanation(result).summary
    return Explanation(
        summary=summary,
        strengths=keep(draft.strengths, POSITIVE_STATUSES),
        gaps=keep(draft.gaps, NEGATIVE_STATUSES),
        interview_questions=questions[:4],
        source="llm",
        dropped_claims=dropped,
    )


def template_explanation(result: MatchResult) -> Explanation:
    """Deterministic explanation from the factors, used without an LLM and as a fallback."""
    factors = result.factors()
    skill_factors = [f for d in result.dimensions if d.name.endswith("skills") for f in d.factors]
    strengths = [
        Claim(text=f"{f.label}: {f.detail}", factor_ids=[f.id]) for f in skill_factors if f.status is FactorStatus.MET
    ]
    strengths += [
        Claim(text=f"{factors[f'dimension:{d.name}'].detail}", factor_ids=[f"dimension:{d.name}"])
        for d in result.dimensions
        if not d.name.endswith("skills") and d.score >= 0.9
    ]
    gaps = [
        Claim(text=f"Knock-out {k.status.value}: {k.criterion} ({k.detail})", factor_ids=[k.factor_id])
        for k in result.knockouts
        if k.status is not KnockoutStatus.PASS
    ]
    gaps += [
        Claim(text=f"{f.label}: {f.detail}", factor_ids=[f.id])
        for d in result.dimensions
        for f in d.factors
        if f.status in (FactorStatus.MISSING, FactorStatus.UNVERIFIED, FactorStatus.UNKNOWN)
    ]
    questions = [
        InterviewQuestion(
            question=f"Can you describe a concrete piece of work where you used {f.label}?", factor_ids=[f.id]
        )
        for f in skill_factors
        if f.status in (FactorStatus.PARTIAL, FactorStatus.UNVERIFIED)
    ]
    questions += [
        InterviewQuestion(question=f"Could you confirm: {k.criterion}?", factor_ids=[k.factor_id])
        for k in result.knockouts
        if k.status is KnockoutStatus.UNKNOWN
    ]
    verdict = (
        "strong match"
        if result.overall_score >= 75
        else "partial match"
        if result.overall_score >= 50
        else "weak match"
    )
    knockout_note = "" if result.passed_knockouts else " A mandatory criterion is not met."
    missing = f" Missing required skills: {', '.join(result.missing_required)}." if result.missing_required else ""
    return Explanation(
        summary=f"Overall score {result.overall_score:g}/100 ({verdict}).{missing}{knockout_note}",
        strengths=strengths[:MAX_ITEMS],
        gaps=gaps[:MAX_ITEMS],
        interview_questions=questions[:4],
        source="template",
    )


def explain(result: MatchResult, llm: LLMClient | None, *, language: str = "English") -> Explanation:
    """LLM explanation checked for faithfulness; the template is used when no LLM is available or it fails."""
    if llm is None:
        return template_explanation(result)
    prompt = (
        f"Language: {language}\n"
        f"Overall score: {result.overall_score:g}/100; passed knock-outs: {result.passed_knockouts}.\n"
        f"Factors:\n{json.dumps(_factor_payload(result), ensure_ascii=False, indent=1)}"
    )
    try:
        session = llm.session(system=SYSTEM_PROMPT, tool=TOOL)
        call = session.start(prompt)
        if call.data is None:
            call = session.correct("Call `record_match_explanation` with the explanation.")
        if call.data is None:
            return template_explanation(result)
        draft = _Draft.model_validate(call.data)
    except (LLMError, ValidationError):
        return template_explanation(result)
    return check_faithfulness(draft, result)
