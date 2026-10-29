"""Deterministic candidate-job matching with explainable factors."""

from .engine import ENGINE_VERSION, match
from .results import Explanation, Factor, FactorStatus, Knockout, KnockoutStatus, MatchResult, ScoringWeights

__all__ = [
    "ENGINE_VERSION",
    "Explanation",
    "Factor",
    "FactorStatus",
    "Knockout",
    "KnockoutStatus",
    "MatchResult",
    "ScoringWeights",
    "match",
]
