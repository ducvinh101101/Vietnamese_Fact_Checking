"""Luồng article → claim → verdict từng claim → tổng hợp cấp bài.

Module này chỉ điều phối các component của Vinh qua interface ``run(claim)``.
Retriever, verifier và UI vẫn là dependency bên ngoài; không có logic web hoặc
content-risk nào được suy diễn ở đây.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from src.article_aggregation import ArticleAggregation, ArticleAggregator
from src.claim_decomposer import ClaimDecomposer
from src.schemas import Article, Claim, RetrievedEvidence, VerificationResult


class ClaimRunner(Protocol):
    """Ranh giới với pipeline claim-level đã có của dự án."""

    def run(self, claim: str) -> tuple[VerificationResult, list[RetrievedEvidence]]:
        """Kiểm chứng một claim và trả evidence đã dùng để trích dẫn."""


@dataclass(frozen=True)
class ClaimRun:
    claim: Claim
    result: VerificationResult
    retrieved_evidence: list[RetrievedEvidence]


@dataclass(frozen=True)
class ArticleRun:
    article_id: str
    claim_runs: list[ClaimRun]
    aggregation: ArticleAggregation


class ArticleFactCheckingPipeline:
    """Điều phối kiểm chứng cấp bài mà không gán nhãn giả/thật cho toàn bài."""

    def __init__(
        self,
        claim_runner: ClaimRunner,
        decomposer: ClaimDecomposer | None = None,
        aggregator: ArticleAggregator | None = None,
    ) -> None:
        self.claim_runner = claim_runner
        self.decomposer = decomposer or ClaimDecomposer()
        self.aggregator = aggregator or ArticleAggregator()

    def run(self, article: Article) -> ArticleRun:
        claims = self.decomposer.decompose(article)
        runs: list[ClaimRun] = []
        results: dict[str, VerificationResult] = {}
        for claim in claims:
            result, retrieved = self.claim_runner.run(claim.text)
            retrieved_ids = {item.evidence.passage_id for item in retrieved}
            if not set(result.evidence_ids).issubset(retrieved_ids):
                raise RuntimeError("Citation claim-level không thuộc evidence đã truy xuất")
            runs.append(ClaimRun(claim, result, retrieved))
            results[claim.claim_id] = result
        aggregation = self.aggregator.aggregate(claims, results)
        if not claims:
            aggregation = replace(aggregation, article_id=article.article_id)
        return ArticleRun(
            article_id=article.article_id,
            claim_runs=runs,
            aggregation=aggregation,
        )
