from src.retriever import BM25Retriever
from src.schemas import Evidence


def test_bm25_returns_most_relevant_evidence():
    retriever = BM25Retriever([
        Evidence("1", "p1", "Thông báo về lịch học mới."),
        Evidence("2", "p2", "Khuyến cáo sức khỏe cộng đồng."),
    ])
    result = retriever.search("lịch học", top_k=1)
    assert result[0].evidence.passage_id == "p1"
