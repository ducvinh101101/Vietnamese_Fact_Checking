import json
import pytest
from src.learned_evidence_policy import LearnedEvidencePolicy, aggregation_features
from src.decision_policy import LABELS


def test_unrelated_label_winner_is_not_used_as_the_citation(tmp_path):
    # A constant REFUTED model lets this test isolate citation label/rank behavior.
    path = tmp_path / "model.json"
    path.write_text(json.dumps(dict(feature_version=1, labels=list(LABELS),
        mean=[0]*21, scale=[1]*21, coef=[[0]*21 for _ in range(3)], intercept=[0, 3, 0])))
    decision = LearnedEvidencePolicy(path).decide([[0.8, 0.1, 0.1], [0.1, 0.85, 0.05], [0.1, 0.2, 0.7]], [10, 9, 8])
    assert decision.label == "REFUTED"
    assert decision.evidence_index == 1


@pytest.mark.parametrize("p", [float("nan"), float("inf"), -0.1])
def test_invalid_probabilities_fail_closed(p):
    with pytest.raises(ValueError):
        aggregation_features([[p, 0.2, 0.8]]*3, [3, 2, 1])


@pytest.mark.parametrize("threshold,expected_reason", [(0.99, "low_confidence"), (0, "no_agreeing_passage")])
def test_aggregate_rejection_when_unsupported_or_below_threshold(tmp_path, threshold, expected_reason):
    path = tmp_path / "model.json"
    path.write_text(json.dumps(dict(feature_version=1, labels=list(LABELS),
        mean=[0]*21, scale=[1]*21, coef=[[0]*21 for _ in range(3)], intercept=[0, 3, 0],
        decisive_min_confidence=threshold)))
    decision = LearnedEvidencePolicy(path).decide([[0.8, 0.1, 0.1]]*3, [3, 2, 1])
    assert decision.label == "NOT_ENOUGH_INFO"
    assert decision.evidence_index == -1
    assert decision.reason == expected_reason
