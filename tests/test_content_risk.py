"""Kiểm thử content-risk W4-06: chấm điểm, dải, OOD, và tách biệt khỏi verdict."""

from __future__ import annotations

from pathlib import Path

import joblib
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline

from src.article_aggregation import ArticleAggregator
from src.article_pipeline import ArticleFactCheckingPipeline
from src.claim_decomposer import ClaimDecomposer
from src.content_risk import ContentRiskScorer
from src.schemas import Article, Evidence, RetrievedEvidence, VerificationResult


def _tiny_model() -> Pipeline:
    texts = [
        "[TITLE] sốc kinh hoàng [BODY] tin chấn động lan truyền chóng mặt",
        "[TITLE] cực sốc [BODY] không thể tin nổi sự thật bị giấu kín",
        "[TITLE] họp báo chính phủ [BODY] số liệu công bố theo quy trình thẩm định",
        "[TITLE] báo cáo thường niên [BODY] kết quả kiểm toán được công bố minh bạch",
    ]
    labels = [1, 1, 0, 0]
    model = Pipeline([
        ("tfidf", TfidfVectorizer()),
        ("clf", LogisticRegression()),
    ])
    model.fit(texts, labels)
    return model


def test_score_in_range_and_banded() -> None:
    scorer = ContentRiskScorer(_tiny_model(), band_edges=(0.34, 0.67),
                               training_source_domains=frozenset({"vnexpress.net"}))
    high = scorer.score("cực sốc kinh hoàng", "tin chấn động bị giấu kín")
    low = scorer.score("họp báo chính phủ", "số liệu kiểm toán minh bạch")
    assert high is not None and low is not None
    assert 0.0 <= high.risk_score <= 1.0
    assert high.risk_score > low.risk_score
    assert high.band in ("thấp", "trung bình", "cao")
    assert "không phải bằng chứng" in high.disclaimer.lower()


def test_out_of_distribution_flag() -> None:
    scorer = ContentRiskScorer(_tiny_model(), training_source_domains=frozenset({"vnexpress.net"}))
    known = scorer.score("t", "b", source_domain="vnexpress.net")
    unknown = scorer.score("t", "b", source_domain="trang-la.example")
    assert known is not None and unknown is not None
    assert known.out_of_distribution_source is False
    assert unknown.out_of_distribution_source is True


def test_disabled_scorer_returns_none() -> None:
    scorer = ContentRiskScorer(None)
    assert scorer.enabled is False
    assert scorer.score("bất kỳ", "nội dung") is None


def test_load_round_trip(tmp_path: Path) -> None:
    directory = tmp_path / "e9_content_risk"
    directory.mkdir()
    joblib.dump(_tiny_model(), directory / "model.joblib")
    (directory / "metadata.json").write_text(
        '{"band_edges": [0.34, 0.67], "band_names": ["thấp", "trung bình", "cao"],'
        ' "training_source_domains": ["vnexpress.net"]}',
        encoding="utf-8",
    )
    scorer = ContentRiskScorer.load(directory)
    assessment = scorer.score("cực sốc", "tin chấn động", source_domain="khac.example")
    assert assessment is not None
    assert assessment.out_of_distribution_source is True


class _StubRunner:
    """Verifier giả: luôn REFUTED, để chứng minh content-risk KHÔNG đổi verdict."""

    def run(self, claim: str) -> tuple[VerificationResult, list[RetrievedEvidence]]:
        evidence = Evidence(document_id="d", passage_id="d-p1", content="x", url="u")
        result = VerificationResult(label="REFUTED", confidence=0.9, evidence_ids=["d-p1"], explanation="")
        return result, [RetrievedEvidence(evidence, 1.0)]


def _article() -> Article:
    return Article(
        article_id="a1",
        title="cực sốc kinh hoàng",
        body="Tin chấn động bị giấu kín. Sự thật gây bàng hoàng.",
        url="https://trang-la.example/bai",
        retrieved_at=None,
    )


def test_content_risk_does_not_change_verdict() -> None:
    pipeline_no_risk = ArticleFactCheckingPipeline(_StubRunner(), ClaimDecomposer(), ArticleAggregator())
    pipeline_with_risk = ArticleFactCheckingPipeline(
        _StubRunner(), ClaimDecomposer(), ArticleAggregator(),
        content_risk_scorer=ContentRiskScorer(_tiny_model(), training_source_domains=frozenset({"vnexpress.net"})),
    )
    run_without = pipeline_no_risk.run(_article())
    run_with = pipeline_with_risk.run(_article())

    # Verdict từng claim và tổng hợp cấp bài phải y hệt dù có hay không content-risk.
    assert run_without.content_risk is None
    assert run_with.content_risk is not None
    assert [r.result.label for r in run_without.claim_runs] == [r.result.label for r in run_with.claim_runs]
    assert run_without.aggregation.assessment == run_with.aggregation.assessment
    # Nguồn ngoài phân bố huấn luyện phải được gắn cờ.
    assert run_with.content_risk.out_of_distribution_source is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
