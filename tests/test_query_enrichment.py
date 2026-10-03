from datetime import date

from src.query_enrichment import TimeAwareRetriever, enrich_query


class _WebLikeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, claim, top_k):
        self.calls.append(("plain", claim, top_k))
        return []

    def search_time_window(self, claim, top_k, start_date, end_date, *, language=None):
        self.calls.append(("window", claim, top_k, start_date, end_date, language))
        return []


def test_enriches_relative_query_with_unambiguous_date():
    query, enriched = enrich_query("Giá xăng tăng từ chiều nay", date(2026, 10, 3))
    assert enriched
    assert query.endswith("ngày 03/10/2026")


def test_time_sensitive_web_search_uses_same_window_as_gate():
    inner = _WebLikeRetriever()
    retriever = TimeAwareRetriever(inner, as_of=date(2026, 10, 3), window_today=10)
    assert retriever.search("Giá xăng tăng từ chiều nay", 5) == []
    assert inner.calls == [(
        "window", "Giá xăng tăng từ chiều nay ngày 03/10/2026", 5,
        date(2026, 9, 23), date(2026, 10, 3), "vi",
    )]


def test_implicit_current_office_query_uses_fresh_news_window():
    inner = _WebLikeRetriever()
    retriever = TimeAwareRetriever(inner, as_of=date(2026, 10, 3), window_current=365)
    assert retriever.search("Donald Trump là tổng thống Mỹ", 3) == []
    assert inner.calls == [(
        "window", "Donald Trump là tổng thống Mỹ ngày 03/10/2026", 3,
        date(2025, 10, 3), date(2026, 10, 3), "vi",
    )]


def test_non_time_sensitive_query_keeps_general_web_search():
    inner = _WebLikeRetriever()
    retriever = TimeAwareRetriever(inner, as_of=date(2026, 10, 3))
    assert retriever.search("Thủ đô của Việt Nam là Hà Nội", 3) == []
    assert inner.calls == [("plain", "Thủ đô của Việt Nam là Hà Nội", 3)]
