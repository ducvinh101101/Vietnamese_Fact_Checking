"""W3-08 metadata-aware, deterministic reranking without verifier changes."""

from __future__ import annotations

from datetime import datetime
import re

from src.retriever import BM25Retriever
from src.schemas import RetrievedEvidence


SPACE = re.compile(r"\s+")


def generate_query(claim: str) -> str:
    """Normalize the user claim into the single reproducible retrieval query."""
    query = SPACE.sub(" ", claim).strip()
    if not query:
        raise ValueError("claim không được rỗng")
    return query


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def filter_metadata(items: list[RetrievedEvidence], filters: dict[str, object]) -> list[RetrievedEvidence]:
    allowed = set(filters.get("allowed_source_types", []))
    after = _timestamp(filters.get("published_after"))  # type: ignore[arg-type]
    before = _timestamp(filters.get("published_before"))  # type: ignore[arg-type]
    include_unknown = bool(filters.get("include_unknown_published_at", True))
    kept: list[RetrievedEvidence] = []
    for item in items:
        evidence = item.evidence
        if allowed and evidence.source_type not in allowed:
            continue
        published = _timestamp(evidence.published_at)
        if published is None and not include_unknown:
            continue
        if published is not None and after is not None and published < after:
            continue
        if published is not None and before is not None and published > before:
            continue
        kept.append(item)
    return kept


def deduplicate_evidence(items: list[RetrievedEvidence]) -> list[RetrievedEvidence]:
    seen: set[tuple[str, str]] = set()
    result: list[RetrievedEvidence] = []
    for item in items:
        key = (item.evidence.url, SPACE.sub(" ", item.evidence.content).strip().casefold())
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


class MetadataRerankedRetriever:
    """BM25 candidates → source/time filter → lexical/authority rerank → dedup."""

    def __init__(self, base: BM25Retriever, config: dict[str, object]) -> None:
        self.base = base
        self.candidate_k = int(config["candidate_k"])
        self.rerank = config["rerank"]  # type: ignore[assignment]
        self.filters = config["filters"]  # type: ignore[assignment]
        if self.candidate_k < 1:
            raise ValueError("candidate_k phải lớn hơn 0")

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        query = generate_query(claim)
        candidates = self.base.search(query, top_k=min(self.candidate_k, len(self.base.evidence_items)))
        filtered = filter_metadata(candidates, self.filters)
        query_terms = set(query.casefold().split())
        overlap_weight = float(self.rerank["query_overlap_weight"])
        authority_weight = float(self.rerank["authority_weight"])

        def score(item: RetrievedEvidence) -> tuple[float, str]:
            terms = set(item.evidence.content.casefold().split())
            overlap = len(query_terms & terms) / max(1, len(query_terms))
            authority = item.evidence.authority_score or 0.0
            return (item.score + overlap_weight * overlap + authority_weight * authority, item.evidence.passage_id)

        reranked = [RetrievedEvidence(item.evidence, score(item)[0]) for item in filtered]
        reranked.sort(key=lambda item: (-item.score, item.evidence.passage_id))
        return deduplicate_evidence(reranked)[:top_k]
