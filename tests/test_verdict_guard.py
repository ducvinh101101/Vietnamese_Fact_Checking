"""Kiểm thử guard hạ verdict quyết đoán xuống NEI khi bằng chứng không vững."""

from __future__ import annotations

from src.schemas import Evidence, RetrievedEvidence, VerificationResult
from src.verdict_guard import GuardedVerifier, guard_reason, _claim_direction


def _it(pid, content):
    return RetrievedEvidence(
        Evidence(document_id=pid, passage_id=pid, content=content, url="http://x/" + pid), 1.0)


class _FixedVerifier:
    """Verifier giả trả verdict cố định, trích dẫn đoạn đầu."""
    def __init__(self, label, conf=0.9): self.label, self.conf = label, conf
    def verify(self, claim, items):
        ids = [items[0].evidence.passage_id] if items and self.label != "NOT_ENOUGH_INFO" else []
        return VerificationResult(self.label, self.conf, ids, "giả")


CLAIM_UP = "Giá xăng tăng từ chiều nay"


def test_claim_direction():
    assert _claim_direction("Giá xăng tăng chiều nay") == "tăng"
    assert _claim_direction("Giá xăng giảm chiều nay") == "giảm"
    assert _claim_direction("Giá xăng tăng rồi giảm") is None
    assert _claim_direction("Thủ đô là Hà Nội") is None


def test_downgrade_on_mixed_direction():
    # Ca thật: SUPPORTED nhưng bằng chứng nói 'trái chiều'.
    items = [_it("a", "Giá dầu thế giới tăng giảm trái chiều trong phiên.")]
    g = GuardedVerifier(_FixedVerifier("SUPPORTED"))
    out = g.verify(CLAIM_UP, items)
    assert out.label == "NOT_ENOUGH_INFO" and g.last_downgraded


def test_downgrade_on_opposite_direction():
    items = [_it("a", "Giá xăng bán lẻ trong nước giảm 300 đồng/lít chiều nay.")]
    g = GuardedVerifier(_FixedVerifier("SUPPORTED"))
    out = g.verify(CLAIM_UP, items)
    assert out.label == "NOT_ENOUGH_INFO"


def test_keep_support_when_direction_matches():
    items = [_it("a", "Giá xăng bán lẻ trong nước tăng 300 đồng/lít từ chiều nay.")]
    g = GuardedVerifier(_FixedVerifier("SUPPORTED"))
    out = g.verify(CLAIM_UP, items)
    assert out.label == "SUPPORTED" and not g.last_downgraded


def test_downgrade_when_world_oil_forecast_mentions_petrol():
    items = [_it(
        "a",
        "Dầu giảm nhẹ sau khi xả kho dự trữ dầu diesel. Dự báo giá xăng trong nước có thể giảm.",
    )]
    g = GuardedVerifier(_FixedVerifier("SUPPORTED"))
    out = g.verify(CLAIM_UP, items)
    assert out.label == "NOT_ENOUGH_INFO"
    assert "không xác nhận trực tiếp" in (g.last_reason or "")


def test_downgrade_on_offtopic_evidence():
    # Claim giá bán lẻ nhưng bằng chứng toàn giá dầu thế giới -> relevance <= 0.
    items = [_it("a", "Dầu WTI ở mức 90 USD/thùng, dầu Brent trên thị trường thế giới OPEC.")]
    g = GuardedVerifier(_FixedVerifier("SUPPORTED"))
    out = g.verify(CLAIM_UP, items)
    assert out.label == "NOT_ENOUGH_INFO"


def test_offtopic_guard_also_applies_to_refuted():
    items = [_it("a", "Một bài hoàn toàn về bóng đá Ronaldo giải đấu.")]
    g = GuardedVerifier(_FixedVerifier("REFUTED"))
    out = g.verify("Giá xăng tăng chiều nay", items)
    assert out.label == "NOT_ENOUGH_INFO"


def test_direction_guard_does_not_touch_refuted():
    # Claim 'tăng' + bằng chứng 'giảm' => REFUTED hợp lệ, guard KHÔNG hạ.
    items = [_it("a", "Giá xăng bán lẻ trong nước giảm 300 đồng/lít chiều nay.")]
    g = GuardedVerifier(_FixedVerifier("REFUTED"))
    out = g.verify(CLAIM_UP, items)
    assert out.label == "REFUTED" and not g.last_downgraded


def test_nei_passes_through():
    items = [_it("a", "bất kỳ")]
    g = GuardedVerifier(_FixedVerifier("NOT_ENOUGH_INFO"))
    assert g.verify(CLAIM_UP, items).label == "NOT_ENOUGH_INFO"


def test_disabled_guard_keeps_original():
    items = [_it("a", "Giá dầu thế giới tăng giảm trái chiều.")]
    g = GuardedVerifier(_FixedVerifier("SUPPORTED"), enabled=False)
    assert g.verify(CLAIM_UP, items).label == "SUPPORTED"


def test_decisive_without_citation_downgraded():
    assert guard_reason(CLAIM_UP, VerificationResult("SUPPORTED", 0.9, [], "x"), []) is not None
