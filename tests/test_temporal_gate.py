"""Kiểm thử neo thời gian (temporal gating) cho claim thời sự.

Hợp đồng:
- Claim thời sự: loại bằng chứng cũ hơn cửa sổ cho phép; hết bằng chứng mới -> rỗng
  -> pipeline trả NOT_ENOUGH_INFO (không SUPPORTED bằng bài cũ).
- Claim phi thời sự: đi qua nguyên vẹn (bài cũ vẫn hợp lệ).
- Bằng chứng không rõ ngày đăng bị loại cho claim thời sự (mặc định), nới được.
- Gate tắt -> không can thiệp.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.schemas import Evidence, RetrievedEvidence
from src.temporal_gate import TemporalGateRetriever, _published_date


AS_OF = date(2026, 10, 3)
TS_CLAIM = "Giá xăng tăng chiều nay"
HISTORICAL_CLAIM = "Thủ đô của Việt Nam là Hà Nội"


def _ev(pid: str, published_at: str | None, score: float) -> RetrievedEvidence:
    return RetrievedEvidence(
        Evidence(document_id=pid, passage_id=pid, content="nội dung " + pid,
                 url="http://x/" + pid, published_at=published_at),
        score,
    )


class _FakeInner:
    """Retriever giả trả danh sách cố định, sắp theo score giảm dần."""

    def __init__(self, items: list[RetrievedEvidence]) -> None:
        self.items = sorted(items, key=lambda i: -i.score)
        self.last_top_k: int | None = None

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        self.last_top_k = top_k
        return self.items[:top_k]


def test_drops_stale_and_undated_for_time_sensitive():
    inner = _FakeInner([
        _ev("stale-2023", "2023-03-13", 0.9),
        _ev("fresh", "2026-10-01T08:00:00+07:00", 0.8),
        _ev("undated", None, 0.7),
        _ev("recent", "2026-09-20", 0.6),
    ])
    gate = TemporalGateRetriever(inner, as_of=AS_OF, window_days=30, candidate_k=10)
    kept = gate.search(TS_CLAIM, top_k=5)
    assert [i.evidence.passage_id for i in kept] == ["fresh", "recent"]
    assert gate.last_applied is True
    assert gate.last_cutoff == date(2026, 9, 3)
    assert gate.last_dropped == 2


def test_all_stale_returns_empty_so_pipeline_is_nei():
    inner = _FakeInner([_ev("a", "2023-03-13", 0.9), _ev("b", None, 0.8)])
    gate = TemporalGateRetriever(inner, as_of=AS_OF, window_days=30)
    assert gate.search(TS_CLAIM, top_k=3) == []
    assert gate.last_dropped == 2


def test_historical_claim_passes_through_untouched():
    items = [_ev("old", "2015-01-01", 0.9), _ev("mid", "2020-06-06", 0.8)]
    gate = TemporalGateRetriever(_FakeInner(items), as_of=AS_OF, window_days=30)
    kept = gate.search(HISTORICAL_CLAIM, top_k=3)
    assert [i.evidence.passage_id for i in kept] == ["old", "mid"]
    assert gate.last_applied is False


def test_keep_undated_flag_relaxes():
    inner = _FakeInner([_ev("undated", None, 0.9), _ev("fresh", "2026-10-01", 0.8)])
    gate = TemporalGateRetriever(inner, as_of=AS_OF, window_days=30, drop_unknown_dates=False)
    kept = gate.search(TS_CLAIM, top_k=5)
    assert {i.evidence.passage_id for i in kept} == {"undated", "fresh"}


def test_disabled_gate_passes_through():
    items = [_ev("stale", "2023-03-13", 0.9)]
    gate = TemporalGateRetriever(_FakeInner(items), as_of=AS_OF, enabled=False)
    kept = gate.search(TS_CLAIM, top_k=3)
    assert [i.evidence.passage_id for i in kept] == ["stale"]
    assert gate.last_applied is False


def test_overfetches_candidate_k_before_truncating():
    inner = _FakeInner([_ev(f"e{i}", "2026-10-01", 1.0 - i / 100) for i in range(15)])
    gate = TemporalGateRetriever(inner, as_of=AS_OF, window_days=30, candidate_k=12)
    gate.search(TS_CLAIM, top_k=3)
    # Gate phải xin dư ứng viên (>= candidate_k) rồi mới cắt về top_k.
    assert inner.last_top_k == 12


def test_result_capped_at_top_k():
    inner = _FakeInner([_ev(f"e{i}", "2026-10-01", 1.0 - i / 100) for i in range(15)])
    gate = TemporalGateRetriever(inner, as_of=AS_OF, window_days=30, candidate_k=12)
    kept = gate.search(TS_CLAIM, top_k=3)
    assert len(kept) == 3


def test_keeps_descending_score_order():
    inner = _FakeInner([
        _ev("hi", "2026-10-01", 0.9),
        _ev("lo", "2026-10-02", 0.4),
        _ev("mid", "2026-09-30", 0.6),
    ])
    gate = TemporalGateRetriever(inner, as_of=AS_OF, window_days=30, candidate_k=10)
    kept = gate.search(TS_CLAIM, top_k=5)
    scores = [i.score for i in kept]
    assert scores == sorted(scores, reverse=True)


def test_published_date_parser():
    assert _published_date("2026-10-01T08:00:00+07:00") == date(2026, 10, 1)
    assert _published_date("2023-03-13") == date(2023, 3, 13)
    assert _published_date(None) is None
    assert _published_date("rác") is None


def test_rejects_bad_window():
    with pytest.raises(ValueError):
        TemporalGateRetriever(_FakeInner([]), window_days=-1)


# --- Cửa sổ phân tầng theo loại mốc ------------------------------------------

from src.query_enrichment import recency_class


def test_recency_class_today_vs_current():
    assert recency_class("Giá xăng tăng chiều nay") == "today"
    assert recency_class("Tổng thống Mỹ hiện nay là ai") == "current"
    assert recency_class("Thủ đô Việt Nam là Hà Nội") is None
    assert recency_class("Giá xăng ngày 13/3/2023") is None  # có ngày tuyệt đối


def test_today_claim_uses_narrow_window():
    inner = _FakeInner([
        _ev("d20", "2026-09-20", 0.9),   # 13 ngày trước -> ngoài cửa sổ 10 ngày
        _ev("d30", "2026-09-30", 0.8),   # 3 ngày trước -> trong cửa sổ
    ])
    gate = TemporalGateRetriever(inner, as_of=AS_OF, window_today=10, window_current=365)
    kept = gate.search("Giá xăng tăng chiều nay", top_k=5)
    assert [i.evidence.passage_id for i in kept] == ["d30"]
    assert gate.last_class == "today" and gate.last_window == 10


def test_current_claim_uses_wide_window():
    inner = _FakeInner([
        _ev("apr", "2026-04-28", 0.9),   # ~5 tháng trước -> trong cửa sổ 365
        _ev("old", "2024-01-01", 0.8),   # >365 ngày -> ngoài
    ])
    gate = TemporalGateRetriever(inner, as_of=AS_OF, window_today=10, window_current=365)
    kept = gate.search("Tổng thống Mỹ hiện nay là Trump", top_k=5)
    assert [i.evidence.passage_id for i in kept] == ["apr"]
    assert gate.last_class == "current" and gate.last_window == 365
