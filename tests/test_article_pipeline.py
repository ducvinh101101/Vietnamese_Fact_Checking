import pytest

from src.article_pipeline import ArticleFactCheckingPipeline
from src.schemas import Article, Evidence, RetrievedEvidence, VerificationResult


class StubClaimRunner:
    def __init__(self, results):
        self.results = results
        self.calls = []
        self.retrieved = [RetrievedEvidence(Evidence("doc", "p1", "Evidence"), 0.8)]

    def run(self, claim):
        self.calls.append(claim)
        return self.results[len(self.calls) - 1], self.retrieved


def article(body="Thông tin thứ nhất. Thông tin thứ hai."):
    return Article(
        article_id="article_001",
        title="",
        body=body,
        url="https://example.com/article",
        retrieved_at="2026-09-06T00:00:00Z",
    )


def verdict(label, evidence_ids=None):
    return VerificationResult(label, 0.8, evidence_ids if evidence_ids is not None else ["p1"], "Stub")


def test_article_pipeline_runs_each_claim_and_keeps_per_claim_provenance():
    runner = StubClaimRunner([verdict("SUPPORTED"), verdict("REFUTED")])
    result = ArticleFactCheckingPipeline(runner).run(article())

    assert runner.calls == ["Thông tin thứ nhất.", "Thông tin thứ hai."]
    assert result.article_id == "article_001"
    assert result.aggregation.assessment == "HAS_REFUTED_CLAIMS"
    assert [run.result.label for run in result.claim_runs] == ["SUPPORTED", "REFUTED"]
    assert result.claim_runs[1].result.evidence_ids == ["p1"]


def test_article_pipeline_returns_no_claims_without_calling_runner():
    runner = StubClaimRunner([])
    result = ArticleFactCheckingPipeline(runner).run(article("Liệu đây có phải câu hỏi?"))

    assert runner.calls == []
    assert result.aggregation.assessment == "NO_CLAIMS"
    assert result.aggregation.article_id == "article_001"


def test_article_pipeline_rejects_citation_outside_claim_evidence():
    runner = StubClaimRunner([verdict("SUPPORTED", ["outside"])])

    with pytest.raises(RuntimeError, match="không thuộc evidence"):
        ArticleFactCheckingPipeline(runner).run(article("Một claim hợp lệ."))
