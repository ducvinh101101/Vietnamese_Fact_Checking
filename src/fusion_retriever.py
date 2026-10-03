"""Hợp nhất bằng chứng local + web bằng Reciprocal Rank Fusion (RRF).

BM25 (local) và Tavily (web) cho điểm trên hai thang khác nhau, không cộng trực
tiếp được. RRF chỉ dùng THỨ HẠNG trong mỗi danh sách nên không phụ thuộc thang:
mỗi ứng viên được cộng ``1 / (rrf_k + rank)`` từ mỗi nguồn nó xuất hiện. Nhờ vậy
một passage xếp cao ở cả hai nguồn được ưu tiên, và web không lấn át local chỉ
vì điểm thô lớn hơn.

Nếu web trả rỗng (bị tắt, thiếu API key, hoặc lỗi mạng) thì fusion = local, nên
pipeline vẫn chạy bình thường — đúng chính sách fail_to: local_only.
"""

from __future__ import annotations

import re

from src.contracts import Retriever
from src.schemas import RetrievedEvidence

_SPACE = re.compile(r"\s+")


def _key(item: RetrievedEvidence) -> tuple[str, str]:
    """Khóa khử trùng: URL + nội dung đã chuẩn hóa khoảng trắng."""
    content = _SPACE.sub(" ", item.evidence.content).strip().casefold()
    return (item.evidence.url.strip().casefold(), content)


class FusionRetriever:
    """Trộn hai retriever theo RRF và trả top-k đã xếp hạng lại.

    ``local`` và ``web`` đều phải tuân contract ``search(claim, top_k)``. ``web``
    có thể là None hoặc trả rỗng; khi đó kết quả chính là của local.
    """

    def __init__(self, local: Retriever, web: Retriever | None = None,
                 rrf_k: int = 60, candidate_k: int = 10) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k phải lớn hơn 0")
        if candidate_k < 1:
            raise ValueError("candidate_k phải lớn hơn 0")
        self.local = local
        self.web = web
        self.rrf_k = rrf_k
        self.candidate_k = candidate_k

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        local_hits = self.local.search(claim, self.candidate_k)
        web_hits = self.web.search(claim, self.candidate_k) if self.web is not None else []

        fused: dict[tuple[str, str], float] = {}
        chosen: dict[tuple[str, str], RetrievedEvidence] = {}
        for hits in (local_hits, web_hits):
            for rank, item in enumerate(hits, start=1):
                key = _key(item)
                fused[key] = fused.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
                # Giữ bản xuất hiện đầu tiên (local trước web) cho mỗi passage trùng.
                chosen.setdefault(key, item)

        ranked = sorted(
            (RetrievedEvidence(chosen[key].evidence, score) for key, score in fused.items()),
            key=lambda item: (-item.score, item.evidence.passage_id),
        )
        return ranked[:top_k]
