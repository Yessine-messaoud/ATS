"""Match result models. Every number shown to a recruiter is traceable to a `Factor`."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FactorStatus(StrEnum):
    MET = "met"
    PARTIAL = "partial"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNVERIFIED = "unverified"


POSITIVE_STATUSES = {FactorStatus.MET, FactorStatus.PARTIAL}
NEGATIVE_STATUSES = {FactorStatus.PARTIAL, FactorStatus.MISSING, FactorStatus.UNKNOWN, FactorStatus.UNVERIFIED}


class Factor(BaseModel):
    """One observable fact behind the score, with a stable id that explanations must cite."""

    id: str
    label: str
    status: FactorStatus
    detail: str
    value: float | None = None


class KnockoutStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class Knockout(BaseModel):
    criterion: str
    status: KnockoutStatus
    detail: str
    factor_id: str


class DimensionScore(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=1, description="Normalized weight among applicable dimensions.")
    points: float = Field(description="Contribution to the 0-100 score before the missing-skill penalty.")
    factors: list[Factor] = Field(default_factory=list)


class ScoringWeights(BaseModel):
    """Per-job configurable weights (relative; normalized over the dimensions that apply to a job)."""

    required_skills: float = Field(default=40, ge=0)
    preferred_skills: float = Field(default=15, ge=0)
    experience: float = Field(default=20, ge=0)
    seniority: float = Field(default=10, ge=0)
    languages: float = Field(default=5, ge=0)
    education: float = Field(default=5, ge=0)
    location: float = Field(default=5, ge=0)
    missing_required_penalty: float = Field(
        default=0.08, ge=0, le=0.5, description="Multiplicative penalty per missing required skill."
    )
    knockouts_enabled: bool = True

    @model_validator(mode="after")
    def some_weight(self) -> ScoringWeights:
        if self.dimension_weights() == {} or sum(self.dimension_weights().values()) == 0:
            raise ValueError("at least one dimension weight must be positive")
        return self

    def dimension_weights(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in DIMENSIONS}


DIMENSIONS = (
    "required_skills",
    "preferred_skills",
    "experience",
    "seniority",
    "languages",
    "education",
    "location",
)


class Claim(BaseModel):
    text: str
    factor_ids: list[str] = Field(min_length=1)


class InterviewQuestion(BaseModel):
    question: str
    factor_ids: list[str] = Field(min_length=1)


class Explanation(BaseModel):
    summary: str
    strengths: list[Claim] = Field(default_factory=list)
    gaps: list[Claim] = Field(default_factory=list)
    interview_questions: list[InterviewQuestion] = Field(default_factory=list)
    source: Literal["llm", "template"] = "template"
    dropped_claims: list[str] = Field(
        default_factory=list, description="LLM claims rejected by the faithfulness check."
    )


class MatchResult(BaseModel):
    engine_version: str
    overall_score: float = Field(ge=0, le=100)
    raw_score: float = Field(ge=0, le=100, description="Weighted score before the missing-skill penalty.")
    penalty_multiplier: float
    passed_knockouts: bool
    knockouts: list[Knockout]
    dimensions: list[DimensionScore]
    matched_required: list[str]
    missing_required: list[str]
    ignored_unverified: list[str] = Field(default_factory=list)
    requirements_validated: bool = False
    explanation: Explanation | None = None

    def factors(self) -> dict[str, Factor]:
        found = {f.id: f for d in self.dimensions for f in d.factors}
        for knockout in self.knockouts:
            status = {
                KnockoutStatus.PASS: FactorStatus.MET,
                KnockoutStatus.FAIL: FactorStatus.MISSING,
                KnockoutStatus.UNKNOWN: FactorStatus.UNKNOWN,
            }[knockout.status]
            found.setdefault(
                knockout.factor_id,
                Factor(id=knockout.factor_id, label=knockout.criterion, status=status, detail=knockout.detail),
            )
        for dimension in self.dimensions:
            found[f"dimension:{dimension.name}"] = Factor(
                id=f"dimension:{dimension.name}",
                label=dimension.name.replace("_", " "),
                status=FactorStatus.MET
                if dimension.score >= 0.75
                else FactorStatus.PARTIAL
                if dimension.score > 0.25
                else FactorStatus.MISSING,
                detail=f"{dimension.name.replace('_', ' ')} score {round(dimension.score * 100)}/100",
                value=round(dimension.score * 100),
            )
        found["overall"] = Factor(
            id="overall",
            label="overall score",
            status=FactorStatus.MET if self.overall_score >= 70 else FactorStatus.PARTIAL,
            detail=f"overall score {self.overall_score:g}/100",
            value=self.overall_score,
        )
        return found
