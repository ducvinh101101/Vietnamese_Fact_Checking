"""Bộ test mở rộng cho retrieval WEB (W3-05) và chuỗi hybrid.

Hoàn toàn offline: provider Tavily, tải trang, robots.txt và DNS đều được tiêm bản
giả. Lỗi phát hiện được ghi bằng ``xfail(strict=True)``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import socket
import zlib

import pytest
import yaml

from src.fusion_retriever import FusionRetriever
from src.query_enrichment import TimeAwareRetriever, enrich_query
from src.schemas import Evidence, RetrievedEvidence
from src.temporal_gate import TemporalGateRetriever
from src.topical_rerank import TopicalRerankRetriever
from src.web_retriever import (
    UsageLedger,
    WebRetrievalError,
    WebRetriever,
    allowed_url,
    assert_public_dns,
    canonical_url,
    decode_html_response,
    extract_passages,
    extract_published_at,
)

ROOT = Path(__file__).resolve().parents[1]
ALLOW_ALL_ROBOTS = "User-agent: *\nAllow: /"
LONG = "Nội dung kiểm chứng chi tiết từ trang nguồn chính thống. " * 6


def web_config(tmp_path: Path) -> dict:
    loaded = deepcopy(yaml.safe_load((ROOT / "configs/web_retrieval.yaml").read_text(encoding="utf-8")))
    loaded["enabled"] = True
    loaded["cache"]["directory"] = str(tmp_path / "cache")
    return loaded


def page(body: str = LONG, title: str = "Tiêu đề", head: str = "") -> str:
    return f"<html><head><title>{title}</title>{head}</head><body><article><p>{body}</p></article></body></html>"


def make(tmp_path, results, fetch=None, robots=ALLOW_ALL_ROBOTS, config=None, **kw) -> WebRetriever:
    return WebRetriever(
        config or web_config(tmp_path), api_key="key",
        provider_request=results if callable(results) else (lambda *_: {"results": results}),
        page_fetcher=fetch or (lambda url, timeout: (url, page())),
        robots_fetcher=robots if callable(robots) else (lambda *_: robots),
        **kw,
    )


def resolver_for(*ips):
    return lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips]


# ======================================================================= URL guards

HOSTS = {"vnexpress.net", "www.who.int"}


class TestAllowedUrl:
    @pytest.mark.parametrize("url", [
        "https://vnexpress.net/a",
        "https://VNEXPRESS.NET/a",
        "https://vnexpress.net:443/a",
        "https://vnexpress.net/a?x=1#frag",
        "https://www.who.int/vi",
    ])
    def test_accepts(self, url):
        assert allowed_url(url, HOSTS)

    @pytest.mark.parametrize("url", [
        "http://vnexpress.net/a",                       # không HTTPS
        "ftp://vnexpress.net/a",
        "https://vnexpress.net:8443/a",                 # cổng lạ
        "https://user:pw@vnexpress.net/a",              # credentials
        "https://user@vnexpress.net/a",
        "https://evil.example/?u=vnexpress.net",
        "https://sub.vnexpress.net/a",                  # subdomain không được wildcard
        "https://vnexpress.net.evil.example/a",
        "https://who.int/a",                            # chỉ www.who.int được duyệt
        "https://vnexpress.net/a b",                    # khoảng trắng
        "https://vnexpress.net/a\x00",                  # ký tự điều khiển
        "https://vnexpress.net\\@evil.example/",        # backslash
        "https://vnexpress.net:abc/a",                  # port không hợp lệ -> ValueError
        "https://[::1]/a",
        "",
        "vnexpress.net/a",
    ])
    def test_rejects(self, url):
        assert not allowed_url(url, HOSTS)


class TestPublicDns:
    def test_accepts_public_ipv4_and_ipv6(self):
        assert_public_dns("vnexpress.net", resolver=resolver_for("111.65.248.132", "2606:4700::6810:84e5"))

    @pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.1",
                                    "169.254.169.254", "::1", "fc00::1", "0.0.0.0", "100.64.0.1"])
    def test_rejects_non_global(self, ip):
        with pytest.raises(WebRetrievalError):
            assert_public_dns("vnexpress.net", resolver=resolver_for(ip))

    def test_rejects_mixed_public_and_private_answers(self):
        with pytest.raises(WebRetrievalError):
            assert_public_dns("vnexpress.net", resolver=resolver_for("8.8.8.8", "127.0.0.1"))

    def test_resolution_failure_and_empty_answer_are_controlled_errors(self):
        def failing(*args, **kwargs):
            raise socket.gaierror("no such host")

        with pytest.raises(WebRetrievalError):
            assert_public_dns("vnexpress.net", resolver=failing)
        with pytest.raises(WebRetrievalError):
            assert_public_dns("vnexpress.net", resolver=lambda *a, **k: [])


class TestCanonicalUrl:
    @pytest.mark.parametrize("raw, expected", [
        ("HTTPS://VnExpress.NET/Path?q=1#frag", "https://vnexpress.net/Path?q=1"),
        ("https://vnexpress.net", "https://vnexpress.net/"),
        ("https://vnexpress.net/a#", "https://vnexpress.net/a"),
    ])
    def test_canonicalisation(self, raw, expected):
        assert canonical_url(raw) == expected


# ================================================================== HTML decoding

class TestDecodeHtml:
    TEXT = '<html><head><meta charset="utf-8"></head><body>Tiếng Việt có dấu</body></html>'

    def test_identity(self):
        assert "Tiếng Việt" in decode_html_response(self.TEXT.encode(), None, None)

    def test_deflate(self):
        assert "Tiếng Việt" in decode_html_response(zlib.compress(self.TEXT.encode()), "deflate", None)

    def test_x_gzip_with_spacing_and_case(self):
        assert "Tiếng Việt" in decode_html_response(gzip.compress(self.TEXT.encode()), " X-GZIP ", None)

    @pytest.mark.parametrize("encoding", ["br", "zstd", "compress"])
    def test_unsupported_encoding_is_controlled(self, encoding):
        with pytest.raises(WebRetrievalError):
            decode_html_response(b"...", encoding, None)

    def test_corrupt_gzip_is_controlled(self):
        with pytest.raises(WebRetrievalError):
            decode_html_response(b"not gzip at all", "gzip", None)

    def test_corrupt_deflate_is_controlled(self):
        with pytest.raises(WebRetrievalError):
            decode_html_response(b"not deflate", "deflate", None)

    def test_meta_charset_wins_over_header(self):
        raw = '<meta charset="windows-1258"><p>Việt</p>'.encode("windows-1258", errors="ignore")
        decoded = decode_html_response(raw, None, "utf-8")
        assert "<p>" in decoded

    def test_unknown_meta_charset_falls_back_to_utf8(self):
        raw = '<meta charset="no-such-charset"><p>Hà Nội</p>'.encode("utf-8")
        assert "Hà Nội" in decode_html_response(raw, None, None)

    def test_header_charset_used_when_not_utf8(self):
        raw = "<p>café</p>".encode("latin-1")
        assert "café" in decode_html_response(raw, None, "latin-1")


# ============================================================= Passage extraction

class TestExtractPassages:
    def test_skips_boilerplate_regions(self):
        html = (
            "<html><head><title>  Tiêu   đề  </title><style>.x{}</style></head><body>"
            f"<header>{'Menu điều hướng trang chủ. ' * 10}</header>"
            f"<nav>{'Liên kết nav. ' * 20}</nav>"
            f"<article><p>{LONG}</p></article>"
            f"<aside>{'Quảng cáo bên lề. ' * 20}</aside>"
            f"<footer>{'Bản quyền footer. ' * 20}</footer>"
            "<noscript>bật javascript</noscript><svg><text>svg</text></svg>"
            "</body></html>"
        )
        title, passages = extract_passages(html, 120, 800, 5)
        assert title == "Tiêu đề"
        joined = " ".join(passages)
        for word in ("Menu", "nav", "Quảng cáo", "footer", "javascript", "svg", ".x{}"):
            assert word not in joined

    def test_minimum_length_filter(self):
        _, passages = extract_passages("<p>Quá ngắn.</p><p>" + LONG + "</p>", 120, 800, 5)
        assert passages == [LONG.strip()]

    def test_long_paragraph_split_into_chunks_within_limit(self):
        text = "".join(f"Câu kiểm chứng số {i} có độ dài vừa phải để chia đoạn. " for i in range(40))
        _, passages = extract_passages(f"<p>{text}</p>", 50, 300, 50)
        assert len(passages) > 1
        assert all(len(p) <= 300 for p in passages)
        assert " ".join(passages) == text.strip()  # không mất câu nào khi chia

    def test_identical_chunks_are_deduplicated(self):
        sentence = "Đây là một câu kiểm chứng có độ dài vừa phải để chia đoạn. "
        _, passages = extract_passages(f"<p>{sentence * 40}</p>", 50, 300, 50)
        assert len(passages) == 1

    def test_single_sentence_longer_than_max_is_truncated(self):
        _, passages = extract_passages("<p>" + "a" * 2000 + "</p>", 10, 500, 3)
        assert passages == ["a" * 500]

    def test_max_passages_per_page(self):
        paragraphs = "".join(f"<p>Đoạn số {i}. {LONG}</p>" for i in range(10))
        _, passages = extract_passages(paragraphs, 120, 800, 3)
        assert len(passages) == 3
        assert passages[0].startswith("Đoạn số 0")

    def test_html_entities_decoded(self):
        _, passages = extract_passages("<p>Bộ Y&nbsp;tế &amp; WHO &#7853;. " + LONG + "</p>", 50, 800, 3)
        assert "Bộ Y tế & WHO" in passages[0].replace("\xa0", " ")

    def test_malformed_html_does_not_crash(self):
        title, passages = extract_passages("<p><b>" + LONG + "<div><p>unclosed", 50, 800, 3)
        assert title == "" and passages

    def test_empty_page(self):
        assert extract_passages("", 50, 800, 3) == ("", [])


# ============================================================ published_at

class TestPublishedAt:
    @pytest.mark.parametrize("head, expected_prefix", [
        ('<meta property="article:published_time" content="2026-10-01T08:00:00+07:00">', "2026-10-01T08:00:00+07:00"),
        ('<meta name="pubdate" content="2026-09-30">', "2026-09-30"),
        ('<meta itemprop="datePublished" content="30/09/2026">', "2026-09-30"),
        ('<meta name="date" content="2026/09/29 10:00">', "2026-09-29"),
    ])
    def test_meta_variants(self, head, expected_prefix):
        assert extract_published_at(page(head=head)).startswith(expected_prefix)

    def test_published_beats_modified_regardless_of_order(self):
        head = ('<meta property="article:modified_time" content="2026-10-05T00:00:00Z">'
                '<meta property="article:published_time" content="2026-10-01T00:00:00Z">')
        assert extract_published_at(page(head=head)).startswith("2026-10-01")

    def test_ldjson_nested_graph(self):
        blob = json.dumps({"@graph": [{"@type": "WebPage"}, {"@type": "NewsArticle", "datePublished": "2026-08-15T07:00:00+07:00"}]})
        head = f'<script type="application/ld+json">{blob}</script>'
        assert extract_published_at(page(head=head)).startswith("2026-08-15")

    def test_ldjson_invalid_json_uses_regex_fallback(self):
        head = '<script type="application/ld+json">{"datePublished": "2026-07-01T00:00:00Z",}{bad</script>'
        assert extract_published_at(page(head=head)).startswith("2026-07-01")

    @pytest.mark.parametrize("value", ["1999-01-01", "2999-01-01", "not a date", "", "31/02/2026"])
    def test_implausible_or_invalid_dates_rejected(self, value):
        assert extract_published_at(page(head=f'<meta name="pubdate" content="{value}">')) is None

    def test_no_signal_returns_none(self):
        assert extract_published_at(page()) is None

    def test_does_not_leak_ldjson_into_passages(self):
        blob = json.dumps({"datePublished": "2026-08-15", "description": "SECRET_LD_TEXT"})
        _, passages = extract_passages(page(head=f'<script type="application/ld+json">{blob}</script>'), 50, 800, 3)
        assert all("SECRET_LD_TEXT" not in p for p in passages)


# =================================================================== Usage ledger

class TestUsageLedger:
    def test_per_minute_limit(self, tmp_path):
        ledger = UsageLedger(tmp_path, per_minute=2, monthly_budget=100)
        ledger.reserve()
        ledger.reserve()
        with pytest.raises(WebRetrievalError, match="mỗi phút"):
            ledger.reserve()

    def test_old_timestamps_expire_from_minute_window(self, tmp_path):
        ledger = UsageLedger(tmp_path, per_minute=1, monthly_budget=100)
        old = datetime.now(timezone.utc).timestamp() - 120
        ledger.path.write_text(json.dumps({"month": datetime.now(timezone.utc).strftime("%Y-%m"),
                                           "requests": 5, "recent": [old]}), encoding="utf-8")
        ledger.reserve()
        state = json.loads(ledger.path.read_text(encoding="utf-8"))
        assert state["requests"] == 6 and len(state["recent"]) == 1

    def test_new_month_resets_budget(self, tmp_path):
        ledger = UsageLedger(tmp_path, per_minute=10, monthly_budget=1)
        ledger.path.write_text(json.dumps({"month": "2000-01", "requests": 999, "recent": []}), encoding="utf-8")
        ledger.reserve()
        assert json.loads(ledger.path.read_text(encoding="utf-8"))["requests"] == 1

    def test_lock_released_after_success_and_failure(self, tmp_path):
        ledger = UsageLedger(tmp_path, per_minute=1, monthly_budget=100)
        ledger.reserve()
        assert not ledger.lock_path.exists()
        with pytest.raises(WebRetrievalError):
            ledger.reserve()
        assert not ledger.lock_path.exists()

    @pytest.mark.slow
    def test_stale_lock_times_out_with_controlled_error(self, tmp_path):
        ledger = UsageLedger(tmp_path, per_minute=10, monthly_budget=100)
        ledger.lock_path.write_text("", encoding="utf-8")
        with pytest.raises(WebRetrievalError, match="khóa"):
            ledger.reserve()

    @pytest.mark.xfail(strict=True, raises=json.JSONDecodeError,
                       reason="BUG: usage.json hỏng (ghi dở, sửa tay) -> JSONDecodeError thô, không phải WebRetrievalError")
    def test_corrupt_ledger_is_controlled_error(self, tmp_path):
        ledger = UsageLedger(tmp_path, per_minute=10, monthly_budget=100)
        ledger.path.write_text("{corrupt", encoding="utf-8")
        with pytest.raises(WebRetrievalError):
            ledger.reserve()


# ================================================================ WebRetriever.search

class TestWebRetrieverSearch:
    def test_bad_top_k_and_date_window(self, tmp_path):
        retriever = make(tmp_path, [])
        with pytest.raises(ValueError):
            retriever.search("claim", 0)
        with pytest.raises(ValueError):
            retriever.search_time_window("claim", 3, date(2026, 10, 2), date(2026, 10, 1))

    def test_payload_never_requests_raw_content_or_answer(self, tmp_path):
        seen = {}
        queries = []

        def provider(payload, key, timeout):
            seen.update(payload)
            queries.append(payload["query"])
            assert timeout == 15.0
            return {"results": []}

        make(tmp_path, provider).search("Giá xăng hôm nay", 3)
        assert queries[0] == "Giá xăng hôm nay"
        assert seen["include_raw_content"] is False and seen["include_answer"] is False
        assert seen["auto_parameters"] is False
        assert seen["max_results"] == 15
        assert "api_key" not in seen and "key" not in json.dumps(seen).lower().replace("auto_parameters", "")

    def test_government_source_metadata(self, tmp_path):
        result = make(tmp_path, [{"url": "https://baochinhphu.vn/a", "score": 0.9}]).search("c", 3)
        assert result
        evidence = result[0].evidence
        assert evidence.source_type == "government" and evidence.authority_score == 0.95
        assert evidence.domain == "baochinhphu.vn"
        assert evidence.passage_id.startswith("web-") and evidence.passage_id.endswith("-p01")
        assert evidence.article_id == evidence.document_id

    def test_document_id_is_stable_hash_of_final_url(self, tmp_path):
        a = make(tmp_path, [{"url": "https://vnexpress.net/x"}]).search("c", 1)
        b = make(tmp_path, [{"url": "https://VNEXPRESS.net/x#f"}]).search("c", 1)
        assert a[0].evidence.document_id == b[0].evidence.document_id

    def test_published_at_extracted_from_page(self, tmp_path):
        html = page(head='<meta property="article:published_time" content="2026-10-30T09:00:00+07:00">')
        result = make(tmp_path, [{"url": "https://vnexpress.net/x"}], fetch=lambda u, t: (u, html)).search("c", 1)
        assert result[0].evidence.published_at.startswith("2026-10-30")

    def test_title_falls_back_to_provider_title(self, tmp_path):
        html = f"<article><p>{LONG}</p></article>"
        result = make(tmp_path, [{"url": "https://vnexpress.net/x", "title": "Tiêu đề provider"}],
                      fetch=lambda u, t: (u, html)).search("c", 1)
        assert result[0].evidence.title == "Tiêu đề provider"

    def test_fetch_error_on_one_page_does_not_block_others(self, tmp_path):
        def fetch(url, timeout):
            if "broken" in url:
                raise WebRetrievalError("timeout")
            return url, page()

        result = make(tmp_path, [{"url": "https://vnexpress.net/broken"}, {"url": "https://tuoitre.vn/ok"}],
                      fetch=fetch).search("c", 3)
        assert {item.evidence.domain for item in result} == {"tuoitre.vn"}
        assert make(tmp_path, [], fetch=fetch).last_status == "not_run"

    def test_provider_failure_is_local_only(self, tmp_path):
        def provider(*_):
            raise WebRetrievalError("down")

        retriever = make(tmp_path, provider)
        assert retriever.search("c") == [] and retriever.last_status == "local_only"

    def test_page_without_eligible_passages(self, tmp_path):
        retriever = make(tmp_path, [{"url": "https://vnexpress.net/x"}], fetch=lambda u, t: (u, "<p>ngắn</p>"))
        assert retriever.search("c") == [] and retriever.last_status == "no_eligible_passages"

    @pytest.mark.parametrize("bad", [None, 42, "https://vnexpress.net/x", {"no_url": 1}, {"url": 123}])
    def test_malformed_result_entries_are_skipped(self, tmp_path, bad):
        retriever = make(tmp_path, [bad, {"url": "https://tuoitre.vn/ok"}])
        assert [item.evidence.domain for item in retriever.search("c", 1)] == ["tuoitre.vn"]

    def test_missing_results_key_is_no_eligible(self, tmp_path):
        retriever = make(tmp_path, lambda *_: {})
        assert retriever.search("c") == [] and retriever.last_status == "no_eligible_passages"

    def test_robots_failure_policy(self, tmp_path):
        def robots_down(*_):
            raise WebRetrievalError("robots down")

        deny = make(tmp_path, [{"url": "https://vnexpress.net/x"}], robots=robots_down)
        assert deny.search("c") == []
        allow_config = web_config(tmp_path)
        allow_config["source_policy"]["robots_failure"] = "allow"
        allow = make(tmp_path, [{"url": "https://vnexpress.net/x"}], robots=robots_down, config=allow_config)
        assert allow.search("c")

    def test_obey_robots_false_never_fetches_robots(self, tmp_path):
        config = web_config(tmp_path)
        config["source_policy"]["obey_robots_txt"] = False

        def robots(*_):
            raise AssertionError("robots must not be fetched")

        assert make(tmp_path, [{"url": "https://vnexpress.net/x"}], robots=robots, config=config).search("c")

    def test_robots_user_agent_specific_disallow(self, tmp_path):
        robots = "User-agent: VietnameseFactChecking\nDisallow: /\n\nUser-agent: *\nAllow: /"
        assert make(tmp_path, [{"url": "https://vnexpress.net/x"}], robots=robots).search("c") == []

    def test_redirect_to_already_seen_article_is_deduplicated(self, tmp_path):
        def fetch(url, timeout):
            return "https://vnexpress.net/canonical", page()

        result = make(tmp_path, [{"url": "https://vnexpress.net/canonical"}, {"url": "https://vnexpress.net/amp"}],
                      fetch=fetch).search("c", 10)
        assert {item.evidence.url for item in result} == {"https://vnexpress.net/canonical"}
        assert len({item.evidence.passage_id for item in result}) == len(result)

    def test_redirect_to_other_allowlisted_host_uses_final_host_metadata(self, tmp_path):
        result = make(tmp_path, [{"url": "https://vnexpress.net/x"}],
                      fetch=lambda u, t: ("https://moh.gov.vn/y", page())).search("c", 1)
        assert result[0].evidence.domain == "moh.gov.vn"
        assert result[0].evidence.source_type == "government"

    def test_top_k_respected_and_passage_ids_unique(self, tmp_path):
        paragraphs = "".join(f"<p>Đoạn {i}. {LONG}</p>" for i in range(5))
        urls = [{"url": f"https://vnexpress.net/{i}"} for i in range(4)]
        result = make(tmp_path, urls, fetch=lambda u, t: (u, f"<article>{paragraphs}</article>")).search("c", 5)
        assert len(result) == 5
        assert len({item.evidence.passage_id for item in result}) == 5
        assert [item.evidence.passage_id.endswith("-p01") for item in result] == [True] * 4 + [False]

    def test_no_secret_or_claim_in_ledger_after_many_calls(self, tmp_path):
        retriever = make(tmp_path, [{"url": "https://vnexpress.net/x"}])
        for _ in range(3):
            retriever.search("Bí mật claim nhạy cảm", 2)
        text = (tmp_path / "cache" / "usage.json").read_text(encoding="utf-8")
        assert "Bí mật" not in text and "key" not in text and "vnexpress" not in text

    @pytest.mark.xfail(strict=True, reason=(
        "BUG: thứ tự primary (p01) + remaining làm score TĂNG lại khi top_k > số bài. "
        "FactCheckingPipeline sẽ raise 'Retriever phải sắp evidence theo score giảm dần' "
        "nếu dùng WebRetriever trực tiếp (hybrid qua RRF nên không bị)."))
    def test_scores_non_increasing_for_retriever_contract(self, tmp_path):
        paragraphs = "".join(f"<p>Đoạn {i}. {LONG}</p>" for i in range(3))
        result = make(
            tmp_path,
            [{"url": "https://vnexpress.net/a", "score": 0.8}, {"url": "https://tuoitre.vn/b", "score": 0.7}],
            fetch=lambda u, t: (u, f"<article>{paragraphs}</article>"),
        ).search("c", 4)
        scores = [item.score for item in result]
        assert scores == sorted(scores, reverse=True), scores

    @pytest.mark.xfail(strict=True, raises=TypeError,
                       reason="BUG: provider trả \"score\": null -> float(None) TypeError làm sập cả search")
    def test_null_provider_score_does_not_crash(self, tmp_path):
        assert make(tmp_path, [{"url": "https://vnexpress.net/x", "score": None}]).search("c", 1)

    def test_non_object_provider_response_is_controlled(self, tmp_path):
        retriever = make(tmp_path, lambda *_: [])
        assert retriever.search("c") == []
        assert retriever.last_status == "invalid_provider_response"


# ======================================================== TimeAware + hybrid chain


class FakeWeb:
    """Giả lập WebRetriever có search_time_window, ghi lại lời gọi."""

    def __init__(self, items: list[RetrievedEvidence]) -> None:
        self.items = items
        self.calls: list[tuple] = []

    def search(self, claim, top_k=3):
        self.calls.append(("search", claim, top_k))
        return self.items[:top_k]

    def search_time_window(self, claim, top_k, start, end, *, language=None):
        self.calls.append(("window", claim, top_k, start, end, language))
        return self.items[:top_k]


class Static:
    def __init__(self, items):
        self.items = items

    def search(self, claim, top_k=3):
        return self.items[:top_k]


def web_item(pid, content, published_at, url, score=1.0):
    return RetrievedEvidence(Evidence(f"web-{pid}", f"web-{pid}-p01", content, url=url,
                                      published_at=published_at, source_type="news", authority_score=0.7), score)


def local_item(pid, content, published_at="2023-03-15T00:00:00Z", url=None, score=5.0):
    return RetrievedEvidence(Evidence(pid, pid, content, url=url or f"https://baochinhphu.vn/{pid}",
                                      published_at=published_at, source_type="government", authority_score=0.95), score)


AS_OF = date(2026, 11, 1)


class TestTimeAwareRetriever:
    @pytest.mark.parametrize("claim", ["Hà Nội là thủ đô Việt Nam",
                                       "Cựu tổng thống Obama thăm Việt Nam năm 2016"])
    def test_non_time_sensitive_uses_plain_search(self, claim):
        web = FakeWeb([])
        TimeAwareRetriever(web, as_of=AS_OF).search(claim, 3)
        assert web.calls == [("search", claim, 3)]

    def test_disabled_never_enriches_or_windows(self):
        web = FakeWeb([])
        layer = TimeAwareRetriever(web, as_of=AS_OF, enabled=False)
        layer.search("Giá xăng hôm nay tăng", 3)
        assert web.calls == [("search", "Giá xăng hôm nay tăng", 3)]
        assert layer.last_enriched_query is None

    def test_inner_without_window_receives_enriched_query(self):
        inner = Static([])
        inner.search = lambda claim, top_k=3, _calls=[]: _calls.append(claim) or []  # type: ignore[assignment]
        layer = TimeAwareRetriever(inner, as_of=AS_OF)
        layer.search("Giá xăng hôm nay tăng", 3)
        assert layer.last_enriched_query == "Giá xăng hôm nay tăng ngày 01/11/2026"

    def test_negative_window_rejected(self):
        with pytest.raises(ValueError):
            TimeAwareRetriever(FakeWeb([]), window_today=-1)

    def test_enrich_query_is_idempotent_for_enriched_output(self):
        query, enriched = enrich_query("Giá xăng hôm nay", AS_OF)
        again, enriched_again = enrich_query(query, AS_OF)
        assert enriched and not enriched_again and again == query


class TestHybridChain:
    """Chuỗi giống system_builder: Fusion(local, TimeAware(web)) -> TemporalGate -> TopicalRerank."""

    def chain(self, local_items, web):
        layer = TimeAwareRetriever(web, as_of=AS_OF, window_today=10, window_current=365) if web else None
        fusion = FusionRetriever(Static(local_items), layer, candidate_k=20)
        gate = TemporalGateRetriever(fusion, as_of=AS_OF, window_today=10, window_current=365, candidate_k=20)
        return TopicalRerankRetriever(gate, candidate_k=20), fusion, gate

    def test_fresh_web_evidence_wins_for_today_claim_and_stale_local_dropped(self):
        web = FakeWeb([web_item("a", "Giá xăng RON 95 tăng 500 đồng/lít từ chiều nay theo kỳ điều hành",
                                "2026-10-31T15:00:00+07:00", "https://vnexpress.net/xang")])
        retriever, _, gate = self.chain([local_item("old", "Giá xăng tăng 500 đồng")], web)
        result = retriever.search("Giá xăng tăng chiều nay", 5)
        assert [item.evidence.passage_id for item in result] == ["web-a-p01"]
        assert gate.last_dropped_stale == 1
        assert web.calls[0][0] == "window" and web.calls[0][3] == AS_OF - timedelta(days=10)

    def test_historical_claim_keeps_local_evidence(self):
        retriever, _, gate = self.chain([local_item("l1", "Lễ kỷ niệm 70 năm Điện ảnh cách mạng Việt Nam")], FakeWeb([]))
        result = retriever.search("Lễ kỷ niệm 70 năm Điện ảnh cách mạng Việt Nam năm 2023", 3)
        assert [item.evidence.passage_id for item in result] == ["l1"]
        assert not gate.last_applied

    def test_web_outage_degrades_to_local_with_error_recorded(self):
        class Down(FakeWeb):
            def search(self, *a, **k):
                raise ConnectionError("network unreachable")

            search_time_window = search

        retriever, fusion, _ = self.chain([local_item("l1", "Hà Nội là thủ đô")], Down([]))
        result = retriever.search("Hà Nội là thủ đô của Việt Nam", 3)
        assert [item.evidence.passage_id for item in result] == ["l1"]
        assert "ConnectionError" in fusion.last_web_error

    def test_all_stale_returns_empty_for_time_sensitive_claim(self):
        web = FakeWeb([web_item("old", "Giá xăng tăng", "2025-01-01T00:00:00Z", "https://vnexpress.net/o")])
        retriever, _, _ = self.chain([local_item("l", "Giá xăng tăng")], web)
        assert retriever.search("Giá xăng hôm nay tăng", 5) == []

    def test_output_contract_distinct_urls_and_descending_scores(self):
        web = FakeWeb([web_item(f"w{i}", f"Giá xăng hôm nay tăng {i} đồng", "2026-10-31T00:00:00Z",
                                f"https://vnexpress.net/{i % 2}") for i in range(6)])
        retriever, _, _ = self.chain([], web)
        result = retriever.search("Giá xăng hôm nay tăng", 5)
        urls = [item.evidence.url for item in result]
        assert len(urls) == len(set(urls)) == 2
        assert all(result[i].score > result[i + 1].score for i in range(len(result) - 1))


@pytest.mark.slow
def test_build_system_hybrid_with_fake_web_runs_full_pipeline_contract():
    """Hybrid thật (corpus v2 + MetadataRerank + verifier rule-based) với web giả."""
    from src.system_builder import SystemOptions, build_system

    web = FakeWeb([web_item("x", "Giá xăng RON 95 tăng 500 đồng/lít từ 15h chiều nay theo kỳ điều hành của liên bộ.",
                            "2026-10-31T15:00:00+07:00", "https://vnexpress.net/xang")])
    system = build_system(SystemOptions(mode="hybrid", engine="rule_based", as_of=AS_OF), web_retriever=web)
    response = system.check("Giá xăng RON 95 tăng 500 đồng chiều nay")
    origins = {record["origin"] for record in response["retrieval"]["evidence"]}
    assert "web" in origins
    assert response["diagnostics"]["web_error"] is None
    assert response["diagnostics"]["temporal_gate"]["recency_class"] == "today"
