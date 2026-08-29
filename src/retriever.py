from rank_bm25 import BM25Okapi

from src.preprocessing import tokenize_for_retrieval
from src.schemas import Evidence, RetrievedEvidence


class BM25Retriever:
    """Baseline retriever BM25. Có thể thay thế bằng hybrid retriever sau này."""

    def __init__(self, evidence_items: list[Evidence]) -> None:
        if not evidence_items:
            raise ValueError("Cần ít nhất một evidence để tạo index")
        self.evidence_items = evidence_items
        self.index = BM25Okapi([tokenize_for_retrieval(item.content) for item in evidence_items])

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        scores = self.index.get_scores(tokenize_for_retrieval(claim))
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]
        return [
            RetrievedEvidence(evidence=self.evidence_items[index], score=float(score))
            for index, score in ranked
        ]
