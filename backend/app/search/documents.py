"""The text that represents a candidate or a job for retrieval.

Only professional content is used: never names, emails, phone numbers, links or addresses, so that retrieval
(like scoring) cannot be influenced by identity.
"""

from __future__ import annotations

from app.matching.skills import canonical, implied_by
from app.models import CandidateProfile, JobProfile


def _skill_terms(names: list[str]) -> list[str]:
    """Canonical names plus the skills they imply, so "PostgreSQL" is also found by a search for "SQL"."""
    terms: list[str] = []
    for name in names:
        key = canonical(name)
        terms.append(key)
        terms.extend(sorted(implied_by(key)))
    return list(dict.fromkeys(terms))


def candidate_text(profile: CandidateProfile) -> str:
    skills = [s.name for s in profile.skills if s.verified is not False]
    skills += [s.name for e in profile.experiences for s in e.skills_used]
    skills += [t.name for p in profile.projects for t in p.technologies]
    parts = [
        profile.professional_title or "",
        " ".join(_skill_terms(skills)),
        " ".join(profile.domains),
        *(f"{e.job_title} {' '.join(e.domains)} {' '.join(e.responsibilities)}" for e in profile.experiences),
        *(f"{ed.degree or ''} {ed.field_of_study or ''}" for ed in profile.education),
        " ".join(c.name for c in profile.certifications),
        " ".join(p.name for p in profile.projects),
    ]
    return "\n".join(part.strip() for part in parts if part.strip())


def job_text(profile: JobProfile) -> str:
    parts = [
        profile.title,
        " ".join(_skill_terms([s.name for s in profile.skill_requirements])),
        " ".join(profile.experience.relevant_domains + profile.technical_domains + profile.business_domains),
        " ".join(profile.responsibilities),
        " ".join(f"{e.degree or ''} {e.field_of_study or ''}" for e in profile.education_requirements),
    ]
    return "\n".join(part.strip() for part in parts if part.strip())


def job_keywords(profile: JobProfile) -> list[str]:
    """Terms for the lexical (full-text) half of hybrid retrieval: the job's skills and what they imply."""
    return _skill_terms([s.name for s in profile.skill_requirements])
