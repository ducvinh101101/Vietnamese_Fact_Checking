"""Retrieval cho bài toán kiểm tra nguồn: cửa sổ câu + BM25 tiếng Việt + dense + RRF.

Khác với ``BM25Retriever`` (baseline đã khóa, giữ nguyên):

* index trên **cửa sổ câu** cắt từ passage gốc thay vì passage 700 ký tự;
* token BM25 bỏ stopword và thêm bigram âm tiết (``src.vi_text``);
* tìm bằng **nhiều truy vấn** (``src.query_generation``) và tùy chọn dense
  encoder, gộp các bảng xếp hạng bằng Reciprocal Rank Fusion;
* ``FusedRetriever`` gộp kho cục bộ và web bằng cùng cơ chế RRF.

Điểm trả về là điểm RRF (>0, giảm dần) – chỉ dùng để xếp hạng. Quyết định
"có nguồn hay không" do cross-encoder ở ``src.source_reranker`` đảm nhận.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from math import log
from pathlib import Path
from typing import Callable, Protocol, Sequence

from src.query_generation import generate_queries
from src.schemas import Evidence, RetrievedEvidence
from src.vi_text import sentence_windows, tokenize_bm25


class SparseBM25:
    """BM25 Okapi trên inverted index – chỉ chấm các tài liệu có chung token.

    Nhanh hơn ``rank_bm25`` khi số cửa sổ lớn và trả đúng tập "có trùng từ
    nội dung", nên tài liệu chỉ trùng stopword không bao giờ xuất hiện.
    """

    def __init__(self, documents: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75) -> None:
        if not documents:
            raise ValueError("Cần ít nhất một tài liệu để tạo index")
        self.k1, self.b = k1, b
        self.lengths = [len(document) for document in documents]
        self.average_length = sum(self.lengths) / len(self.lengths) or 1.0
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for index, document in enumerate(documents):
            for token, frequency in Counter(document).items():
                self.postings[token].append((index, frequency))
        total = len(documents)
        self.idf = {
            token: log(1 + (total - len(posting) + 0.5) / (len(posting) + 0.5))
            for token, posting in self.postings.items()
        }

    def search(self, query_tokens: Sequence[str], top_n: int) -> list[tuple[int, float]]:
        scores: dict[int, float] = defaultdict(float)
        for token in set(query_tokens):
            posting = self.postings.get(token)
            if not posting:
                continue
            idf = self.idf[token]
            for index, frequency in posting:
                norm = self.k1 * (1 - self.b + self.b * self.lengths[index] / self.average_length)
                scores[index] += idf * frequency * (self.k1 + 1) / (frequency + norm)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:top_n]


class DenseEncoder(Protocol):
    def encode_queries(self, texts: list[str]): ...  # -> np.ndarray (n, d), L2-normalised
    def encode_passages(self, texts: list[str]): ...


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60, weights: Sequence[float] | None = None) -> list[tuple[str, float]]:
    """RRF: score(d) = Σ w_i / (k + rank_i(d)). Ổn định với thứ hạng hòa theo id."""
    weights = list(weights) if weights is not None else [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("Số trọng số phải bằng số bảng xếp hạng")
    fused: dict[str, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights):
        for rank, key in enumerate(ranking, start=1):
            fused[key] += weight / (k + rank)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))


def build_windows(items: Sequence[Evidence], window: int = 2, stride: int = 1, max_chars: int = 600,
                  scope: str = "passage") -> list[Evidence]:
    """Cắt văn bản thành cửa sổ câu, giữ metadata nguồn.

    ``scope="passage"``: cắt trong từng passage (cửa sổ không vượt ranh giới passage).
    ``scope="document"``: nối các passage cùng bài theo thứ tự rồi mới cắt, để
    Evidence nhiều câu nằm vắt qua ranh giới hai passage vẫn vào trọn một cửa sổ
    (trên dev ViFactCheck: gold nằm trọn trong 1 cửa sổ 86,0% → 92,8%).
    """
    if scope not in {"passage", "document"}:
        raise ValueError("scope phải là 'passage' hoặc 'document'")
    if scope == "document":
        groups: dict[str, list[Evidence]] = {}
        for item in items:
            groups.setdefault(item.document_id or item.url or item.passage_id, []).append(item)
        merged = []
        for document_id, parts in groups.items():
            parts = sorted(parts, key=lambda part: part.passage_id)
            text = " ".join(part.content.strip() for part in parts if part.content.strip())
            merged.append(replace(parts[0], passage_id=f"{document_id}-doc", content=text))
        items = merged
    windows: list[Evidence] = []
    for item in items:
        chunks = sentence_windows(item.content, window, stride, max_chars) or [item.content]
        if len(chunks) == 1 and scope == "passage":
            windows.append(item)
            continue
        for index, chunk in enumerate(chunks, start=1):
            windows.append(replace(item, passage_id=f"{item.passage_id}-w{index:02d}", content=chunk))
    return windows


class HybridSourceRetriever:
    """Multi-query BM25 (+ dense tùy chọn) trên cửa sổ câu, gộp bằng RRF."""

    def __init__(
        self,
        evidence_items: Sequence[Evidence],
        window: int = 2,
        stride: int = 1,
        max_chars: int = 600,
        candidates_per_query: int = 50,
        rrf_k: int = 60,
        dense_encoder: DenseEncoder | None = None,
        dense_cache: str | Path | None = None,
        dense_weight: float = 1.0,
        segmenter: Callable[[str], list[str]] | None = None,
        use_query_generation: bool = True,
        window_scope: str = "passage",
    ) -> None:
        if not evidence_items:
            raise ValueError("Cần ít nhất một evidence để tạo index")
        self.evidence_items = build_windows(evidence_items, window, stride, max_chars, window_scope)
        self._article_windows: dict[str, list[str]] = {}
        for item in self.evidence_items:
            self._article_windows.setdefault(item.document_id, []).append(item.content)
        self.segmenter = segmenter
        self.index = SparseBM25([tokenize_bm25(item.content, segmenter) for item in self.evidence_items])
        self.candidates_per_query = candidates_per_query
        self.rrf_k = rrf_k
        self.dense_encoder = dense_encoder
        self.dense_weight = dense_weight
        self.use_query_generation = use_query_generation
        self.embeddings = None
        if dense_encoder is not None:
            self.embeddings = self._load_or_encode(dense_cache)

    def _load_or_encode(self, cache: str | Path | None):
        import numpy as np

        if cache is not None and Path(cache).exists():
            embeddings = np.load(cache)
            if embeddings.shape[0] == len(self.evidence_items):
                return embeddings
        embeddings = self.dense_encoder.encode_passages([item.content for item in self.evidence_items])  # type: ignore[union-attr]
        if cache is not None:
            Path(cache).parent.mkdir(parents=True, exist_ok=True)
            np.save(cache, embeddings)
        return embeddings

    def rankings(self, claim: str) -> tuple[list[list[str]], list[float]]:
        queries = generate_queries(claim) if self.use_query_generation else generate_queries(claim)[:1]
        rankings: list[list[str]] = []
        weights: list[float] = []
        for query in queries:
            hits = self.index.search(tokenize_bm25(query.text, self.segmenter), self.candidates_per_query)
            if hits:
                rankings.append([str(index) for index, _ in hits])
                weights.append(1.0 if query.kind == "claim" else 0.5)
        if self.dense_encoder is not None and self.embeddings is not None:
            import numpy as np

            query_vector = self.dense_encoder.encode_queries([queries[0].text])[0]
            similarities = self.embeddings @ query_vector
            top = np.argsort(-similarities)[: self.candidates_per_query]
            rankings.append([str(int(index)) for index in top])
            weights.append(self.dense_weight)
        return rankings, weights

    def article_passages(self, document_id: str) -> list[str]:
        """Các cửa sổ câu của cùng bài, theo thứ tự trong bài."""
        return list(self._article_windows.get(document_id, []))

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        rankings, weights = self.rankings(claim)
        if not rankings:
            return []
        fused = reciprocal_rank_fusion(rankings, self.rrf_k, weights)[:top_k]
        return [RetrievedEvidence(self.evidence_items[int(key)], score) for key, score in fused]


class FusedRetriever:
    """Gộp nhiều retriever (vd. kho cục bộ + web) bằng RRF, khử trùng theo nội dung."""

    def __init__(self, retrievers: Sequence[object], weights: Sequence[float] | None = None,
                 candidates_per_retriever: int = 30, rrf_k: int = 60) -> None:
        if not retrievers:
            raise ValueError("Cần ít nhất một retriever")
        self.retrievers = list(retrievers)
        self.weights = list(weights) if weights is not None else [1.0] * len(self.retrievers)
        self.candidates_per_retriever = candidates_per_retriever
        self.rrf_k = rrf_k
        self.last_errors: list[str] = []

    def article_passages(self, document_id: str) -> list[str]:
        """Mọi đoạn của bài từ nguồn đầu tiên có bài này (kho cục bộ hoặc web)."""
        for retriever in self.retrievers:
            lookup = getattr(retriever, "article_passages", None)
            passages = lookup(document_id) if callable(lookup) else None
            if passages:
                return list(passages)
        return []

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        by_key: dict[str, Evidence] = {}
        rankings: list[list[str]] = []
        weights: list[float] = []
        self.last_errors = []
        for retriever, weight in zip(self.retrievers, self.weights):
            try:
                results = retriever.search(claim, self.candidates_per_retriever)  # type: ignore[attr-defined]
            except Exception as error:  # một nguồn lỗi không được làm hỏng nguồn còn lại
                self.last_errors.append(f"{type(retriever).__name__}: {error}")
                continue
            ranking: list[str] = []
            for item in results:
                key = " ".join(item.evidence.content.casefold().split())
                by_key.setdefault(key, item.evidence)
                if key not in ranking:
                    ranking.append(key)
            if ranking:
                rankings.append(ranking)
                weights.append(weight)
        if not rankings:
            return []
        fused = reciprocal_rank_fusion(rankings, self.rrf_k, weights)[:top_k]
        return [RetrievedEvidence(by_key[key], score) for key, score in fused]
