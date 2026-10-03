import pandas as pd
import pytest
from scripts.export_reviewed_training_pairs import validate_reviews


def inputs():
    return (pd.DataFrame([dict(pair_id="1", split="train", claim="claim", claim_source_url="train-url",
                              passage_id="p", passage="evidence", passage_url="train-url", reviewed_pair_label="REFUTED",
                              reviewer="Vinh", review_notes="Passage contradicts the number in the claim", review_status="approved")]),
            pd.DataFrame([dict(Statement="claim", Url="train-url")]),
            {"p": {"content": "evidence", "url": "train-url"}}, {"heldout"})


def test_export_uses_reviewed_relation_and_keeps_provenance():
    result = validate_reviews(*inputs())
    assert result.iloc[0].labels == 1
    assert result.iloc[0].passage_id == "p"


@pytest.mark.parametrize("field,value", [("review_status", "pending"), ("claim_source_url", "heldout"), ("passage", "tampered"), ("reviewer", "")])
def test_export_rejects_unapproved_or_invalid_training_pairs(field, value):
    reviews, train, corpus, held = inputs()
    reviews.loc[0, field] = value
    with pytest.raises(ValueError):
        validate_reviews(reviews, train, corpus, held)


def test_ai_silver_requires_opt_in_and_retains_origin():
    reviews, train, corpus, held = inputs()
    reviews.loc[0, "review_status"] = "ai_reviewed"
    with pytest.raises(ValueError):
        validate_reviews(reviews, train, corpus, held)
    result = validate_reviews(reviews, train, corpus, held, allow_ai_reviewed=True)
    assert result.iloc[0].label_origin == "ai_silver"


def test_unresolved_never_exported_even_with_ai_opt_in():
    reviews, train, corpus, held = inputs()
    reviews.loc[0, "review_status"] = "needs_human_review"
    with pytest.raises(ValueError):
        validate_reviews(reviews, train, corpus, held, allow_ai_reviewed=True)
