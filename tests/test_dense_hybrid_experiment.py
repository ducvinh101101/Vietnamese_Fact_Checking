import pytest

from scripts.evaluate_dense_hybrid import metrics, rrf


def test_rrf_rewards_agreement_and_has_deterministic_ties():
    assert rrf([0, 1], [2, 1]) == [1, 0, 2]
    assert rrf([], []) == []
    assert rrf([4], []) == [4]


def test_metrics_count_misses_and_cutoffs():
    result = metrics([1, 3, 5, 0], [1, 2, 3, 4])
    assert result['recall_at_3'] == 0.5
    assert result['recall_at_5'] == 0.75
    assert result['mrr_at_5'] == pytest.approx((1 + 1/3 + 1/5) / 4)
    assert result['latency_ms']['p50'] == 2.5
