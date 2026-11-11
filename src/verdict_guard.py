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

import math
import re

from src.contracts import Verifier
from src.schemas import RetrievedEvidence, VerificationResult
from src.topical_rerank import _RETAIL_HINTS, relevance

_DECISIVE = ("SUPPORTED", "REFUTED")
_OPPOSITE = {"tăng": "giảm", "giảm": "tăng"}
# Không cắt ở dấu '.' nằm giữa hai chữ số (số kiểu Việt '1.500', thập phân '2.5').
_SENTENCES = re.compile(r"(?<!\d)[.!?;]+|[.!?;]+(?!\d)")
_NEG_DIRECTION = re.compile(r"\b(?:không|chưa|chẳng|chả)\s+(?:hề\s+|được\s+|có\s+)?(tăng|giảm)\b")
_NEG_WORDS = ("không", "chưa", "chẳng", "chả")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_WORDS = re.compile(r"\w+", re.UNICODE)
_HEDGED_PRICE_WORDS = ("dự báo", "có thể", "khả năng", "ước tính", "kỳ vọng")
_RELATIVE_TIME_WORDS = ("hôm nay", "chiều nay", "sáng nay", "tối nay", "ngày mai")
_TIME_IN_SENTENCE = re.compile(r"\b(?:từ\s*)?\d{1,2}\s*(?:h|giờ)\b|\bngày\s+\d{1,2}(?:[/-]\d{1,2})?\b")
_FOCUS_STOPWORDS = frozenset(
    "và của có là các một những được cho với từ đã đang sẽ trong ngoài trên dưới khi về "
    "thì mà nếu nên hay hoặc tại theo đến ra vào này đó kia ấy rất quá cũng chỉ vẫn còn "
    "chiều sáng trưa tối đêm nay mai qua hôm hiện bây giờ gần đây mới đây vừa tuần tháng "
    "năm ngày số giá tăng giảm".split()
)


def _claim_direction(claim: str) -> str | None:
    """Claim khẳng định chiều gì? 'tăng'/'giảm'/None (None nếu có cả hai/không có)."""
    text = _NEG_DIRECTION.sub(" ", claim.casefold())     # 'không tăng' không khẳng định 'tăng'
    has_up, has_down = "tăng" in text, "giảm" in text
    if has_up and not has_down:
        return "tăng"
    if has_down and not has_up:
        return "giảm"
    return None


def _negated_direction(claim: str) -> str | None:
    """Chiều bị PHỦ ĐỊNH trong claim ('không tăng' -> 'tăng'), hoặc None."""
    found = {m.group(1) for m in _NEG_DIRECTION.finditer(claim.casefold())}
    return found.pop() if len(found) == 1 else None


def _canon_number(token: str) -> str:
    low = token.replace(".", "") if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token) else token.replace(",", ".")
    try:
        return f"{float(low):g}"
    except ValueError:
        return low


def _numbers(text: str) -> set[str]:
    return {_canon_number(t) for t in _NUMBER.findall(text)}


def _numbers_contradict(claim: str, cited_texts: list[str], coverage: float) -> bool:
    """Số trong claim vắng ở bằng chứng VÀ câu bằng chứng khớp chủ đề nhất mang số khác.

    Thiếu số (bằng chứng không nhắc năm) không phải mâu thuẫn; chỉ coi là mâu thuẫn khi
    có phép THAY số: claim 500 vs câu nguồn nói 300 về cùng chủ đề."""
    claim_numbers = _numbers(claim)
    if not claim_numbers:
        return False
    focus = _focus_terms(claim)
    all_numbers = set().union(*(_numbers(t) for t in cited_texts)) if cited_texts else set()
    missing = claim_numbers - all_numbers
    if not missing:
        return False
    best_sentence, best_cover = "", -1
    for text in cited_texts:
        for sentence in _SENTENCES.split(text.casefold()):
            cover = _focus_coverage(focus, sentence)
            if cover > best_cover:
                best_sentence, best_cover = sentence, cover
    return bool(_numbers(best_sentence) - claim_numbers) and best_cover >= max(1, math.ceil(len(focus) * coverage))


def _focus_terms(claim: str) -> set[str]:
    """Return claim terms that identify its subject, not generic relation words."""
    return {
        word for word in _WORDS.findall(claim.casefold())
        if len(word) > 1 and word not in _FOCUS_STOPWORDS
    }


def _focus_coverage(focus: set[str], sentence: str) -> int:
    return len(focus & set(_WORDS.findall(sentence.casefold())))


