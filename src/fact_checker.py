"""Verifier có fallback xác định được để demo không phụ thuộc API/LLM.

Lớp này sẽ được thay bằng verifier PhoBERT/XLM-R đã fine-tune.
"""

import re

from src.preprocessing import tokenize_for_retrieval
from src.schemas import RetrievedEvidence, VerificationResult


def _numbers(text: str) -> set[str]:
    """Extract digit groups so a changed date, percentage, or quantity is not ignored."""
    return set(re.findall(r"\d+(?:[.,]\d+)?", text))


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
        negation_conflict = bool((claim_terms ^ evidence_terms) & self.refute_markers)
        claim_numbers = _numbers(claim)
        evidence_numbers = _numbers(best.evidence.content)
        number_conflict = bool(claim_numbers and evidence_numbers and not claim_numbers.issubset(evidence_numbers))

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
