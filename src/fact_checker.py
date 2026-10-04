"""Verifier có fallback xác định được để demo không phụ thuộc API/LLM.

Lớp này sẽ được thay bằng verifier PhoBERT/XLM-R đã fine-tune.
"""

import re

from src.evidence_focus import split_sentences
from src.minimal_pair import _canon
from src.preprocessing import tokenize_for_retrieval
from src.schemas import RetrievedEvidence, VerificationResult


def _numbers(text: str) -> set[str]:
    """Extract digit groups so a changed date, percentage, or quantity is not ignored.

    Chuẩn hóa định dạng Việt: '1.500' == '1500', '2,5' == '2.5'."""
    return {_canon(t) for t in re.findall(r"\d+(?:[.,]\d+)*", text)}


# Từ ghép/thành ngữ chứa dấu hiệu phủ định nhưng KHÔNG phủ định mệnh đề ('không khí', 'hàng không').
_NEG_COMPOUNDS = re.compile(
    r"\b(?:hàng không|không khí|không gian|không quân|không chỉ|không những|không ngừng|"
    r"không phận|sân bay|phòng không|không gì)\b|\bkhông\s+(?=khí\b|gian\b)")


def _strip_compounds(text: str) -> str:
    return _NEG_COMPOUNDS.sub(" ", text.casefold())


def _best_sentence(claim_terms: set[str], passage: str) -> str:
    sentences = split_sentences(passage) or [passage]
    return max(sentences, key=lambda s: len(claim_terms & set(tokenize_for_retrieval(s))))


class RuleBasedFactChecker:
    def __init__(self, support_threshold: float = 0.45, refute_markers: list[str] | None = None) -> None:
        self.support_threshold = support_threshold
        self.refute_markers = set(refute_markers or [])

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        if not evidence_items:
            return VerificationResult(
                label="NOT_ENOUGH_INFO", confidence=1.0, evidence_ids=[],
                explanation="Không tìm thấy bằng chứng trong kho tài liệu hiện có.",
            )

        claim_terms = set(tokenize_for_retrieval(claim))
        best = evidence_items[0]
        evidence_terms = set(tokenize_for_retrieval(best.evidence.content))
        overlap = len(claim_terms & evidence_terms) / max(1, len(claim_terms))
        # Phủ định / số liệu chỉ so trên CÂU khớp claim nhất, không phải cả passage: một câu khác
        # trong bài chứa 'chưa/không' không được làm claim nguyên văn bị REFUTED.
        focus_sentence = _best_sentence(claim_terms, best.evidence.content)
        claim_negs = set(tokenize_for_retrieval(_strip_compounds(claim)))
        sentence_negs = set(tokenize_for_retrieval(_strip_compounds(focus_sentence)))
        negation_conflict = bool((claim_negs ^ sentence_negs) & self.refute_markers)
        claim_numbers = _numbers(claim)
        evidence_numbers = _numbers(best.evidence.content)
        # Mâu thuẫn số liệu = THAY số (claim có số vắng ở nguồn VÀ câu nguồn có số khác claim).
        # Nguồn không nhắc tới một con số của claim chỉ là thiếu thông tin, không phải bác bỏ.
        number_conflict = bool((claim_numbers - evidence_numbers) and (_numbers(focus_sentence) - claim_numbers))

        if overlap >= self.support_threshold and (negation_conflict or number_conflict):
            label = "REFUTED"
            explanation = (
                "Bằng chứng được truy xuất có số liệu không khớp với phát biểu."
                if number_conflict else
                "Bằng chứng được truy xuất có dấu hiệu phủ định hoặc mâu thuẫn với phát biểu."
            )
        elif overlap >= self.support_threshold:
            label = "SUPPORTED"
            explanation = "Bằng chứng được truy xuất có nhiều thông tin trùng khớp với phát biểu."
        else:
            label = "NOT_ENOUGH_INFO"
            explanation = "Các bằng chứng truy xuất chưa đủ liên quan để đưa ra kết luận chắc chắn."

        confidence = round(min(0.95, max(0.35, overlap)), 2)
        # NEI means the retrieved passage was insufficient to decide. It must not
        # be displayed as a decisive citation.
        evidence_ids = [] if label == "NOT_ENOUGH_INFO" else [best.evidence.passage_id]
        return VerificationResult(
            label=label, confidence=confidence, evidence_ids=evidence_ids, explanation=explanation
        )
