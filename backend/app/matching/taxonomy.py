"""ESCO skills taxonomy (European Skills, Competences, Qualifications and Occupations).

When loaded, it extends skill normalization: any preferred or alternative label, in English or French, maps to
one canonical skill; and a narrower skill implies its broader ones (e.g. a specific database implies "database
management systems"). Without a taxonomy, the curated v0 graph in `skills.py` is used alone.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", stripped).strip(" .,;:")


@dataclass
class TaxonomySkill:
    uri: str
    labels: dict[str, str]
    """Preferred label per language ("en", "fr")."""
    alt_labels: list[str] = field(default_factory=list)
    skill_type: str | None = None


@dataclass
class Taxonomy:
    version: str
    skills: dict[str, TaxonomySkill]
    broader: dict[str, set[str]]
    _label_index: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for uri, skill in self.skills.items():
            for label in [*skill.labels.values(), *skill.alt_labels]:
                # The first concept to claim a label keeps it; ambiguous alt labels stay with one concept.
                self._label_index.setdefault(_normalize(label), uri)

    def uri_for(self, key: str) -> str | None:
        return self._label_index.get(key)

    def canonical_key(self, uri: str) -> str:
        skill = self.skills[uri]
        return _normalize(skill.labels.get("en") or next(iter(skill.labels.values())))

    def broader_keys(self, key: str) -> set[str]:
        """Canonical keys of every broader concept of `key` (transitively)."""
        uri = self.uri_for(key)
        if uri is None:
            return set()
        seen: set[str] = set()
        stack = list(self.broader.get(uri, ()))
        while stack:
            current = stack.pop()
            if current not in seen and current in self.skills:
                seen.add(current)
                stack.extend(self.broader.get(current, ()))
        return {self.canonical_key(u) for u in seen}


_active: Taxonomy | None = None


def active_taxonomy() -> Taxonomy | None:
    return _active


def set_taxonomy(taxonomy: Taxonomy | None) -> None:
    """Activate a taxonomy for normalization (None restores the curated graph only)."""
    global _active
    _active = taxonomy
    from . import skills  # local import: skills depends on this module

    skills.implied_by.cache_clear()
    skills.mention_pattern.cache_clear()


# --- ESCO CSV import -------------------------------------------------------------------------------------------------


def _split_labels(value: str | None) -> list[str]:
    return [label.strip() for label in (value or "").splitlines() if label.strip()]


def read_esco_csv(skill_files: dict[str, Path], broader_file: Path | None, version: str) -> Taxonomy:
    """Read the official ESCO CSV export: `skills_<lang>.csv` per language, and `broaderRelationsSkillPillar.csv`.

    Only the columns conceptUri, preferredLabel, altLabels, skillType (skills) and conceptUri, broaderUri
    (relations) are used, so minor format differences between ESCO versions are tolerated.
    """
    skills: dict[str, TaxonomySkill] = {}
    for language, path in skill_files.items():
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                uri, label = row.get("conceptUri"), row.get("preferredLabel")
                if not uri or not label:
                    continue
                skill = skills.setdefault(
                    uri, TaxonomySkill(uri=uri, labels={}, skill_type=row.get("skillType") or None)
                )
                skill.labels[language] = label.strip()
                skill.alt_labels.extend(_split_labels(row.get("altLabels")))

    broader: dict[str, set[str]] = {}
    if broader_file is not None:
        with broader_file.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                narrower, wider = row.get("conceptUri"), row.get("broaderUri")
                if narrower and wider:
                    broader.setdefault(narrower, set()).add(wider)
    return Taxonomy(version=version, skills=skills, broader=broader)


def taxonomy_rows(taxonomy: Taxonomy) -> Iterable[dict[str, object]]:
    for skill in taxonomy.skills.values():
        yield {
            "uri": skill.uri,
            "label_en": skill.labels.get("en"),
            "label_fr": skill.labels.get("fr"),
            "alt_labels": sorted(set(skill.alt_labels)),
            "skill_type": skill.skill_type,
        }
