"""Kiểm thử gộp theo URL + xếp theo độ khớp chủ đề."""

from __future__ import annotations

import pytest

from src.schemas import Evidence, RetrievedEvidence
from src.topical_rerank import TopicalRerankRetriever, relevance


def _ev(pid, url, content, score):
    return RetrievedEvidence(
        Evidence(document_id=url, passage_id=pid, content=content, url=url), score)


class _Inner:
    def __init__(self, items): self.items = items
    def search(self, claim, top_k=3): return self.items[:top_k]


CLAIM = "Giá xăng tăng từ chiều nay"


def test_retail_scores_higher_than_world():
    world = "Giá dầu WTI 90 USD/thùng, dầu Brent giảm trên thị trường thế giới."
    retail = "Giá xăng bán lẻ trong nước kỳ điều hành tăng 300 đồng/lít theo liên bộ."
    assert relevance(CLAIM, retail) > relevance(CLAIM, world)


def test_collapse_one_line_per_url_picks_best_passage():
    A = "http://x/a"
    items = [
        _ev("A-p01", A, "Giá dầu WTI USD/thùng thị trường thế giới.", 20.0),
        _ev("A-p02", A, "Giá xăng bán lẻ trong nước tăng 300 đồng/lít kỳ điều hành.", 18.0),
    ]
    out = TopicalRerankRetriever(_Inner(items), candidate_k=10).search(CLAIM, top_k=5)
    assert len(out) == 1  # một URL -> một dòng
    assert "bán lẻ" in out[0].evidence.content  # chọn đoạn khớp nhất


def test_retail_article_outranks_world_article():
    out = TopicalRerankRetriever(_Inner([
        _ev("w", "http://x/world", "Giá dầu Brent WTI USD/thùng thế giới.", 20.0),
        _ev("r", "http://x/retail", "Giá xăng bán lẻ trong nước tăng 300 đồng/lít.", 5.0),
    ]), candidate_k=10).search(CLAIM, top_k=5)
    assert out[0].evidence.url.endswith("/retail")


def test_scores_strictly_descending_for_pipeline():
    out = TopicalRerankRetriever(_Inner([
        _ev(f"e{i}", f"http://x/{i}", "giá xăng bán lẻ tăng đồng/lít", 1.0) for i in range(5)
    ]), candidate_k=10).search(CLAIM, top_k=5)
    scores = [r.score for r in out]
    assert all(scores[i] > scores[i + 1] for i in range(len(scores) - 1))


def test_distinct_urls_in_output():
    A, B = "http://x/a", "http://x/b"
    out = TopicalRerankRetriever(_Inner([
        _ev("a1", A, "giá xăng bán lẻ tăng", 3.0),
        _ev("a2", A, "giá xăng bán lẻ tăng mạnh", 2.0),
        _ev("b1", B, "giá xăng bán lẻ giảm", 1.0),
    ]), candidate_k=10).search(CLAIM, top_k=5)
    assert len({r.evidence.url for r in out}) == len(out)


def test_disabled_passes_through():
    items = [_ev("a1", "http://x/a", "giá xăng", 3.0), _ev("a2", "http://x/a", "giá dầu", 2.0)]
    out = TopicalRerankRetriever(_Inner(items), enabled=False).search(CLAIM, top_k=5)
    assert len(out) == 2  # không gộp khi tắt


def test_non_price_claim_uses_pure_overlap():
    claim = "Thủ đô Việt Nam là Hà Nội"
    a = "Hà Nội là thủ đô của Việt Nam."
    b = "Thành phố Hồ Chí Minh là trung tâm kinh tế."
    assert relevance(claim, a) > relevance(claim, b)


def test_unrelated_high_score_cannot_be_top_one():
    claim = "Bộ Y tế công bố lịch tiêm chủng"
    out = TopicalRerankRetriever(_Inner([
        _ev("noise", "https://x/noise", "Đội tuyển bóng đá giành chiến thắng.", 100.0),
        _ev("match", "https://x/match", "Bộ Y tế công bố lịch tiêm chủng cho trẻ em.", 1.0),
    ])).search(claim, top_k=2)
    assert [item.evidence.passage_id for item in out] == ["match"]
