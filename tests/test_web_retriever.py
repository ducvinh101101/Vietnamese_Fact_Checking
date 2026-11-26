from copy import deepcopy
import gzip
from pathlib import Path

import pytest
import yaml

from src.web_retriever import WebRetriever, allowed_url, assert_public_dns, decode_html_response, extract_passages


def config(tmp_path):
    loaded = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs/web_retrieval.yaml").read_text(encoding="utf-8"))
    loaded = deepcopy(loaded)
    loaded["enabled"] = True
    loaded["cache"]["directory"] = str(tmp_path / "cache")
    return loaded


def test_web_retriever_filters_allowlist_and_records_required_metadata(tmp_path):
    def provider(payload, key, timeout):
        assert key == "secret-not-logged"
        assert payload["include_domains"] == ["baochinhphu.vn", "vnexpress.net", "www.who.int"]
        return {"results": [
            {"url": "https://evil.example/claim", "score": 0.99},
            {"url": "https://vnexpress.net/test", "score": 0.8, "title": "Search title"},
        ]}

    def fetch(url, timeout):
        assert url == "https://vnexpress.net/test"
        return url, "<html><title>Trang nguồn</title><article><p>" + "Nội dung đã được nguồn công bố. " * 12 + "</p></article></html>"

    results = WebRetriever(
        config(tmp_path), api_key="secret-not-logged", provider_request=provider,
        page_fetcher=fetch, robots_fetcher=lambda *_: "User-agent: *\nAllow: /",
    ).search("claim", 3)
    assert results
    assert all(item.evidence.url == "https://vnexpress.net/test" for item in results)
    assert all(item.evidence.domain == "vnexpress.net" for item in results)
    assert all(item.evidence.title == "Trang nguồn" for item in results)
    assert all(item.evidence.retrieved_at for item in results)
    assert all(item.evidence.source_type == "news" for item in results)
    assert all(item.evidence.authority_score == 0.7 for item in results)


def test_web_retriever_falls_back_without_key_or_enablement(tmp_path):
    disabled = config(tmp_path)
    disabled["enabled"] = False
    retriever = WebRetriever(disabled, api_key="key")
    assert retriever.search("claim") == []
    assert retriever.last_status == "disabled"
    enabled = WebRetriever(config(tmp_path), api_key=None)
    assert enabled.search("claim") == []
    assert enabled.last_status == "missing_api_key"


def test_usage_budget_is_persisted_without_claim_or_page_content(tmp_path):
    configured = config(tmp_path)
    configured["limits"]["monthly_credit_budget"] = 1
    retriever = WebRetriever(
        configured,
        api_key="key",
        provider_request=lambda *args: {"results": []},
    )
    assert retriever.search("claim one") == []
    assert retriever.last_status == "no_eligible_passages"
    assert retriever.search("claim two") == []
    assert retriever.last_status == "budget_exhausted"
    ledger = (tmp_path / "cache" / "usage.json").read_text(encoding="utf-8")
    assert "claim" not in ledger and "key" not in ledger and "content" not in ledger


def test_usage_budget_is_counted_per_api_key(tmp_path):
    """Đổi TAVILY_API_KEY → hạn mức tính lại từ 0; key cũ vẫn bị chặn. Sổ không chứa key."""
    import json

    configured = config(tmp_path)
    configured["limits"]["monthly_credit_budget"] = 1
    cache = tmp_path / "cache"
    cache.mkdir()
    # Sổ định dạng cũ (không theo key) – coi như của key cũ, không chặn key mới.
    month = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m")
    (cache / "usage.json").write_text(json.dumps({"month": month, "requests": 5, "recent": []}), encoding="utf-8")

    def make(key):
        return WebRetriever(configured, api_key=key, provider_request=lambda *args: {"results": []})

    first = make("tvly-first-secret")
    first.search("claim one")
    assert first.last_status == "no_eligible_passages"
    first.search("claim two")
    assert first.last_status == "budget_exhausted"
    second = make("tvly-second-secret")
    second.search("claim three")
    assert second.last_status == "no_eligible_passages"
    ledger = (cache / "usage.json").read_text(encoding="utf-8")
    assert "secret" not in ledger and "tvly" not in ledger


def test_tls_context_trusts_certifi_roots_and_skips_weak_dhe():
    """sggp.org.vn: root GlobalSign R6 không có trong kho Windows nhưng có trong certifi.
    moh.gov.vn: khóa DH quá yếu → không đề nghị DHE (vẫn kiểm tra chứng chỉ + tên miền)."""
    import ssl

    from src.web_retriever import tls_context

    context = tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert any("GlobalSign Root CA - R6" in str(ca.get("subject")) for ca in context.get_ca_certs())
    assert not [c["name"] for c in context.get_ciphers() if c["name"].startswith("DHE-")]


