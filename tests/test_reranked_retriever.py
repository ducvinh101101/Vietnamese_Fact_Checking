from src.reranked_retriever import MetadataRerankedRetriever, deduplicate_evidence, filter_metadata, generate_query
from src.retriever import BM25Retriever
from src.schemas import Evidence, RetrievedEvidence


def evidence(pid, content, source_type="news", published_at="2024-01-01T00:00:00Z", score=0.7):
    return RetrievedEvidence(Evidence("d" + pid, pid, content, url="https://x/" + pid, source_type=source_type, published_at=published_at, authority_score=score), 1.0)


def test_query_filter_and_dedup_are_deterministic():
    assert generate_query("  claim   text ") == "claim text"
    items = [evidence("1", "same"), evidence("2", "same")]
    items[1] = RetrievedEvidence(items[1].evidence.__class__(**{**items[1].evidence.__dict__, "url": items[0].evidence.url}), 0.5)
    assert [item.evidence.passage_id for item in deduplicate_evidence(items)] == ["1"]
    filtered = filter_metadata([evidence("g", "a", "government"), evidence("old", "b", "news", "2020-01-01T00:00:00Z")], {"allowed_source_types": ["government"], "published_after": "2023-01-01T00:00:00Z", "published_before": None, "include_unknown_published_at": False})
    assert [item.evidence.passage_id for item in filtered] == ["g"]


def test_reranked_retriever_keeps_contract_and_filters_unknown_dates():
    base = BM25Retriever([
        Evidence("a", "a", "vaccine health guidance", url="https://a", source_type="news", published_at=None, authority_score=0.7),
        Evidence("b", "b", "vaccine health guidance official", url="https://b", source_type="government", published_at="2024-01-01T00:00:00Z", authority_score=0.95),
    ])
    retriever = MetadataRerankedRetriever(base, {"candidate_k": 10, "rerank": {"query_overlap_weight": 0.2, "authority_weight": 0.05}, "filters": {"allowed_source_types": ["government", "news"], "published_after": "2023-01-01T00:00:00Z", "published_before": None, "include_unknown_published_at": False}})
    result = retriever.search("vaccine health guidance", 3)
    assert [item.evidence.passage_id for item in result] == ["b"]
