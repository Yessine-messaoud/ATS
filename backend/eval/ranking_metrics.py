"""Ranking metrics against graded human relevance labels."""

from __future__ import annotations

import math
from collections.abc import Sequence


def dcg(gains: Sequence[float]) -> float:
    return sum((2**gain - 1) / math.log2(rank + 2) for rank, gain in enumerate(gains))


def ndcg_at_k(ranked_labels: Sequence[float], k: int) -> float:
    """NDCG@k of a ranking, given the human label of each ranked item in ranked order."""
    ideal = dcg(sorted(ranked_labels, reverse=True)[:k])
    return dcg(ranked_labels[:k]) / ideal if ideal else 1.0


def _ranks(values: Sequence[float]) -> list[float]:
    """Average ranks (1-based), ties sharing the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for position in range(i, j + 1):
            ranks[order[position]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    """Spearman rank correlation with tie handling (Pearson correlation of the ranks)."""
    ra, rb = _ranks(a), _ranks(b)
    mean_a, mean_b = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(ra, rb, strict=True))
    var_a = math.sqrt(sum((x - mean_a) ** 2 for x in ra))
    var_b = math.sqrt(sum((y - mean_b) ** 2 for y in rb))
    return cov / (var_a * var_b) if var_a and var_b else 0.0