def test_url_dns_and_passage_guards():
    hosts = {"vnexpress.net"}
    assert allowed_url("https://vnexpress.net/path", hosts)
    assert not allowed_url("https://vnexpress.net.evil.example/path", hosts)
    assert not allowed_url("https://vnexpress.net@evil.example/path", hosts)
    try:
        assert_public_dns("vnexpress.net", resolver=lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 0))])
    except RuntimeError as error:
        assert "private" in str(error)
    else:
        raise AssertionError("Private IP must be rejected")
    title, passages = extract_passages("<title>T</title><script>ignore()</script><p>" + "Đoạn đủ dài. " * 20 + "</p>", 120, 250, 3)
    assert title == "T"
    assert passages and all("ignore" not in passage for passage in passages)


def test_html_decoder_handles_gzip_and_meta_charset_before_bad_header():
    raw = '<html><head><meta charset="utf-8"><title>Tiêu đề tiếng Việt</title></head></html>'.encode("utf-8")
    decoded = decode_html_response(gzip.compress(raw), "gzip", "iso-8859-1")
    assert "Tiêu đề tiếng Việt" in decoded


def test_extract_passages_removes_duplicate_page_text():
    repeated = "Đoạn nội dung trùng lặp cần chỉ xuất hiện một lần trong evidence. " * 4
    _, passages = extract_passages(
        f"<article><div><p>{repeated}</p></div><p>{repeated}</p></article>", 120, 800, 3,
    )
    assert passages == [repeated.strip()]


def test_web_retriever_respects_robots_txt(tmp_path):
    fetched = False

    def fetch(url, timeout):
        nonlocal fetched
        fetched = True
        return url, "<p>" + "Nội dung không được phép tải. " * 10 + "</p>"

    retriever = WebRetriever(
        config(tmp_path), api_key="key",
        provider_request=lambda *_: {"results": [{"url": "https://vnexpress.net/private"}]},
        page_fetcher=fetch,
        robots_fetcher=lambda *_: "User-agent: *\nDisallow: /private",
    )
    assert retriever.search("claim") == []
    assert not fetched
    assert retriever.last_status == "no_eligible_passages"


def test_extract_passages_selects_relevant_passages_not_page_header():
    header = "<p>" + "Thời tiết hôm nay nắng đẹp, mời bạn đọc xem thêm các bài viết khác trên chuyên trang. " * 2 + "</p>"
    filler = "".join(f"<p>{'Đoạn văn số ' + str(i) + ' nói về chủ đề thể thao và giải trí cuối tuần này. ' * 3}</p>" for i in range(3))
    relevant = "<p>" + "Bộ Y tế công bố cả nước ghi nhận 120 ca mắc mới trong ngày 15/3/2023 tại nhiều địa phương. " * 2 + "</p>"
    _, passages = extract_passages(f"<article>{header}{filler}{relevant}</article>", 80, 800, 1,
                                   query="Bộ Y tế ghi nhận 120 ca mắc mới ngày 15/3/2023")
    assert passages and "120 ca mắc mới" in passages[0]


def test_web_retriever_reads_multiple_pages_and_ranks_globally(tmp_path):
    pages = {
        "https://vnexpress.net/a": "<p>" + "Tin tức chung chung về thể thao và văn hóa trong tuần qua tại nhiều nơi. " * 3 + "</p>",
        "https://vnexpress.net/b": "<p>" + "Giá xăng RON 95 giảm 500 đồng mỗi lít theo điều hành của liên Bộ. " * 3 + "</p>",
    }

    configured = config(tmp_path)
    configured["extraction"]["max_pages"] = 5
    results = WebRetriever(
        configured, api_key="key",
        provider_request=lambda *_: {"results": [{"url": url, "score": 0.9} for url in pages]},
        page_fetcher=lambda url, timeout: (url, pages[url]),
        robots_fetcher=lambda *_: "User-agent: *\nAllow: /",
    ).search("Giá xăng RON 95 giảm 500 đồng", 2)
    assert {item.evidence.url for item in results} == set(pages)
    assert results[0].evidence.url == "https://vnexpress.net/b"


