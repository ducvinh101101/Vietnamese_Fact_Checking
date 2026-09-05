"""Các interface ổn định tại ranh giới retrieval và verification."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.schemas import RetrievedEvidence, VerificationResult


@runtime_checkable
class Retriever(Protocol):
    """Truy xuất evidence đã xếp hạng cho một claim đã được chuẩn hóa."""

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        """Trả tối đa ``top_k`` evidence theo thứ tự điểm giảm dần."""


@runtime_checkable
class Verifier(Protocol):
    """Đưa ra verdict cho một claim và evidence do retriever cung cấp."""

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        """Trả một verdict có thể trích dẫn bằng ``evidence_ids``."""
