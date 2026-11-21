from copy import deepcopy
import gzip
from pathlib import Path

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
