"""Dựng ``SourceAttributionPipeline`` từ ``configs/source_attribution.yaml``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.env_loader import load_dotenv
from src.hybrid_retriever import FusedRetriever, HybridSourceRetriever
from src.io_utils import load_evidence_jsonl
from src.source_attribution import AttributionThresholds, SourceAttributionPipeline
from src.source_reranker import CrossEncoderReranker, LexicalSourceScorer, VerifierRelevanceScorer


ROOT = Path(__file__).resolve().parents[1]


class SentenceTransformerEncoder:
    """Dense encoder (bge-m3, e5, hoặc bi-encoder nhóm tự fine-tune)."""

    def __init__(self, model: str, query_prefix: str = "", passage_prefix: str = "", batch_size: int = 32,
                 segmenter=None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError("Cần cài sentence-transformers để bật dense retrieval.") from error
        self.model = SentenceTransformer(model)
        self.query_prefix, self.passage_prefix, self.batch_size = query_prefix, passage_prefix, batch_size
        self.segment = segmenter or (lambda text: text)  # PhoBERT bi-encoder cần tách từ

    def encode_queries(self, texts: list[str]):
        return self.model.encode([self.query_prefix + self.segment(text) for text in texts], normalize_embeddings=True,
                                 batch_size=self.batch_size)

    def encode_passages(self, texts: list[str]):
        return self.model.encode([self.passage_prefix + self.segment(text) for text in texts], normalize_embeddings=True,
                                 batch_size=self.batch_size, show_progress_bar=True)


def vncorenlp_segmenter(vncorenlp_dir: str | Path):
    """Trả hàm tách từ VnCoreNLP (chuỗi đã nối "_") – dùng cho model PhoBERT."""
    from src.phobert_fact_checker import shared_vncorenlp

    segmenter = shared_vncorenlp(vncorenlp_dir)
    return lambda text: " ".join(segmenter.word_segment(text))


def _resolve(path: str) -> str:
    candidate = ROOT / path
    return str(candidate) if candidate.exists() else path


def load_config(path: str | Path = ROOT / "configs" / "source_attribution.yaml") -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def build_local_retriever(config: dict[str, Any], corpus_items=None) -> HybridSourceRetriever:
    local = config["local"]
    dense_cfg = local.get("dense") or {}
    encoder = None
    if dense_cfg.get("model"):
        segmenter = vncorenlp_segmenter(ROOT / config["verifier"]["vncorenlp_dir"]) if dense_cfg.get("segment") else None
        encoder = SentenceTransformerEncoder(_resolve(dense_cfg["model"]), dense_cfg.get("query_prefix", ""),
                                             dense_cfg.get("passage_prefix", ""), segmenter=segmenter)
    items = corpus_items if corpus_items is not None else load_evidence_jsonl(ROOT / local["corpus"])
    return HybridSourceRetriever(
        items,
        window=int(local["window_sentences"]), stride=int(local["window_stride"]),
        max_chars=int(local["window_max_chars"]), candidates_per_query=int(local["candidates_per_query"]),
        rrf_k=int(local["rrf_k"]), dense_encoder=encoder,
        dense_cache=(ROOT / dense_cfg["cache"]) if encoder is not None and dense_cfg.get("cache") else None,
        dense_weight=float(dense_cfg.get("weight", 1.0)),
        use_query_generation=bool(local.get("multi_query", False)),
    )


def build_scorer(config: dict[str, Any], verifier=None):
    reranker = config["reranker"]
    if reranker["model"] == "lexical":
        return LexicalSourceScorer()
    if reranker["model"] == "verifier":
        if verifier is None:
            verifier = build_verifier(dict(config, verifier=dict(config["verifier"], enabled=True)))
        return VerifierRelevanceScorer(verifier, float(reranker.get("lexical_blend", 0.0)))
    segmenter = vncorenlp_segmenter(ROOT / config["verifier"]["vncorenlp_dir"]) if reranker.get("segment") else None
    return CrossEncoderReranker(_resolve(reranker["model"]), int(reranker["max_length"]),
                                int(reranker["batch_size"]), segmenter=segmenter)


def build_verifier(config: dict[str, Any]):
    verifier = config["verifier"]
    if not verifier.get("enabled"):
        return None
    from src.phobert_fact_checker import PhoBERTFactChecker

    return PhoBERTFactChecker(ROOT / verifier["model_path"], ROOT / verifier["vncorenlp_dir"],
                              int(verifier["max_length"]), float(verifier.get("temperature", 1.0)))


def build_pipeline(config: dict[str, Any] | None = None, *, use_web: bool | None = None,
                   use_verifier: bool | None = None, corpus_items=None, verifier=None) -> SourceAttributionPipeline:
    """``verifier``: truyền instance PhoBERT đã nạp để dùng chung với pipeline cũ."""
    load_dotenv()  # TAVILY_API_KEY trong .env
    config = config or load_config()
    local = build_local_retriever(config, corpus_items)
    retrievers: list[object] = [local]
    weights = [1.0]
    web_cfg = config.get("web", {})
    if (web_cfg.get("enabled") if use_web is None else use_web):
        from src.web_retriever import WebRetriever

        web_config = dict(config["web_retrieval"])
        web_config["cache"] = dict(web_config["cache"], directory=str(ROOT / web_config["cache"]["directory"]))
        web = WebRetriever(web_config)
        if web.api_key:
            retrievers.append(web)
            weights.append(float(web_cfg.get("weight", 1.0)))
    retriever = FusedRetriever(retrievers, weights, candidates_per_retriever=int(config["decision"]["candidate_k"])) \
        if len(retrievers) > 1 else local
    if verifier is None and (use_verifier is None or use_verifier):
        if use_verifier or config["verifier"].get("enabled"):
            verifier = build_verifier(dict(config, verifier=dict(config["verifier"], enabled=True)))
    decision = config["decision"]
    return SourceAttributionPipeline(
        retriever, build_scorer(config, verifier), verifier, AttributionThresholds(**decision["thresholds"]),
        candidate_k=int(decision["candidate_k"]), assess_k=int(decision["assess_k"]),
        max_citations=int(decision["max_citations"]),
    )
