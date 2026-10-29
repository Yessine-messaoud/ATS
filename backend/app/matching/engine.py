"""Deterministic matching engine: knock-outs, weighted dimensions, missing-skill penalty.

No LLM is involved. Given the same profiles, weights and date, the result is identical.
"""

from __future__ import annotations

from datetime import date

from app.models import CandidateProfile, JobProfile, RequirementKind

from .features import relevant_experience_months, skill_index
from .knockouts import evaluate_knockouts
from .results import DimensionScore, KnockoutStatus, MatchResult, ScoringWeights
from .scoring import (
    score_education,
    score_experience,
    score_languages,
    score_location,
    score_seniority,
    score_skills,
)
from .skills import canonical, normalize_text
from .taxonomy import active_taxonomy

ENGINE_VERSION = "match-v1"


def engine_version() -> str:
    """Engine version plus the active taxonomy, so every stored score is traceable to the rules that produced it."""
    taxonomy = active_taxonomy()
    return f"{ENGINE_VERSION}+{taxonomy.version}" if taxonomy else ENGINE_VERSION


def _relevant_keys(job: JobProfile) -> set[str]:
    keys = {canonical(r.name) for r in job.skill_requirements}
    keys |= {normalize_text(d) for d in job.experience.relevant_domains + job.technical_domains}
    return keys


def match(
    candidate: CandidateProfile,
    job: JobProfile,
    *,
    weights: ScoringWeights | None = None,
    today: date | None = None,
    requirements_validated: bool = False,
) -> MatchResult:
    weights = weights or ScoringWeights()
    today = today or date.today()
    relevant = _relevant_keys(job)
    index = skill_index(candidate, today, sought={canonical(r.name) for r in job.skill_requirements})
    relevant_months, _ = relevant_experience_months(candidate, today, relevant)

    required, required_matches = score_skills(job, RequirementKind.REQUIRED, index, today)
    preferred, preferred_matches = score_skills(job, RequirementKind.PREFERRED, index, today)
    scored = {
        "required_skills": required,
        "preferred_skills": preferred,
        "experience": score_experience(candidate, job, relevant, today),
        "seniority": score_seniority(candidate, job, today),
        "languages": score_languages(candidate, job),
        "education": score_education(candidate, job, relevant_months, today),
        "location": score_location(candidate, job),
    }
    applicable = {name: s for name, s in scored.items() if s is not None and weights.dimension_weights()[name] > 0}
    total_weight = sum(weights.dimension_weights()[name] for name in applicable) or 1.0

    dimensions = []
    raw = 0.0
    for name, (score, factors) in applicable.items():
        weight = weights.dimension_weights()[name] / total_weight
        raw += weight * score
        dimensions.append(
            DimensionScore(
                name=name,
                score=round(score, 4),
                weight=round(weight, 4),
                points=round(100 * weight * score, 1),
                factors=factors,
            )
        )

    missing = [m.requirement for m in required_matches if m.credit == 0]
    penalty = (1 - weights.missing_required_penalty) ** len(missing)
    knockouts = evaluate_knockouts(candidate, job) if weights.knockouts_enabled else []
    return MatchResult(
        engine_version=engine_version(),
        overall_score=round(100 * raw * penalty, 1),
        raw_score=round(100 * raw, 1),
        penalty_multiplier=round(penalty, 4),
        passed_knockouts=all(k.status is not KnockoutStatus.FAIL for k in knockouts),
        knockouts=knockouts,
        dimensions=dimensions,
        matched_required=[m.requirement for m in required_matches if m.credit > 0],
        missing_required=missing,
        ignored_unverified=sorted(
            {m.requirement for m in required_matches + preferred_matches if m.unverified and m.credit == 0}
        ),
        requirements_validated=requirements_validated,
    )
