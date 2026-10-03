"""Guard hạ verdict quyết đoán xuống NEI khi bằng chứng trích dẫn không vững.

Quan sát thực tế: verifier (PhoBERT) đôi khi trả SUPPORTED với độ tin cao dựa trên
bằng chứng THỰC RA không ủng hộ claim — ví dụ claim "giá xăng TĂNG chiều nay" nhưng
đoạn trích nói giá dầu thế giới "tăng giảm TRÁI CHIỀU" hoặc "giảm". Đây là false
positive — lỗi tệ nhất với một hệ fact-check.

Guard này là lớp AN TOÀN hậu kiểm, cố ý BẢO THỦ (chỉ hạ khi có dấu hiệu rõ), và
tắt được. Nó KHÔNG bao giờ "nâng" verdict, chỉ có thể hạ xuống NOT_ENOUGH_INFO:

1) Lạc chủ đề: nếu đoạn được trích có độ khớp chủ đề với claim <= ngưỡng (dùng lại
   hàm relevance của topical_rerank — có trừ điểm nếu đoạn chỉ nói giá dầu thế giới
   trong khi claim hỏi giá bán lẻ) -> hạ, vì "ủng hộ/bác bỏ" không có căn cứ chủ đề.
   Áp dụng cho cả SUPPORTED và REFUTED.
2) Ngược chiều / mơ hồ (chỉ với SUPPORTED): nếu claim khẳng định một CHIỀU
   (tăng/giảm) mà đoạn trích nói "trái chiều", hoặc chỉ nói chiều ngược lại mà không
   nói chiều của claim -> hạ, vì bằng chứng không thực sự ủng hộ chiều đó.
   (Với REFUTED thì ngược chiều lại là HỢP LỆ nên không đụng.)

Guard chỉ đọc nội dung ĐÃ trích dẫn; không gọi lại mô hình, không sửa bằng chứng.
"""

from __future__ import annotations

from src.contracts import Verifier
from src.schemas import RetrievedEvidence, VerificationResult
from src.topical_rerank import relevance

_DECISIVE = ("SUPPORTED", "REFUTED")
_OPPOSITE = {"tăng": "giảm", "giảm": "tăng"}


def _claim_direction(claim: str) -> str | None:
    """Claim khẳng định chiều gì? 'tăng'/'giảm'/None (None nếu có cả hai/không có)."""
    text = claim.casefold()
    has_up, has_down = "tăng" in text, "giảm" in text
    if has_up and not has_down:
        return "tăng"
    if has_down and not has_up:
        return "giảm"
    return None


def guard_reason(claim: str, result: VerificationResult,
                 evidence_items: list[RetrievedEvidence],
                 min_relevance: float = 0.0) -> str | None:
    """Trả lý do cần hạ xuống NEI, hoặc None nếu verdict giữ nguyên."""
    if result.label not in _DECISIVE:
        return None
    cited_ids = set(result.evidence_ids)
    cited = [it.evidence for it in evidence_items if it.evidence.passage_id in cited_ids]
    if not cited:
        # Verdict quyết đoán mà không có trích dẫn -> không có căn cứ.
        return "verdict quyết đoán nhưng không có đoạn bằng chứng được trích dẫn"

    # (1) Lạc chủ đề: đoạn khớp nhất vẫn <= ngưỡng.
    best_rel = max(relevance(claim, e.content) for e in cited)
    if best_rel <= min_relevance:
        return "bằng chứng trích dẫn không khớp chủ đề của claim"

    # (2) Ngược chiều / mơ hồ — chỉ với SUPPORTED.
    if result.label == "SUPPORTED":
        direction = _claim_direction(claim)
        if direction is not None:
            text = " ".join(e.content for e in cited).casefold()
            if "trái chiều" in text:
                return f"bằng chứng nói 'trái chiều' — chưa khẳng định được '{direction}'"
            opposite = _OPPOSITE[direction]
            if opposite in text and direction not in text:
                return f"bằng chứng nói '{opposite}', ngược với claim '{direction}'"
    return None


class GuardedVerifier:
    """Bọc một Verifier: giữ verify() nhưng hạ verdict xuống NEI khi guard phát hiện
    bằng chứng không vững. Bọc trong suốt — pipeline dùng như verifier thường."""

    def __init__(self, inner: Verifier, enabled: bool = True, min_relevance: float = 0.0) -> None:
        self.inner = inner
        self.enabled = enabled
        self.min_relevance = min_relevance
        self.last_downgraded = False
        self.last_reason: str | None = None

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        result = self.inner.verify(claim, evidence_items)
        self.last_downgraded = False
        self.last_reason = None
        if not self.enabled:
            return result
        reason = guard_reason(claim, result, evidence_items, self.min_relevance)
        if reason is None:
            return result
        self.last_downgraded = True
        self.last_reason = reason
        return VerificationResult(
            "NOT_ENOUGH_INFO", 0.0, [],
            f"[guard] Hạ từ {result.label} xuống NEI: {reason}.",
        )
