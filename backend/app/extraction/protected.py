"""Remove protected personal characteristics that the model copied into a candidate profile anyway.

The extraction prompt forbids them, but models (local ones especially) sometimes keep a line such as
"Né le 03/07/1992 — Célibataire". This deterministic pass is the safety net: any text segment stating a marital
status, birth date or age, nationality, religion, gender or health condition is dropped, and the removal is counted
in the extraction metadata. Segments are the parts of a string between separators (— | ; , . and line breaks), so
the rest of a sentence survives.
"""

from __future__ import annotations

import re
from typing import Any

PROTECTED = re.compile(
    "|".join(
        [
            # marital status and family
            r"\b(célibataire|celibataire|mariée?|divorcée?|veuf|veuve|pacsée?|fiancée?)\b",
            r"\b(marital|family)\s+status\b",
            r"\bsituation\s+(familiale|matrimoniale)\b",
            r"\b(married|divorced|widowed)\b",
            r"\b\d+\s+(enfants?|children|kids)\b",
            r"\b(mother|father|mère|père)\s+(of|de)\s+\w+",
            # birth date and age
            r"\bnée?\s+(le|en)\b",
            r"\b(date|lieu)\s+de\s+naissance\b",
            r"\b(date|place)\s+of\s+birth\b",
            r"\bborn\s+(on|in)\b",
            r"\bd\.?o\.?b\.?\s*:",
            r"\b(âgée?\s+de\s+\d{2}\s+ans|\d{2}\s+years\s+old)\b",  # not "10 ans d'expérience"
            r"\b(âge|age)\s*:\s*\d{2}\b",
            # nationality, religion, gender, health
            r"\bnationalit(é|e|y)\b",
            # religion words only: adjectives such as "Christian" are also first names and brands
            r"\b(religion|confession\s+religieuse|musulmane?)\b",
            r"\b(sexe|gender|genre)\s*:",
            r"\b(handicap|disability|disabled|rqth|wheelchair|pregnan(t|cy)|enceinte)\b",
        ]
    ),
    re.IGNORECASE,
)
SEPARATORS = re.compile(r"\s*(?:\u2014|\u2013|\||;|\n|(?<!\d)[.,](?!\d))\s*")  # em/en dash, |, ;, newline, . ,


def _clean(text: str, removed: list[str]) -> str | None:
    if not PROTECTED.search(text):
        return text
    kept = []
    for segment in SEPARATORS.split(text):
        if not segment:
            continue
        if PROTECTED.search(segment):
            removed.append(segment)
        else:
            kept.append(segment)
    return ", ".join(kept) or None


def _walk(value: Any, removed: list[str]) -> Any:
    if isinstance(value, str):
        return _clean(value, removed)
    if isinstance(value, list):
        cleaned = [_walk(item, removed) for item in value]
        return [item for item in cleaned if item is not None]
    if isinstance(value, dict):
        return {key: _walk(item, removed) for key, item in value.items()}
    return value


def scrub_protected(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The profile without protected characteristics, and the removed segments.

    Identity (name, contact details) is skipped: names such as "Christian" or "Marié" must not be mangled.
    Evidence quotes are cleaned like any other text; a shortened quote is still checked against the source.
    """
    removed: list[str] = []
    cleaned = {key: value if key == "identity" else _walk(value, removed) for key, value in data.items()}
    return cleaned, removed