def _has_direct_subject_support(claim: str, passage: str, direction: str | None = None,
                                coverage: float = 0.6) -> bool:
    """Require one sentence to cover the claim subject and, when present, direction.

    This intentionally prefers abstention over treating loose lexical similarity
    as entailment.  It blocks evidence that shares only broad words such as
    "giá" while discussing another entity or a speculative outcome.
    """
    focus = _focus_terms(claim)
    required = max(1, math.ceil(len(focus) * coverage)) if focus else 0
    for sentence in _SENTENCES.split(passage.casefold()):
        if required and _focus_coverage(focus, sentence) < required:
            continue
        if direction is not None and direction not in sentence:
            continue
        if direction is not None and any(hedge in sentence for hedge in _HEDGED_PRICE_WORDS):
            continue
        return True
    return False


def _has_direct_retail_fuel_support(claim: str, passage: str, direction: str) -> bool:
    """Return whether a time-sensitive petrol-price claim has direct support.

    Articles about crude oil often mention a *forecast* for petrol prices.  That
    is not evidence that Vietnamese retail petrol has already changed.  For this
    narrow high-risk claim type, require the same sentence to name petrol, state
    the claimed direction, and contain a retail/price-administration indicator.
    """
    claim_low = claim.casefold()
    if "xăng" not in claim_low or not any(word in claim_low for word in _RELATIVE_TIME_WORDS):
        return True
    for sentence in _SENTENCES.split(passage.casefold()):
        if (
            "xăng" in sentence
            and direction in sentence
            and any(hint in sentence for hint in _RETAIL_HINTS)
            and not any(hedge in sentence for hedge in _HEDGED_PRICE_WORDS)
            and (
                not any(word in claim_low for word in _RELATIVE_TIME_WORDS)
                or any(word in sentence for word in _RELATIVE_TIME_WORDS)
                or _TIME_IN_SENTENCE.search(sentence) is not None
            )
        ):
            return True
    return False


def guard_reason(claim: str, result: VerificationResult,
                 evidence_items: list[RetrievedEvidence],
                 min_relevance: float = 0.0, focus_coverage: float = 0.6) -> str | None:
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
    if not any(_has_direct_subject_support(claim, e.content, coverage=focus_coverage) for e in cited):
        return "bằng chứng không nêu trực tiếp chủ đề trọng tâm của claim"

    # (2) Ngược chiều / mơ hồ — chỉ với SUPPORTED.
    if result.label == "SUPPORTED":
        negated = _negated_direction(claim)
        if negated is not None:
            for e in cited:
                for sentence in _SENTENCES.split(e.content.casefold()):
                    if negated in sentence and not any(w in sentence for w in _NEG_WORDS) \
                            and _OPPOSITE[negated] not in sentence:
                        return f"claim phủ định '{negated}' nhưng bằng chứng khẳng định '{negated}'"
        if _numbers_contradict(claim, [e.content for e in cited], focus_coverage):
            return "số liệu trong claim khác với số liệu trong bằng chứng"
        direction = _claim_direction(claim)
        if direction is not None:
            text = " ".join(e.content for e in cited).casefold()
            if not any(_has_direct_subject_support(claim, e.content, direction, focus_coverage) for e in cited):
                return f"bằng chứng không khẳng định trực tiếp chiều '{direction}' của claim"
            if not any(_has_direct_retail_fuel_support(claim, e.content, direction) for e in cited):
                return (
                    "bằng chứng không xác nhận trực tiếp giá xăng bán lẻ "
                    f"'{direction}'"
                )
            if "trái chiều" in text:
                return f"bằng chứng nói 'trái chiều' — chưa khẳng định được '{direction}'"
            opposite = _OPPOSITE[direction]
            if opposite in text and direction not in text:
                return f"bằng chứng nói '{opposite}', ngược với claim '{direction}'"
    return None


class GuardedVerifier:
    """Bọc một Verifier: giữ verify() nhưng hạ verdict xuống NEI khi guard phát hiện
    bằng chứng không vững. Bọc trong suốt — pipeline dùng như verifier thường."""

    def __init__(self, inner: Verifier, enabled: bool = True, min_relevance: float = 0.0,
                 focus_coverage: float = 0.6) -> None:
        self.inner = inner
        self.enabled = enabled
        self.min_relevance = min_relevance
        self.focus_coverage = focus_coverage
        self.last_downgraded = False
        self.last_reason: str | None = None
        self.last_model_result: VerificationResult | None = None

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        result = self.inner.verify(claim, evidence_items)
        self.last_model_result = result
        self.last_downgraded = False
        self.last_reason = None
        if result.status == 'error':
            return result
        if not self.enabled:
            return result
        reason = guard_reason(claim, result, evidence_items, self.min_relevance, self.focus_coverage)
        if reason is None:
            return result
        self.last_downgraded = True
        self.last_reason = reason
        return VerificationResult(
            "NOT_ENOUGH_INFO", 0.0, [],
            f"[guard] Hạ từ {result.label} xuống NEI: {reason}.",
        )
