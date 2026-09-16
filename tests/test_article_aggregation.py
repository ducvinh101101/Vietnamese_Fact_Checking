import pytest

from src.article_aggregation import ArticleAggregator
from src.schemas import Claim, VerificationResult


def make_claim(claim_id: str) -> Claim:
    return Claim(claim_id=claim_id, article_id="article_001", text=f"Nội dung {claim_id}.")


def result(label: str) -> VerificationResult:
    return VerificationResult(label, 0.8, ["evidence-1"], "Kết quả test")


def test_refuted_claim_is_not_a_whole_article_fake_verdict():
    claims = [make_claim("c1"), make_claim("c2")]
    aggregation = ArticleAggregator().aggregate(
        claims, {"c1": result("REFUTED"), "c2": result("SUPPORTED")}
    )

    assert aggregation.assessment == "HAS_REFUTED_CLAIMS"
    assert aggregation.refuted_count == 1
    assert "không kết luận toàn bộ bài viết là giả" in aggregation.explanation


def test_missing_verdict_is_reported_transparently():
    aggregation = ArticleAggregator().aggregate([make_claim("c1"), make_claim("c2")], {"c1": result("REFUTED")})

    assert aggregation.assessment == "PARTIALLY_EVALUATED"
    assert aggregation.unverified_count == 1
    assert aggregation.claims[1].label is None


def test_all_nei_stays_insufficient_evidence():
    aggregation = ArticleAggregator().aggregate([make_claim("c1")], {"c1": result("NOT_ENOUGH_INFO")})

    assert aggregation.assessment == "INSUFFICIENT_EVIDENCE"


def test_results_from_another_article_are_rejected():
    with pytest.raises(ValueError, match="không thuộc article"):
        ArticleAggregator().aggregate([make_claim("c1")], {"other": result("SUPPORTED")})