def test_web_retriever_interleaves_results_of_multiple_queries(tmp_path):
    configured = config(tmp_path)
    configured["limits"]["requests_per_claim"] = 2
    configured["extraction"]["max_pages"] = 2
    calls = []

    def provider(payload, key, timeout):
        calls.append(payload["query"])
        prefix = "a" if len(calls) == 1 else "b"
        return {"results": [{"url": f"https://vnexpress.net/{prefix}{i}"} for i in range(3)]}

    fetched = []

    def fetch(url, timeout):
        fetched.append(url)
        return url, "<p>" + "Bộ Y tế ghi nhận 120 ca mắc mới tại Hà Nội trong ngày hôm qua theo báo cáo. " * 3 + "</p>"

    WebRetriever(configured, api_key="key", provider_request=provider, page_fetcher=fetch,
                 robots_fetcher=lambda *_: "User-agent: *\nAllow: /").search("Theo Bộ Y tế, Hà Nội có 120 ca mắc mới", 3)
    assert len(calls) == 2
    assert fetched == ["https://vnexpress.net/a0", "https://vnexpress.net/b0"]


def test_failure_statuses_distinguish_unreachable_pages_from_empty_results(tmp_path):
    from src.web_retriever import WEB_FAILURE_MESSAGES, WEB_RETRYABLE_STATUSES, WebRetrievalError

    def provider(payload, key, timeout):
        return {"results": [{"url": "https://vnexpress.net/a"}, {"url": "https://vnexpress.net/b"}]}

    def timeout_fetch(url, timeout):
        raise WebRetrievalError("Hết thời gian")

    unreachable = WebRetriever(config(tmp_path), api_key="key", provider_request=provider,
                               page_fetcher=timeout_fetch, robots_fetcher=lambda *_: "")
    assert unreachable.search("claim") == []
    assert unreachable.last_status == "pages_unreachable"
    assert "pages_unreachable" in WEB_FAILURE_MESSAGES and "pages_unreachable" in WEB_RETRYABLE_STATUSES

    def broken_provider(payload, key, timeout):
        raise WebRetrievalError("down")

    down = WebRetriever(config(tmp_path), api_key="key", provider_request=broken_provider)
    assert down.search("claim") == []
    assert down.last_status == "local_only"

    empty = WebRetriever(config(tmp_path), api_key="key", provider_request=lambda *_: {"results": []})
    assert empty.search("claim") == []
    assert empty.last_status == "no_eligible_passages"
    assert "no_eligible_passages" not in WEB_FAILURE_MESSAGES


def test_per_minute_limit_is_not_retryable(tmp_path):
    from src.web_retriever import WEB_FAILURE_MESSAGES, WEB_RETRYABLE_STATUSES

    configured = config(tmp_path)
    configured["limits"]["requests_per_minute"] = 1
    configured["limits"]["requests_per_claim"] = 1
    retriever = WebRetriever(configured, api_key="key", provider_request=lambda *_: {"results": []})
    retriever.search("claim one")
    assert retriever.search("claim two") == []
    assert retriever.last_status == "rate_limited"
    assert "rate_limited" in WEB_FAILURE_MESSAGES and "rate_limited" not in WEB_RETRYABLE_STATUSES


def test_robots_download_failure_counts_as_unreachable_not_blocked(tmp_path):
    from src.web_retriever import WebRetrievalError

    def robots_down(url, timeout):
        raise WebRetrievalError("timeout")

    retriever = WebRetriever(
        config(tmp_path), api_key="key",
        provider_request=lambda *_: {"results": [{"url": "https://vnexpress.net/a"}]},
        page_fetcher=lambda url, timeout: (url, ""), robots_fetcher=robots_down,
    )
    assert retriever.search("claim") == []
    assert retriever.last_status == "pages_unreachable"


def test_robots_decoder_handles_undeclared_gzip_and_bogus_charset():
    from src.web_retriever import decode_robots_response

    text = "User-agent: *\nDisallow: /admin\n"
    assert decode_robots_response(gzip.compress(text.encode()), None) == text  # gzip không khai báo
    assert decode_robots_response(gzip.compress(text.encode()), "gzip") == text
    assert decode_robots_response(text.encode(), None) == text


