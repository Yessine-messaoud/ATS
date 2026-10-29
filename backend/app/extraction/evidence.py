"""Deterministic check that extracted items are grounded in the source text."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.models import Evidenced

MATCH_THRESHOLD = 90
# When an item carries no evidence quote, the field that must itself appear in the source.
ANCHOR_FIELDS = ("raw_name", "name", "company", "institution", "language")


@dataclass
class EvidenceStats:
    items: int = 0
    verified: int = 0
    unverified: int = 0
    missing_evidence: int = 0
    unverified_paths: list[str] = field(default_factory=list)

    @property
    def unverified_rate(self) -> float:
        return self.unverified / self.items if self.items else 0.0


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def is_grounded(quote: str, normalized_source: str) -> bool:
    needle = normalize(quote)
    if not needle:
        return False
    if needle in normalized_source:
        return True
    return fuzz.partial_ratio(needle, normalized_source) >= MATCH_THRESHOLD


def _anchor(item: Evidenced) -> str | None:
    for name in ANCHOR_FIELDS:
        value = getattr(item, name, None)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _walk(node: object, path: str, source: str, stats: EvidenceStats) -> None:
    if isinstance(node, list):
        for index, child in enumerate(node):
            _walk(child, f"{path}[{index}]", source, stats)
        return
    if not isinstance(node, BaseModel):
        return
    if isinstance(node, Evidenced):
        stats.items += 1
        quote = node.evidence or _anchor(node)
        if node.evidence is None:
            stats.missing_evidence += 1
        node.verified = quote is not None and is_grounded(quote, source)
        if node.verified:
            stats.verified += 1
        else:
            stats.unverified += 1
            stats.unverified_paths.append(path)
    for name in type(node).model_fields:
        _walk(getattr(node, name), f"{path}.{name}" if path else name, source, stats)


def verify_evidence(profile: BaseModel, source_text: str) -> EvidenceStats:
    """Set `verified` on every Evidenced item in `profile` (in place) and return the counts."""
    stats = EvidenceStats()
    _walk(profile, "", normalize(source_text), stats)
    return stats
