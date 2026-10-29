"""Text embedding providers.

`HashingEmbedder` is the default: a deterministic feature-hashing model over words and character n-grams. It needs
no model download, API key or GPU, works the same way in every language, and matches surface variants
("Postgres" / "PostgreSQL", "ingénieur" / "engineer" share n-grams). It does not understand synonyms with
different spellings; a neural multilingual model can replace it behind the same `Embedder` interface.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.matching.skills import normalize_text

EMBEDDING_DIM = 384
WORD_RE = re.compile(r"[\w+#.]+")


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _bucket(feature: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    value = int.from_bytes(digest, "little")
    return value % dim, 1.0 if (value >> 63) & 1 else -1.0


class HashingEmbedder:
    """Signed feature hashing of words (weight 1) and character 3-5-grams (weight 0.5), L2-normalized."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim
        self.name = f"hashing-ngram-v1-{dim}"

    def _features(self, text: str) -> dict[str, float]:
        features: dict[str, float] = {}
        for word in WORD_RE.findall(normalize_text(text)):
            features[f"w:{word}"] = features.get(f"w:{word}", 0.0) + 1.0
            padded = f"<{word}>"
            for n in (3, 4, 5):
                for i in range(len(padded) - n + 1):
                    gram = f"c:{padded[i : i + n]}"
                    features[gram] = features.get(gram, 0.0) + 0.5
        return features

    def embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for feature, count in self._features(text).items():
            index, sign = _bucket(feature, self.dim)
            vector[index] += sign * (1.0 + math.log(count)) if count >= 1 else sign * count
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@lru_cache
def get_embedder() -> Embedder:
    return HashingEmbedder()