def test_last_trace_records_search_results_and_page_outcomes(tmp_path):
    """Vết từng lần search để phân tích lỗi không tốn thêm lượt Tavily."""
    from src.web_retriever import WebRetrievalError

    configured = config(tmp_path)
    configured["limits"]["requests_per_claim"] = 1
    configured["extraction"]["max_pages"] = 1
    good = "<article><p>" + "Giá xăng RON 95 giảm 500 đồng mỗi lít theo điều hành của liên Bộ. " * 3 + "</p></article>"

    def fetch(url, timeout):
        if url.endswith("/down"):
            raise WebRetrievalError("Không tải được trang nguồn web") from ConnectionError("ssl")
        return url, good

    retriever = WebRetriever(
        configured, api_key="key",
        provider_request=lambda *_: {"results": [
            {"url": "https://evil.example/x", "title": "Ngoài", "score": 0.9},
            {"url": "https://vnexpress.net/private/a", "title": "Chặn", "score": 0.8},
            {"url": "https://vnexpress.net/down", "score": 0.7},
            {"url": "https://vnexpress.net/ok", "title": "Bài", "score": 0.6},
            {"url": "https://vnexpress.net/late", "score": 0.5},
        ]},
        page_fetcher=fetch, robots_fetcher=lambda *_: "User-agent: *\nDisallow: /private",
    )
    assert retriever.search("Giá xăng RON 95 giảm 500 đồng", 3)
    trace = retriever.last_trace
    assert trace["queries"] == ["Giá xăng RON 95 giảm 500 đồng"]
    assert trace["provider_error"] is None
    assert [r["url"] for r in trace["search_results"]][:2] == ["https://evil.example/x", "https://vnexpress.net/private/a"]
    assert trace["search_results"][0] == {"query_index": 0, "rank": 0, "url": "https://evil.example/x",
                                          "title": "Ngoài", "score": 0.9}
    outcomes = {page["url"]: page for page in trace["pages"]}
    assert outcomes["https://evil.example/x"]["outcome"] == "not_allowed"
    assert outcomes["https://vnexpress.net/private/a"]["outcome"] == "robots_blocked"
    assert outcomes["https://vnexpress.net/down"]["outcome"] == "fetch_failed"
    assert "ConnectionError: ssl" in outcomes["https://vnexpress.net/down"]["error"]
    assert outcomes["https://vnexpress.net/ok"]["outcome"] == "used"
    assert 0 < outcomes["https://vnexpress.net/ok"]["max_relevance"] <= 1
    assert outcomes["https://vnexpress.net/late"]["outcome"] == "not_read"  # quá max_pages


def test_last_trace_records_provider_failure(tmp_path):
    from src.web_retriever import WebRetrievalError

    def broken(payload, key, timeout):
        raise WebRetrievalError("down")

    retriever = WebRetriever(config(tmp_path), api_key="key", provider_request=broken)
    retriever.search("claim")
    assert retriever.last_trace["provider_error"] == "down"
    assert retriever.last_trace["pages"] == []


def test_robots_txt_is_fetched_once_per_host(tmp_path):
    calls = []

    def robots(url, timeout):
        calls.append(url)
        return "User-agent: *\nAllow: /"

    retriever = WebRetriever(
        config(tmp_path), api_key="key",
        provider_request=lambda *_: {"results": [{"url": f"https://vnexpress.net/{i}"} for i in range(3)]},
        page_fetcher=lambda url, timeout: (url, "<article><p>" + "Nội dung bài báo nguồn. " * 12 + "</p></article>"),
        robots_fetcher=robots,
    )
    assert retriever.search("claim", 5)
    assert len(calls) == 1


def test_fetch_page_wraps_incomplete_read(monkeypatch, tmp_path):
    """Máy chủ ngắt giữa chừng (IncompleteRead) = trang lỗi, không làm hỏng cả lượt tìm web."""
    from http.client import IncompleteRead

    import src.web_retriever as wr

    class _Response:
        headers = type("H", (), {"get_content_type": lambda self: "text/html", "get": lambda self, k, d=None: None,
                                 "get_content_charset": lambda self: "utf-8"})()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, amount):
            raise IncompleteRead(b"partial")

    monkeypatch.setattr(wr, "_opener", lambda: type("O", (), {"open": lambda self, req, timeout: _Response()})())
    monkeypatch.setattr(wr, "assert_public_dns", lambda host: None)
    web = wr.WebRetriever(config(tmp_path), api_key="test")
    with pytest.raises(wr.WebRetrievalError):
        web._fetch_page("https://vnexpress.net/a-1.html", 1.0)


def test_query_overrides_apply_per_query_and_only_safe_keys(tmp_path):
    payloads = []

    def provider(payload, key, timeout):
        payloads.append(dict(payload))
        return {"results": []}

    cfg = config(tmp_path)
    cfg["limits"]["requests_per_claim"] = 2
    cfg["provider"]["query_overrides"] = [{}, {"time_range": "month", "search_depth": "advanced"}]
    WebRetriever(cfg, api_key="k", provider_request=provider, page_fetcher=lambda *a: ("", ""),
                 robots_fetcher=lambda *_: "").search("Ngày 20/11, Ba Lan theo dõi 11 mục tiêu xâm nhập không phận", 3)
    assert len(payloads) == 2
    assert "time_range" not in payloads[0]
    assert payloads[1]["time_range"] == "month"
    assert payloads[1]["search_depth"] == cfg["provider"]["search_depth"]  # không cho đổi sang advanced (2 credit)
