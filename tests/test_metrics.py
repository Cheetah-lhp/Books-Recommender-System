import pytest

from books_recommender.evaluation.metrics import (
    average_precision_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_ranking_metrics():
    recommended = [10, 20, 30, 40]
    relevant = {20, 40}
    assert precision_at_k(recommended, relevant, 4) == 0.5
    assert recall_at_k(recommended, relevant, 2) == 0.5
    assert reciprocal_rank(recommended, relevant, 4) == 0.5
    assert average_precision_at_k(recommended, relevant, 4) == pytest.approx(0.5)
    assert 0.0 < ndcg_at_k(recommended, relevant, 4) < 1.0


def test_empty_truth_is_safe():
    assert recall_at_k([1], set(), 10) == 0.0
    assert ndcg_at_k([1], set(), 10) == 0.0
