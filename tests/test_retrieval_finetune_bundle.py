import pandas as pd
import pytest

from scripts.build_retrieval_finetune_bundle import merge_training
from scripts.materialize_train_pair_ai_review import materialize


def frames():
    gold = pd.DataFrame([dict(Statement="claim", Evidence="gold", Url="train-url", labels=0)])
    silver = pd.DataFrame([dict(Statement="claim", Evidence="passage", Url="train-url", labels=2,
                                passage_url="train-url", label_origin="ai_silver", review_status="ai_reviewed")])
    return gold, silver


def test_weights_and_train_mix():
    gold, silver = frames()
    original, combined, conflicts, added = merge_training(gold, silver, {"dev-url"})
    assert added == 1 and conflicts.empty
    assert combined.sample_weight.tolist() == [1.0, 0.5]
    assert original.sample_weight.tolist() == [1.0]


def test_duplicate_gold_not_reweighted_by_silver():
    gold, silver = frames()
    silver.loc[0, "Evidence"] = "gold"
    silver.loc[0, "labels"] = 0
    _, combined, conflicts, added = merge_training(gold, silver, set())
    assert len(combined) == 1 and added == 0 and conflicts.empty


def test_conflict_quarantined_without_overwriting_gold():
    gold, silver = frames()
    silver.loc[0, "Evidence"] = "gold"
    _, combined, conflicts, added = merge_training(gold, silver, set())
    assert len(conflicts) == 1 and added == 0
    assert combined.labels.tolist() == [0]


def test_heldout_passage_rejected():
    gold, silver = frames()
    silver.loc[0, "passage_url"] = "dev-url"
    with pytest.raises(ValueError):
        merge_training(gold, silver, {"dev-url"})


def test_ledger_requires_complete_unique_coverage():
    source = pd.DataFrame({"review_status": ["pending"] * 540})
    ledger = pd.DataFrame({"row": list(range(539)) + [0], "decision": ["N"] * 540, "note": ["reason"] * 540})
    with pytest.raises(ValueError):
        materialize(source, ledger)


def test_materialize_never_promotes_ai_to_human_gold():
    source = pd.DataFrame({"review_status": ["pending"] * 540})
    ledger = pd.DataFrame({"row": range(540), "decision": ["S"] * 539 + ["U"], "note": ["reason"] * 540})
    result = materialize(source, ledger)
    assert "approved" not in set(result.review_status)
    assert result.iloc[-1].review_status == "needs_human_review"
    assert result.iloc[-1].reviewed_pair_label == ""
