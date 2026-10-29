"""Knock-out criteria: binary checks on mandatory requirements.

A failed knock-out never hides a candidate; the ranking lists them separately with the reason. Missing information
gives UNKNOWN (to be checked by the recruiter), not FAIL.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from app.models import CandidateProfile, JobProfile, LanguageLevel, RequirementKind, WorkMode

from .results import Knockout, KnockoutStatus
from .skills import normalize_text

LEVEL_ORDER = {
    LanguageLevel.A1: 1,
    LanguageLevel.A2: 2,
    LanguageLevel.B1: 3,
    LanguageLevel.B2: 4,
    LanguageLevel.C1: 5,
    LanguageLevel.C2: 6,
    LanguageLevel.NATIVE: 7,
}
CERTIFICATION_MATCH = 85
LANGUAGE_NAMES = {
    "anglais": "english",
    "francais": "french",
    "arabe": "arabic",
    "allemand": "german",
    "espagnol": "spanish",
    "italien": "italian",
}


def language_key(name: str) -> str:
    key = normalize_text(name)
    return LANGUAGE_NAMES.get(key, key)


def same_place(a: str | None, b: str | None) -> bool | None:
    if not a or not b:
        return None
    return normalize_text(a) == normalize_text(b)


def language_knockouts(candidate: CandidateProfile, job: JobProfile) -> list[Knockout]:
    spoken = {language_key(lang.language): lang for lang in candidate.languages if lang.verified is not False}
    results = []
    for requirement in job.language_requirements:
        if requirement.requirement is not RequirementKind.REQUIRED:
            continue
        key = language_key(requirement.language)
        factor_id = f"language:{key}"
        needed = f" {requirement.level.value}" if requirement.level else ""
        criterion = f"{requirement.language}{needed} required"
        have = spoken.get(key)
        if have is None:
            results.append(
                Knockout(
                    criterion=criterion, status=KnockoutStatus.FAIL, detail="language not listed", factor_id=factor_id
                )
            )
        elif requirement.level is None:
            results.append(
                Knockout(criterion=criterion, status=KnockoutStatus.PASS, detail="language listed", factor_id=factor_id)
            )
        elif have.level is None:
            results.append(
                Knockout(
                    criterion=criterion,
                    status=KnockoutStatus.UNKNOWN,
                    detail="level not stated in the CV",
                    factor_id=factor_id,
                )
            )
        elif LEVEL_ORDER[have.level] >= LEVEL_ORDER[requirement.level]:
            results.append(
                Knockout(
                    criterion=criterion,
                    status=KnockoutStatus.PASS,
                    detail=f"level {have.level.value}",
                    factor_id=factor_id,
                )
            )
        else:
            results.append(
                Knockout(
                    criterion=criterion,
                    status=KnockoutStatus.FAIL,
                    detail=f"level {have.level.value}",
                    factor_id=factor_id,
                )
            )
    return results


def certification_knockouts(candidate: CandidateProfile, job: JobProfile) -> list[Knockout]:
    results = []
    for requirement in job.certification_requirements:
        if requirement.requirement is not RequirementKind.REQUIRED:
            continue
        factor_id = f"certification:{normalize_text(requirement.name)}"
        matches = [
            cert
            for cert in candidate.certifications
            if fuzz.token_set_ratio(normalize_text(cert.name), normalize_text(requirement.name)) >= CERTIFICATION_MATCH
        ]
        if any(cert.verified is not False for cert in matches):
            status, detail = KnockoutStatus.PASS, f"holds {matches[0].name}"
        elif matches:
            status, detail = KnockoutStatus.UNKNOWN, "claimed but not found in the document"
        else:
            status, detail = KnockoutStatus.FAIL, "not listed"
        results.append(
            Knockout(criterion=f"{requirement.name} required", status=status, detail=detail, factor_id=factor_id)
        )
    return results


def location_knockouts(candidate: CandidateProfile, job: JobProfile) -> list[Knockout]:
    if job.work_mode is WorkMode.REMOTE or job.location is None or not job.location.country:
        return []
    home = candidate.identity.location
    same_country = same_place(home.country if home else None, job.location.country)
    criterion = f"based in or relocating to {job.location.country}"
    if same_country is None:
        status, detail = KnockoutStatus.UNKNOWN, "candidate location not stated"
    elif same_country:
        status, detail = KnockoutStatus.PASS, f"based in {home.country if home else ''}"
    elif candidate.work_preferences.willing_to_relocate is True:
        status, detail = KnockoutStatus.PASS, "willing to relocate"
    elif candidate.work_preferences.willing_to_relocate is False:
        status, detail = KnockoutStatus.FAIL, "not willing to relocate"
    else:
        status, detail = KnockoutStatus.UNKNOWN, "based abroad; relocation not stated"
    return [Knockout(criterion=criterion, status=status, detail=detail, factor_id="location:country")]


def work_authorization_knockouts(candidate: CandidateProfile, job: JobProfile) -> list[Knockout]:
    if not job.work_authorization:
        return []
    stated = candidate.work_preferences.work_authorization
    detail = f"candidate states: {stated}" if stated else "not stated in the CV"
    return [
        Knockout(
            criterion=f"work authorization: {job.work_authorization}",
            status=KnockoutStatus.UNKNOWN,
            detail=f"{detail}; must be confirmed by the recruiter",
            factor_id="work_authorization",
        )
    ]


def evaluate_knockouts(candidate: CandidateProfile, job: JobProfile) -> list[Knockout]:
    return [
        *language_knockouts(candidate, job),
        *certification_knockouts(candidate, job),
        *location_knockouts(candidate, job),
        *work_authorization_knockouts(candidate, job),
    ]
