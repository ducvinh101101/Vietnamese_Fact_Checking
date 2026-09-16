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
    assert retriever.last_status == "local_only"
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
