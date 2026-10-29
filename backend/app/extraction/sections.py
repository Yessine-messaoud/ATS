"""Detect common CV section headings (FR/EN) to give the extractor a document map."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MAX_HEADING_CHARS = 40

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "profile", "about me", "objective", "profil", "resume", "a propos", "objectif"),
    "experience": (
        "experience",
        "experiences",
        "work experience",
        "professional experience",
        "employment",
        "work history",
        "experience professionnelle",
        "experiences professionnelles",
        "parcours professionnel",
        "stages",
    ),
    "education": ("education", "academic background", "formation", "formations", "parcours academique", "etudes"),
    "skills": (
        "skills",
        "technical skills",
        "competences",
        "competences techniques",
        "savoir-faire",
        "technologies",
        "outils",
    ),
    "projects": ("projects", "personal projects", "academic projects", "projets", "projets academiques"),
    "certifications": ("certifications", "certificates", "licenses", "certificats"),
    "languages": ("languages", "langues"),
    "interests": ("interests", "hobbies", "centres d'interet", "loisirs", "activites"),
}


@dataclass(frozen=True)
class Section:
    name: str
    heading: str
    line_number: int


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[\s:•\-_|#*]+", " ", stripped.lower()).strip()


_KEYWORD_TO_SECTION = {_normalize(k): name for name, keywords in SECTION_KEYWORDS.items() for k in keywords}


def detect_sections(text: str) -> list[Section]:
    sections = []
    for number, line in enumerate(text.splitlines(), start=1):
        candidate = line.strip()
        if not candidate or len(candidate) > MAX_HEADING_CHARS:
            continue
        name = _KEYWORD_TO_SECTION.get(_normalize(candidate))
        if name is not None:
            sections.append(Section(name=name, heading=candidate, line_number=number))
    return sections
