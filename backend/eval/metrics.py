"""Deterministic scoring of extracted profiles against gold annotations."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from app.matching.knockouts import language_key
from app.models import CandidateProfile, JobProfile, RequirementKind

FUZZY_MATCH = 88
# Equivalent spellings that fuzzy matching alone does not reconcile.
ALIASES = {
    "spark": "apache spark",
    "postgres": "postgresql",
    "gcp": "google cloud platform",
    "google cloud": "google cloud platform",
    "k8s": "kubernetes",
    "sklearn": "scikit-learn",
    "js": "javascript",
    "nodejs": "node.js",
    "node": "node.js",
    "expressjs": "express",
    "express.js": "express",
    "reactjs": "react",
    "react.js": "react",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "microsoft power bi": "power bi",
    "amazon web services": "aws",
    "gitlab ci/cd": "gitlab ci",
    "argo cd": "argocd",
    "onnx runtime": "onnx runtime",
    "star schema": "star schema modeling",
    "dimensional modeling": "star schema modeling",
}


def norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    stripped = re.sub(r"\s+", " ", stripped).strip(" .")
    return ALIASES.get(stripped, stripped)


def _matches(a: str, b: str, *, lenient: bool = False) -> bool:
    """Strict: whole-string similarity, so "SQL" does not match "SQL Server" (two different skills).
    Lenient (names of organisations and titles): word-subset matches count, so "ISITCom" matches
    "Higher Institute ... (ISITCom)"."""
    na, nb = norm(a), norm(b)
    if na == nb:
        return True
    if lenient:
        return fuzz.token_set_ratio(na, nb) >= FUZZY_MATCH
    return fuzz.ratio(na, nb) >= FUZZY_MATCH


@dataclass
class SetScore:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    false_positives: list[str] = field(default_factory=list)
    false_negatives: list[str] = field(default_factory=list)

    def add(self, other: SetScore) -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


def score_sets(predicted: Iterable[str], gold: Iterable[str], *, lenient: bool = False) -> SetScore:
    """Greedy one-to-one matching with normalization, aliases and fuzzy comparison."""
    remaining = list(dict.fromkeys(gold))
    score = SetScore()
    for item in dict.fromkeys(predicted):
        match = next((g for g in remaining if _matches(item, g, lenient=lenient)), None)
        if match is None:
            score.fp += 1
            score.false_positives.append(item)
        else:
            score.tp += 1
            remaining.remove(match)
    score.fn = len(remaining)
    score.false_negatives = remaining
    return score


def _language_score(predicted: dict[str, str | None], gold: dict[str, str | None]) -> SetScore:
    # Compare names first, then levels only where the gold states one. Names go through the matching engine's
    # normalisation ("Anglais" = "English"): a name the engine reads correctly is a correct extraction.
    predicted = {language_key(name): level for name, level in predicted.items()}
    gold = {language_key(name): level for name, level in gold.items()}
    score = SetScore()
    for name, level in gold.items():
        found = next((p for p in predicted if _matches(p, name)), None)
        if found is None:
            score.fn += 1
            score.false_negatives.append(name)
        elif level is None or (predicted[found] or "").lower() == level.lower():
            score.tp += 1
        else:
            score.fp += 1
            score.fn += 1
            score.false_positives.append(f"{found}:{predicted[found]}")
            score.false_negatives.append(f"{name}:{level}")
    for name in predicted:
        if not any(_matches(name, g) for g in gold):
            score.fp += 1
            score.false_positives.append(name)
    return score


def score_candidate(profile: CandidateProfile, gold: dict[str, Any]) -> dict[str, Any]:
    dump = profile.model_dump_json().lower()
    return {
        "skills": score_sets([s.name for s in profile.skills], gold["skills"]),
        "experiences": score_sets(
            [f"{e.company} | {e.job_title}" for e in profile.experiences],
            [f"{e['company']} | {e['job_title']}" for e in gold["experiences"]],
            lenient=True,
        ),
        "education": score_sets([e.institution for e in profile.education], gold["education"], lenient=True),
        "certifications": score_sets([c.name for c in profile.certifications], gold["certifications"], lenient=True),
        "languages": _language_score(
            {lang.language: lang.level.value if lang.level else None for lang in profile.languages}, gold["languages"]
        ),
        "scalars": {
            "full_name": _matches(profile.identity.full_name or "", gold["full_name"], lenient=True),
            "email": (profile.identity.email or "").lower() == gold["email"].lower(),
        },
        "sensitive_leaks": [term for term in gold.get("must_not_contain", []) if term.lower() in dump],
    }


def score_job(profile: JobProfile, gold: dict[str, Any]) -> dict[str, Any]:
    required = [s.name for s in profile.skill_requirements if s.requirement is RequirementKind.REQUIRED]
    preferred = [s.name for s in profile.skill_requirements if s.requirement is RequirementKind.PREFERRED]
    return {
        "required_skills": score_sets(required, gold["required_skills"]),
        "preferred_skills": score_sets(preferred, gold["preferred_skills"]),
        "languages": _language_score(
            {lang.language: lang.level.value if lang.level else None for lang in profile.language_requirements},
            gold["languages"],
        ),
        "scalars": {
            "title": _matches(profile.title, gold["title"], lenient=True),
            "contract_type": (profile.contract_type.value if profile.contract_type else None) == gold["contract_type"],
            "work_mode": (profile.work_mode.value if profile.work_mode else None) == gold["work_mode"],
            "minimum_years": profile.experience.minimum_years == gold["minimum_years"],
            "currency": (
                str(profile.compensation.currency) if profile.compensation and profile.compensation.currency else None
            )
            == gold["currency"],
        },
    }
