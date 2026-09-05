"""Tổng hợp minh bạch verdict của nhiều claim thuộc cùng một article."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from src.schemas import Claim, Label, VerificationResult


ArticleAssessment = Literal[
    "NO_CLAIMS",
    "PARTIALLY_EVALUATED",
    "HAS_REFUTED_CLAIMS",
    "ALL_CLAIMS_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "MIXED_EVIDENCE",
]


@dataclass(frozen=True)
class ClaimAssessment:
    claim_id: str
    text: str
    label: Label | None
    confidence: float | None
    evidence_ids: list[str]


@dataclass(frozen=True)
class ArticleAggregation:
    article_id: str
    assessment: ArticleAssessment
    claims: list[ClaimAssessment]
    supported_count: int
    refuted_count: int
    not_enough_info_count: int
    unverified_count: int
    explanation: str


class ArticleAggregator:
    """Tạo nhận định cấp bài mà không thay thế verdict ở cấp claim."""

    def aggregate(
        self, claims: list[Claim], results: Mapping[str, VerificationResult]
    ) -> ArticleAggregation:
        if not claims:
            return ArticleAggregation(
                article_id="",
                assessment="NO_CLAIMS",
                claims=[],
                supported_count=0,
                refuted_count=0,
                not_enough_info_count=0,
                unverified_count=0,
                explanation="Bài viết không có claim nào để kiểm chứng.",
            )

        article_ids = {claim.article_id for claim in claims}
        if len(article_ids) != 1 or not next(iter(article_ids)).strip():
            raise ValueError("Mọi claim phải thuộc đúng một article_id không rỗng")
        claim_ids = {claim.claim_id for claim in claims}
        unknown_results = set(results).difference(claim_ids)
        if unknown_results:
            raise ValueError("results chứa claim_id không thuộc article")

        assessments: list[ClaimAssessment] = []
        counts = {"SUPPORTED": 0, "REFUTED": 0, "NOT_ENOUGH_INFO": 0}
        for claim in claims:
            result = results.get(claim.claim_id)
            if result is None:
                assessments.append(ClaimAssessment(claim.claim_id, claim.text, None, None, []))
                continue
            counts[result.label] += 1
            assessments.append(
                ClaimAssessment(
                    claim.claim_id,
                    claim.text,
                    result.label,
                    result.confidence,
                    result.evidence_ids,
                )
            )

        unverified = len(claims) - sum(counts.values())
        assessment, explanation = self._summarize(counts, unverified)
        return ArticleAggregation(
            article_id=next(iter(article_ids)),
            assessment=assessment,
            claims=assessments,
            supported_count=counts["SUPPORTED"],
            refuted_count=counts["REFUTED"],
            not_enough_info_count=counts["NOT_ENOUGH_INFO"],
            unverified_count=unverified,
            explanation=explanation,
        )

    @staticmethod
    def _summarize(
        counts: Mapping[str, int], unverified: int
    ) -> tuple[ArticleAssessment, str]:
        supported = counts["SUPPORTED"]
        refuted = counts["REFUTED"]
        not_enough_info = counts["NOT_ENOUGH_INFO"]
        evaluated = supported + refuted + not_enough_info
        if unverified:
            return (
                "PARTIALLY_EVALUATED",
                f"Đã kiểm chứng {evaluated} claim, còn {unverified} claim chưa có verdict; "
                f"trong các claim đã chấm có {refuted} claim bị bác bỏ.",
            )
        if refuted:
            return (
                "HAS_REFUTED_CLAIMS",
                f"Có {refuted} claim bị bác bỏ. Điều này không kết luận toàn bộ bài viết là giả.",
            )
        if supported and supported == evaluated:
            return (
                "ALL_CLAIMS_SUPPORTED",
                "Tất cả claim đã tách đều được evidence hiện có ủng hộ; phạm vi chỉ là các claim đã kiểm chứng.",
            )
        if not_enough_info == evaluated:
            return (
                "INSUFFICIENT_EVIDENCE",
                "Evidence hiện có chưa đủ để kết luận cho các claim đã tách.",
            )
        return (
            "MIXED_EVIDENCE",
            "Các claim đã tách có kết quả pha trộn giữa được ủng hộ và chưa đủ evidence.",
        )
