"""Ranking metrics, and a regression guard on the matching eval (runs offline, no LLM)."""

import pytest

from eval.ranking_metrics import ndcg_at_k, spearman
from eval.run_matching import run


def test_ndcg() -> None:
    assert ndcg_at_k([3, 1, 0], 3) == 1
    assert ndcg_at_k([0, 1, 3], 3) < 0.6
    assert ndcg_at_k([0, 0], 2) == 1  # nothing relevant to rank


def test_spearman_handles_ties() -> None:
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1)
    assert spearman([90, 50, 40, 10], [3, 1, 1, 0]) == pytest.approx(0.9487, abs=1e-3)


def test_matching_eval_does_not_regress() -> None:
    summary = run()["summary"]

    assert summary["top1_accuracy"] == 1
    assert summary["mean_ndcg@3"] >= 0.9
    assert summary["mean_spearman"] >= 0.7
