"""Derive matching features from a candidate profile: skill evidence and experience timelines.

Only professional content is read. Identity fields (name, email, phone, links) are never used.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date

from app.models import CandidateProfile, Experience, SeniorityLevel

from .skills import KNOWN_SKILLS, canonical, implied_by, mention_pattern, normalize_text

INTERNSHIP_MARKERS = ("intern", "internship", "stage", "stagiaire", "trainee", "apprenti", "alternance")
INTERNSHIP_WEIGHT = 0.5


@dataclass
class SkillEvidence:
    key: str
    name: str
    listed: bool = False
    project_count: int = 0
    months_used: float = 0.0
    last_used: date | None = None
    experiences: list[str] = field(default_factory=list)
    unverified_only: bool = False

    @property
    def used_professionally(self) -> bool:
        return self.months_used > 0


def months_between(start: date, end: date) -> float:
    return max((end - start).days / 30.44, 0.0)


def experience_interval(experience: Experience, today: date) -> tuple[date, date] | None:
    start, end = experience.dates.start_date, experience.dates.end_date
    if start is None:
        return None
    if end is None:
        end = today if experience.current is not False else start
    return start, end


def is_internship(experience: Experience) -> bool:
    title = normalize_text(experience.job_title)
    return any(marker in title for marker in INTERNSHIP_MARKERS)


def experience_text(experience: Experience) -> str:
    parts = [experience.job_title, *experience.responsibilities, *experience.achievements]
    return normalize_text(" \n ".join(parts))


def skill_index(
    profile: CandidateProfile, today: date, sought: AbstractSet[str] = frozenset()
) -> dict[str, SkillEvidence]:
    """Merge listed skills, per-experience skills and project technologies into one evidence record per skill.

    `sought` (the job's skill keys) are also searched for in experience descriptions, so a skill the candidate
    used but did not list is still found.
    """
    index: dict[str, SkillEvidence] = {}

    def entry(name: str) -> SkillEvidence:
        key = canonical(name)
        if key not in index:
            index[key] = SkillEvidence(key=key, name=name)
        return index[key]

    for skill in profile.skills:
        evidence = entry(skill.name)
        if skill.verified is False:
            # Unverified claims (evidence not found in the document) earn no credit until a human confirms them.
            evidence.unverified_only = not evidence.listed
            continue
        evidence.listed = True
        evidence.unverified_only = False

    for project in profile.projects:
        for technology in project.technologies:
            if technology.verified is not False:
                entry(technology.name).project_count += 1

    for experience in profile.experiences:
        if experience.verified is False:
            continue
        interval = experience_interval(experience, today)
        text = experience_text(experience)
        used = {canonical(s.name) for s in experience.skills_used if s.verified is not False}
        used |= {key for key in index.keys() | sought if mention_pattern(key).search(text)}
        for key in used:
            evidence = index.get(key) or entry(key)
            evidence.unverified_only = False
            evidence.experiences.append(experience.company)
            if interval is not None:
                weight = INTERNSHIP_WEIGHT if is_internship(experience) else 1.0
                evidence.months_used += months_between(*interval) * weight
                evidence.last_used = max(filter(None, [evidence.last_used, interval[1]]))
    return index


def skill_strength(evidence: SkillEvidence, today: date) -> float:
    """How well a skill is demonstrated, in [0, 1]: professional use > projects > a bare listing, decaying with age."""
    if evidence.unverified_only:
        return 0.0
    if evidence.used_professionally:
        strength = 0.7 + 0.3 * min(evidence.months_used / 36, 1.0)
    elif evidence.project_count:
        strength = 0.65
    elif evidence.listed:
        strength = 0.55
    else:
        return 0.0
    if evidence.last_used is not None:
        years_ago = (today - evidence.last_used).days / 365.25
        if years_ago > 6:
            strength *= 0.7
        elif years_ago > 3:
            strength *= 0.85
    return strength


def relevant_experience_months(profile: CandidateProfile, today: date, relevant: set[str] | None) -> tuple[float, int]:
    """Months of experience (overlaps merged) and number of positions counted.

    With `relevant` given, only positions using one of those skills or domains count; None counts every position.
    Internships count half.
    """
    intervals: list[tuple[date, date, float]] = []
    for experience in profile.experiences:
        interval = experience_interval(experience, today)
        if interval is None or experience.verified is False:
            continue
        if relevant is not None:
            text = experience_text(experience) + " " + normalize_text(" ".join(experience.domains))
            uses = {canonical(s.name) for s in experience.skills_used}
            uses |= {key for key in relevant | KNOWN_SKILLS if mention_pattern(key).search(text)}
            # FastAPI work is Python work: expand through the implication graph.
            uses |= {implied for key in list(uses) for implied in implied_by(key)}
            if not uses & relevant:
                continue
        intervals.append((*interval, INTERNSHIP_WEIGHT if is_internship(experience) else 1.0))

    total = 0.0
    cursor: date | None = None
    for start, end, weight in sorted(intervals):
        effective_start = max(start, cursor) if cursor else start
        if end > effective_start:
            total += months_between(effective_start, end) * weight
        cursor = max(cursor, end) if cursor else end
    return total, len(intervals)


def total_experience_months(profile: CandidateProfile, today: date) -> float | None:
    months, positions = relevant_experience_months(profile, today, relevant=None)
    if positions:
        return months
    if profile.total_years_experience is not None:
        return profile.total_years_experience * 12
    return None


SENIORITY_ORDER = {
    SeniorityLevel.INTERN: 0,
    SeniorityLevel.JUNIOR: 1,
    SeniorityLevel.MID: 2,
    SeniorityLevel.SENIOR: 3,
    SeniorityLevel.LEAD: 4,
    SeniorityLevel.MANAGER: 4,
    SeniorityLevel.DIRECTOR: 5,
    SeniorityLevel.EXECUTIVE: 6,
}


def is_student(profile: CandidateProfile, today: date) -> bool:
    return any(e.dates.end_date is not None and e.dates.end_date > today for e in profile.education)


def candidate_seniority(profile: CandidateProfile, today: date) -> tuple[SeniorityLevel | None, str]:
    """Stated seniority, or one derived from total experience."""
    if profile.seniority is not None:
        return profile.seniority, "stated"
    months = total_experience_months(profile, today)
    if months is None:
        return None, "unknown"
    if is_student(profile, today) or months < 6:
        return SeniorityLevel.INTERN, "derived"
    years = months / 12
    level = (
        SeniorityLevel.JUNIOR
        if years < 2
        else SeniorityLevel.MID
        if years < 5
        else SeniorityLevel.SENIOR
        if years < 9
        else SeniorityLevel.LEAD
    )
    return level, "derived"
