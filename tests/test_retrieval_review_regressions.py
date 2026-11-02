from datetime import date
from pathlib import Path
from email.message import Message

import pytest
import yaml

import src.web_retriever as web
from src.schemas import Evidence, RetrievedEvidence
from src.topical_rerank import TopicalRerankRetriever, RelevanceFilteredRetriever, eligible
from src.query_enrichment import window_start


@pytest.fixture
def config(tmp_path):
    cfg = yaml.safe_load(Path("configs/web_retrieval.yaml").read_text(encoding="utf-8"))
    cfg["enabled"] = True
    cfg["cache"]["directory"] = str(tmp_path)
    return cfg


@pytest.mark.parametrize("claim,passage", [
    ("Sông băng tan chảy khiến cuộc sống trở nên khó khăn hơn", "Bệnh nhân hậu phẫu gặp khó khăn hơn."),
    ("Thủ khoa toán Trần Minh Đức", "Thủ khoa toán Trần Minh Hoàng đạt điểm cao."),
    ("Phát hiện thiên hà xa nhất vũ trụ", "Giá xăng bán lẻ giảm mạnh."),
])
def test_irrelevant_and_wrong_person_abstain(claim, passage):
    assert not eligible(claim, passage)


def test_conflicting_number_can_be_refuting_evidence():
    assert eligible("Giá xăng tăng 500 đồng", "Giá xăng chỉ tăng 300 đồng một lít.")


def test_this_month_does_not_accept_news_from_previous_month():
    assert window_start("Lãi suất tháng này giảm", date(2026, 11, 2), 365) == date(2026, 11, 1)


def test_upstream_rank_not_overridden_by_long_keyword_stuffing():
    claim = "Bộ Y tế công bố lịch tiêm chủng cho trẻ em"
    a = RetrievedEvidence(Evidence("a", "a", "Bộ Y tế công bố lịch tiêm chủng mới.", url="https://x/a"), 10)
    b = RetrievedEvidence(Evidence("b", "b", claim + " và nhiều thông tin liên quan", url="https://x/b"), 5)
    class Inner:
        def search(self, *args):
            return [a, b]
    assert TopicalRerankRetriever(Inner()).search(claim)[0].evidence.passage_id == "a"


def test_local_application_abstains_when_no_relevant_candidates():
    class Inner:
        def search(self, *args):
            return [RetrievedEvidence(Evidence("a", "a", "Bệnh nhân gặp khó khăn hơn"), 5)]
    assert RelevanceFilteredRetriever(Inner()).search("Sông băng tan chảy khiến cuộc sống trở nên khó khăn hơn") == []


def test_sidebar_removed_and_article_preferred():
    noise = "Gọi điện chuyển khoản 700 triệu đồng. " * 8
    body = "Giá vàng SJC hôm nay giảm theo thông báo. " * 8
    html = f'<div>{noise}</div><article><div class="sidebar">{noise}</div><p>{body}</p></article>'
    _, passages = web.extract_passages(html, 120, 800, 3)
    assert passages == [body.strip()]


def test_robots_multiple_charset_header(config, monkeypatch):
    class Response:
        headers = Message()
        headers["Content-Type"] = "text/plain; charset=utf-8,gbk"
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return b"User-agent: *\nDisallow: /private"
    class Opener:
        def open(self, *args, **kwargs): return Response()
    monkeypatch.setattr(web, "assert_public_dns", lambda *_: None)
    monkeypatch.setattr(web, "build_opener", lambda *_: Opener())
    retriever = web.WebRetriever(config, api_key="key")
    assert retriever._robots_allow("https://laodong.vn/news", 1)
    assert not retriever._robots_allow("https://laodong.vn/private", 1)


def test_fallback_filters_stale_and_uses_provider_date(config):
    calls = []
    def provider(payload, *args):
        calls.append(payload.copy())
        return {"results": [{"url": "https://vnexpress.net/a", "published_date":
                             "2023-01-01" if len(calls) < 3 else "2026-11-02"}]}
    retriever = web.WebRetriever(
        config, api_key="key", provider_request=provider,
        page_fetcher=lambda url, _: (url, "<article><p>" + "Giá vàng hôm nay giảm. " * 10 + "</p></article>"),
        robots_fetcher=lambda *_: "User-agent: *\nAllow: /",
    )
    items = retriever.search_time_window("Giá vàng hôm nay ngày 02/11/2026", 2, date(2026, 10, 23), date(2026, 11, 2))
    assert len(calls) == 3
    assert calls[1]["query"] == "Giá vàng hôm nay"
    assert calls[2]["topic"] == "general"
    assert items and items[0].evidence.published_at_source == "tavily"
    assert retriever.last_attempts[-1]["count"] > 0


def test_page_date_wins_over_provider_and_budget_is_bounded(config):
    calls = []
    def provider(*args):
        calls.append(1)
        return {"results": [{"url": "https://vnexpress.net/a", "published_date": "2026-11-02"}]}
    retriever = web.WebRetriever(
        config, api_key="key", provider_request=provider,
        page_fetcher=lambda url, _: (url, '<meta property="article:published_time" content="2020-01-01"><p>' + "Tin cũ. " * 25 + "</p>"),
        robots_fetcher=lambda *_: "User-agent: *\nAllow: /",
    )
    assert retriever.search_time_window("Giá vàng hôm nay", 2, date(2026, 10, 23), date(2026, 11, 2)) == []
    assert len(calls) == config["limits"]["requests_per_claim"]
