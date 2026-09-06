import pytest

from src.retrieval_aware_policy import decide_rank_aware


def test_zero_rank_bias_matches_global_maximum_probability():
    decision = decide_rank_aware([[0.51, 0.20, 0.29], [0.10, 0.80, 0.10]], rank_bias=0)

    assert decision.label == "REFUTED"
    assert decision.evidence_index == 1
    assert decision.confidence == pytest.approx(0.80)


def test_rank_bias_can_prefer_a_similarly_confident_higher_ranked_candidate():
    decision = decide_rank_aware([[0.76, 0.10, 0.14], [0.10, 0.82, 0.08]], rank_bias=0.5)

    assert decision.label == "SUPPORTED"
    assert decision.evidence_index == 0
    assert decision.confidence == pytest.approx(0.76)


def test_decisive_threshold_abstains_using_best_rank_aware_nei_candidate():
    decision = decide_rank_aware([[0.45, 0.10, 0.30], [0.10, 0.40, 0.55]], rank_bias=0, decisive_min_confidence=0.5)

    assert decision.label == "NOT_ENOUGH_INFO"
    assert decision.evidence_index == 1
    assert decision.confidence == pytest.approx(0.55)
