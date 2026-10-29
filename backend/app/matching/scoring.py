"""Per-dimension scorers. Each returns (score in [0, 1], factors), or None when the job does not use the dimension."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from rapidfuzz import fuzz

from app.models import CandidateProfile, ContractType, JobProfile, RequirementKind, SeniorityLevel, WorkMode

from .features import (
    SENIORITY_ORDER,
    SkillEvidence,
    candidate_seniority,
    relevant_experience_months,
    skill_strength,
)
from .knockouts import LEVEL_ORDER, language_key, same_place
from .results import Factor, FactorStatus
from .skills import canonical, normalize_text, skill_credit

Scored = tuple[float, list[Factor]] | None

MET_THRESHOLD = 0.7
FIELD_MATCH = 70


@dataclass
class SkillMatch:
    requirement: str
    key: str
    credit: float
    via: str | None
    how: str
    unverified: bool

    @property
    def status(self) -> FactorStatus:
        if self.unverified and self.credit == 0:
            return FactorStatus.UNVERIFIED
        if self.credit >= MET_THRESHOLD:
            return FactorStatus.MET
        return FactorStatus.PARTIAL if self.credit > 0 else FactorStatus.MISSING


def _describe(evidence: SkillEvidence) -> str:
    if evidence.used_professionally:
        years = evidence.months_used / 12
        span = f"{years:.1f} years" if years >= 1 else f"{round(evidence.months_used)} months"
        return f"used for {span} ({', '.join(dict.fromkeys(evidence.experiences))})"
    if evidence.project_count:
        return f"used in {evidence.project_count} project(s)"
    return "listed without professional use"


def match_skill(
    requirement_name: str, minimum_years: float | None, index: dict[str, SkillEvidence], today: date
) -> SkillMatch:
    want = canonical(requirement_name)
    best = SkillMatch(requirement_name, want, 0.0, None, "missing", unverified=False)
    for evidence in index.values():
        base, how = skill_credit(evidence.key, want)
        if base == 0:
            continue
        if evidence.unverified_only:
            best.unverified = True
            continue
        credit = base * skill_strength(evidence, today)
        if minimum_years and evidence.months_used < minimum_years * 12:
            credit *= max(0.5, evidence.months_used / (minimum_years * 12))
        if credit > best.credit:
            best = SkillMatch(requirement_name, want, credit, evidence.name, how, best.unverified)
    return best


def _skill_factor(match: SkillMatch, index: dict[str, SkillEvidence]) -> Factor:
    if match.via is None:
        detail = "claimed but not found in the source document" if match.unverified else "not found in the profile"
    else:
        evidence = index[canonical(match.via)]
        prefix = {"exact": "", "implied": f"via {match.via}: ", "related": f"related skill {match.via}: "}[match.how]
        detail = prefix + _describe(evidence)
    return Factor(
        id=f"skill:{match.key}",
        label=match.requirement,
        status=match.status,
        detail=detail,
        value=round(match.credit, 2),
    )


def score_skills(
    job: JobProfile, kind: RequirementKind, index: dict[str, SkillEvidence], today: date
) -> tuple[Scored, list[SkillMatch]]:
    requirements = [r for r in job.skill_requirements if r.requirement is kind]
    if not requirements:
        return None, []
    matches = [match_skill(r.name, r.minimum_years, index, today) for r in requirements]
    score = sum(m.credit for m in matches) / len(matches)
    return (score, [_skill_factor(m, index) for m in matches]), matches


def score_experience(candidate: CandidateProfile, job: JobProfile, relevant: set[str], today: date) -> Scored:
    minimum = job.experience.minimum_years
    if not minimum:
        return None
    months, positions = relevant_experience_months(candidate, today, relevant)
    if positions == 0 and candidate.total_years_experience is None and not candidate.experiences:
        months_text, score, status = "no experience listed", 0.0, FactorStatus.MISSING
    else:
        years = months / 12
        score = min(years / minimum, 1.0)
        status = FactorStatus.MET if score >= 1 else FactorStatus.PARTIAL if score > 0 else FactorStatus.MISSING
        months_text = f"{years:.1f} years of relevant experience for {minimum:g} required"
    return score, [Factor(id="experience", label="relevant experience", status=status, detail=months_text, value=score)]


def required_seniority(job: JobProfile) -> SeniorityLevel | None:
    if job.seniority or job.experience.required_seniority:
        return job.seniority or job.experience.required_seniority
    if job.contract_type in (ContractType.INTERNSHIP, ContractType.APPRENTICESHIP):
        return SeniorityLevel.INTERN
    return None


def score_seniority(candidate: CandidateProfile, job: JobProfile, today: date) -> Scored:
    wanted = required_seniority(job)
    if wanted is None:
        return None
    level, source = candidate_seniority(candidate, today)
    if level is None:
        factor = Factor(id="seniority", label="seniority", status=FactorStatus.UNKNOWN, detail="cannot be determined")
        return 0.5, [factor]
    distance = abs(SENIORITY_ORDER[level] - SENIORITY_ORDER[wanted])
    score = {0: 1.0, 1: 0.6, 2: 0.25}.get(distance, 0.0)
    status = FactorStatus.MET if distance == 0 else FactorStatus.PARTIAL if score else FactorStatus.MISSING
    detail = f"{level.value} ({source}) for a {wanted.value} role"
    return score, [Factor(id="seniority", label="seniority", status=status, detail=detail, value=score)]


def score_languages(candidate: CandidateProfile, job: JobProfile) -> Scored:
    if not job.language_requirements:
        return None
    spoken = {language_key(lang.language): lang for lang in candidate.languages if lang.verified is not False}
    total = weight_sum = 0.0
    factors = []
    for requirement in job.language_requirements:
        key = language_key(requirement.language)
        weight = 2.0 if requirement.requirement is RequirementKind.REQUIRED else 1.0
        have = spoken.get(key)
        if have is None:
            score, status, detail = 0.0, FactorStatus.MISSING, "not listed"
        elif requirement.level is None:
            score, status, detail = 1.0, FactorStatus.MET, f"listed{f' ({have.level.value})' if have.level else ''}"
        elif have.level is None:
            score, status, detail = 0.7, FactorStatus.UNKNOWN, f"level not stated ({requirement.level.value} wanted)"
        else:
            gap = LEVEL_ORDER[requirement.level] - LEVEL_ORDER[have.level]
            score = 1.0 if gap <= 0 else 0.6 if gap == 1 else 0.3
            status = FactorStatus.MET if gap <= 0 else FactorStatus.PARTIAL
            detail = f"{have.level.value} for {requirement.level.value} wanted"
        total += weight * score
        weight_sum += weight
        factors.append(
            Factor(id=f"language:{key}", label=requirement.language, status=status, detail=detail, value=score)
        )
    return total / weight_sum, factors


DEGREE_LEVELS = [
    (8, r"\b(phd|ph\.d|doctorat|doctorate)\b"),
    (5, r"\b(master|mastere|msc|m\.sc|mba|ingenieur|engineer|engineering)\b"),
    (3, r"\b(licence|bachelor|bsc|b\.sc|ba)\b"),
    (2, r"\b(bts|dut|bac\s*\+\s*2|associate)\b"),
]


def degree_level(text: str | None) -> int | None:
    if not text:
        return None
    normalized = normalize_text(text)
    levels = [level for level, pattern in DEGREE_LEVELS if re.search(pattern, normalized)]
    # "Diplôme d'ingénieur ou Master" -> the lowest accepted level.
    return min(levels) if levels else None


def score_education(candidate: CandidateProfile, job: JobProfile, relevant_months: float, today: date) -> Scored:
    requirements = [r for r in job.education_requirements if r.requirement is RequirementKind.REQUIRED]
    requirements = requirements or job.education_requirements
    if not requirements:
        return None
    requirement = requirements[0]
    needed = degree_level(requirement.degree)
    best_level, best_field = 0, 0.0
    for education in candidate.education:
        level = degree_level(education.degree) or 0
        in_progress = education.dates.end_date is not None and education.dates.end_date > today
        best_level = max(best_level, level - 1 if in_progress else level)
        if requirement.field_of_study and education.field_of_study:
            best_field = max(
                best_field,
                fuzz.token_set_ratio(
                    normalize_text(requirement.field_of_study), normalize_text(education.field_of_study)
                ),
            )

    if not candidate.education:
        score, status, detail = 0.4, FactorStatus.UNKNOWN, "no education listed"
    elif needed is None or best_level >= needed:
        field_ok = not requirement.field_of_study or best_field >= FIELD_MATCH
        score, status = (1.0, FactorStatus.MET) if field_ok else (0.8, FactorStatus.PARTIAL)
        detail = "degree level met" + ("" if field_ok else ", different field of study")
    elif relevant_months >= 36 and best_level >= needed - 2:
        score, status, detail = (
            0.7,
            FactorStatus.PARTIAL,
            "lower degree, compensated by 3+ years of relevant experience",
        )
    else:
        score, status, detail = 0.3, FactorStatus.MISSING, "required degree level not met"
    wanted = requirement.degree or requirement.field_of_study or "degree"
    return score, [Factor(id="education", label=f"education: {wanted}", status=status, detail=detail, value=score)]


def score_location(candidate: CandidateProfile, job: JobProfile) -> Scored:
    if job.work_mode is None and job.location is None:
        return None
    home = candidate.identity.location
    preferred_modes = candidate.work_preferences.preferred_work_modes
    if job.work_mode is WorkMode.REMOTE:
        if job.location and job.location.country and home and home.country:
            same = same_place(home.country, job.location.country)
            score, detail = (1.0, "remote, same country") if same else (0.5, "remote, but based in another country")
        else:
            score, detail = 1.0, "remote role"
    elif job.location is None or home is None or not (home.city or home.country):
        factor = Factor(id="location", label="location", status=FactorStatus.UNKNOWN, detail="location not stated")
        return 0.5, [factor]
    elif same_place(home.city, job.location.city):
        score, detail = 1.0, f"based in {home.city}"
    elif same_place(home.country, job.location.country):
        score, detail = (
            0.7,
            f"based in {home.city or home.country}, role in {job.location.city or job.location.country}",
        )
    elif candidate.work_preferences.willing_to_relocate:
        score, detail = 0.6, "based abroad, willing to relocate"
    else:
        score, detail = 0.2, "based abroad"
    if preferred_modes and job.work_mode and job.work_mode not in preferred_modes:
        score *= 0.8
        detail += f"; prefers {', '.join(m.value for m in preferred_modes)}"
    status = FactorStatus.MET if score >= 0.9 else FactorStatus.PARTIAL if score > 0.3 else FactorStatus.MISSING
    return score, [Factor(id="location", label="location / work mode", status=status, detail=detail, value=score)]
