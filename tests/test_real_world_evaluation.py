import pandas as pd
import pytest
from scripts.evaluate_real_world_predictions import evaluate


def gold():
    return pd.DataFrame([dict(claim_id=str(i), claim=f"claim {i}", gold_label=label,
                             topic_group=f"topic {i}", source_url=f"https://example.org/{i}",
                             observed_at="2026-09-07", reviewer_1="a", reviewer_2="b", review_status="approved")
                         for i, label in enumerate(["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"])])


def test_missing_predictions_are_not_hidden_by_coverage():
    predictions = pd.DataFrame([dict(claim_id="0", predicted_label="SUPPORTED", citation_faithful="true")])
    result = evaluate(gold(), predictions)
    assert result["accuracy_all_claims"] == pytest.approx(1/3)
    assert result["accuracy_answered_only"] == 1
    assert result["coverage"] == pytest.approx(1/3)
    assert not result["accuracy_target_80_point_estimate_met"]


def test_unreviewed_gold_is_rejected():
    frame = gold()
    frame.loc[0, "review_status"] = "pending"
    predictions = pd.DataFrame(columns=["claim_id", "predicted_label", "citation_faithful"])
    with pytest.raises(ValueError, match="approved"):
        evaluate(frame, predictions)
