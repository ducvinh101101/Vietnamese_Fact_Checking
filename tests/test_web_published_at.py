"""Kiểm thử trích xuất ngày đăng (published_at) cho bằng chứng web.

Phần "mức chuẩn" của neo thời gian: web evidence phải mang ngày đăng THẬT lấy từ
trang (meta tag / JSON-LD / thẻ <time>), không chỉ retrieved_at."""

from __future__ import annotations

from src.web_retriever import _normalize_date, extract_published_at


def test_meta_article_published_time_iso():
    html = (
        '<html><head>'
        '<meta property="article:published_time" content="2023-03-13T10:30:00+07:00">'
        '<title>x</title></head><body><p>nội dung</p></body></html>'
    )
    assert extract_published_at(html) == "2023-03-13T10:30:00+07:00"


def test_jsonld_date_published():
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type":"NewsArticle","datePublished":"2026-10-01T08:00:00+07:00",'
        '"dateModified":"2026-10-02"}</script></head><body></body></html>'
    )
    assert extract_published_at(html).startswith("2026-10-01")


def test_time_tag_datetime():
    html = '<html><body><time datetime="2024-07-05">5/7</time><p>a</p></body></html>'
    assert extract_published_at(html).startswith("2024-07-05")


def test_published_wins_over_modified():
    html = (
        '<html><head>'
        '<meta property="article:modified_time" content="2026-10-02">'
        '<meta property="article:published_time" content="2023-01-01">'
        '</head><body></body></html>'
    )
    assert extract_published_at(html).startswith("2023-01-01")


def test_dmy_vietnamese_format_in_meta():
    html = '<html><head><meta name="pubdate" content="13/03/2023"></head><body></body></html>'
    assert extract_published_at(html).startswith("2023-03-13")


def test_no_date_returns_none():
    html = "<html><body><p>không có ngày tháng nào ở đây</p></body></html>"
    assert extract_published_at(html) is None


def test_normalize_rejects_implausible_year():
    assert _normalize_date("1899-01-01") is None
    assert _normalize_date("không phải ngày") is None
    assert _normalize_date("") is None
    assert _normalize_date(None) is None
