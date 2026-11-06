from copy import deepcopy
from http.client import IncompleteRead
from threading import Barrier
from datetime import date
import json
from pathlib import Path

import pytest
import yaml

from src.news_discovery import NewsDiscovery, parse_feed
from src.web_retriever import WebRetriever, _normalize_date


CLAIM = 'Giá vàng thế giới tăng mạnh, thoát đáy một năm, lên sát 4.000 USD nhờ giá dầu giảm 8%.'
URL = 'https://vnexpress.net/gold.html'
FEED = 'https://vnexpress.net/rss/kinh-doanh.rss'


def rss(url=URL, text=CLAIM, stamp='Tue, 03 Nov 2026 07:30:34 +0700'):
    return f'<rss><channel><item><title>{text}</title><link>{url}</link><description>Thông tin từ báo.</description><pubDate>{stamp}</pubDate></item></channel></rss>'


def test_parse_rss_and_atom_and_reject_xml_entities():
    entry = parse_feed(rss())[0]
    assert entry['url'] == URL and entry['title'] == CLAIM
    atom = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Title</title><link href="https://vnexpress.net/a"/><summary>Summary</summary><published>2026-11-03</published></entry></feed>'
    assert parse_feed(atom)[0]['url'] == 'https://vnexpress.net/a'
    with pytest.raises(ValueError):
        parse_feed('<!DOCTYPE rss [<!ENTITY x "x">]><rss/>')


def test_rfc822_date_is_understood():
    assert _normalize_date('Tue, 03 Nov 2026 07:30:34 +0700') == '2026-11-03T07:30:34+07:00'
    assert _normalize_date('garbage') is None


def test_feed_discovery_cache_relevance_dates_and_allowed_urls():
    calls = []
    def fetch(url, timeout):
        calls.append(url)
        entries = rss() + ''
        entries = entries.replace('</channel>',
            '<item><title>Bóng đá đội tuyển</title><link>https://vnexpress.net/noise</link></item>'
            f'<item><title>{CLAIM}</title><link>https://evil.example/a</link></item>'
            f'<item><title>{CLAIM}</title><link>https://vnexpress.net/old</link><pubDate>2020-01-01</pubDate></item></channel>')
        return url, entries
    discovery = NewsDiscovery({'feeds': [FEED], 'ttl_seconds': 300}, fetch,
                               lambda url: url.startswith('https://vnexpress.net/'), _normalize_date)
    for _ in range(2):
        results = discovery.search(CLAIM, (date(2026, 11, 1), date(2026, 11, 3)))
        assert [r['url'] for r in results] == [URL]
    assert calls == [FEED] and discovery.last_feeds[0]['cached']


def test_feed_errors_do_not_discard_other_publishers():
    def fetch(url, timeout):
        if url.endswith('/bad'):
            raise RuntimeError('Timeout RSS')
        return url, rss()
    discovery = NewsDiscovery({'feeds': ['https://vnexpress.net/bad', FEED]}, fetch,
                               lambda u: u.startswith('https://vnexpress.net/'), _normalize_date)
    assert discovery.search(CLAIM)
    assert discovery.last_feeds[0]['error'] == 'Timeout RSS'


def test_feed_redirect_outside_allowlist_is_rejected():
    discovery = NewsDiscovery({'feeds': [FEED]}, lambda *_: ('https://evil.example/', rss()),
                               lambda u: u.startswith('https://vnexpress.net/'), _normalize_date)
    assert not discovery.search(CLAIM)
    assert 'allowlist' in discovery.last_feeds[0]['error']


@pytest.fixture
def config(tmp_path):
    cfg = yaml.safe_load(Path('configs/web_retrieval.yaml').read_text(encoding='utf-8'))
    cfg['enabled'] = True
    cfg['cache']['directory'] = str(tmp_path)
    cfg['discovery']['feeds'] = [FEED]
    return cfg


def test_finds_new_article_without_search_key_or_hint_url(config):
    web = WebRetriever(config, api_key='',
        provider_request=lambda *_: pytest.fail('RSS should resolve this without Tavily'),
        feed_fetcher=lambda url, _: (url, rss()),
        page_fetcher=lambda url, _: (url, f'<meta property="article:published_time" content="2026-11-03"><article><p>{CLAIM} {CLAIM}</p></article>'),
        robots_fetcher=lambda *_: '')
    items = web.search(CLAIM, 5)
    assert items and items[0].evidence.url == URL
    assert web.last_attempts[0]['stage'] == 'publisher_rss'
    assert items[0].evidence.published_at_source == 'page'


def test_feed_snippet_never_becomes_evidence_when_page_is_irrelevant(config):
    web = WebRetriever(config, api_key='', feed_fetcher=lambda url, _: (url, rss()),
        page_fetcher=lambda url, _: (url, '<article><p>Thông tin bóng đá không liên quan. ' * 8 + '</p></article>'),
        robots_fetcher=lambda *_: '')
    # Page extraction is not filtered by topic for general search, but the
    # matching RSS snippet must never be copied into evidence content.
    items = web.search(CLAIM)
    assert all(CLAIM not in item.evidence.content for item in items)


def test_original_page_date_overrides_feed_date(config):
    web = WebRetriever(config, api_key='', feed_fetcher=lambda url, _: (url, rss()),
        page_fetcher=lambda url, _: (url, f'<meta property="article:published_time" content="2020-01-01"><p>{CLAIM} {CLAIM}</p>'),
        robots_fetcher=lambda *_: '')
    assert not web._search(CLAIM, 5, date_window=(date(2026, 11, 1), date(2026, 11, 3)),
                           results_override=parse_feed(rss()))
    assert 'ngoài cửa sổ' in web.last_candidates[0]['reason']


def test_general_fallback_recovers_index_missing_date_and_uses_original_page(config):
    config = deepcopy(config)
    config['discovery']['enabled'] = False
    calls = []
    def provider(payload, *_):
        calls.append(payload)
        return {'results': [] if payload['topic'] == 'news' else [{'url': URL}]}
    web = WebRetriever(config, api_key='key', provider_request=provider,
        page_fetcher=lambda url, _: (url, f'<meta property="article:published_time" content="2026-11-03"><p>{CLAIM} {CLAIM}</p>'),
        robots_fetcher=lambda *_: '')
    assert web.search_time_window(CLAIM, 5, date(2026, 11, 1), date(2026, 11, 3), language='vi')
    assert len(calls) == 2
    assert calls[1]['topic'] == 'general' and 'filter_by_published_date' not in calls[1]
    assert 'filter_by_language' not in calls[1]


def test_benchmark_never_passes_expected_url_as_source_hint():
    source = Path('scripts/evaluate_web_discovery.py').read_text(encoding='utf-8')
    assert "layer.search(case['claim'], 5)" in source
    assert 'source_urls=' not in source


def test_sitemap_candidates_are_locators_and_never_dates_or_evidence():
    xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://congly.vn/quoc-hoi-thao-luan-4-du-an-luat.html</loc><lastmod>2026-11-06</lastmod></url></urlset>'
    entry = parse_feed(xml)[0]
    assert entry['published_date'] == '' and entry['_date_source'] == 'publisher_sitemap'
    discovery = NewsDiscovery({'sitemap_templates': ['https://congly.vn/sitemap-{date}.xml']},
                               lambda u, _: (u, xml), lambda u: u.startswith('https://congly.vn/'), _normalize_date)
    items = discovery.search('Quốc hội thảo luận 4 dự án luật về sở hữu trí tuệ và điện lực',
                              sitemap_days=(date(2026, 11, 3),), include_feeds=False)
    assert items and items[0]['url'].endswith('du-an-luat.html')


def test_parallel_fetches_and_single_robots_request(config):
    config['discovery']['enabled'] = False
    config['fetching']['workers'] = 2
    barrier = Barrier(2, timeout=3)
    robots_calls = []
    def fetch(url, _):
        barrier.wait()  # Fails if page fetches are accidentally sequential.
        return url, '<p>' + CLAIM * 3 + '</p>'
    web = WebRetriever(config, api_key='key', page_fetcher=fetch,
                       robots_fetcher=lambda u, _: robots_calls.append(u) or '')
    items = web._search(CLAIM, 2, results_override=[{'url': URL}, {'url': URL + '?b=2'}])
    assert len(items) == 2 and len(robots_calls) == 1


def test_broken_transfer_on_one_source_does_not_lose_other_sources(config):
    config['discovery']['enabled'] = False
    def fetch(url, _):
        if url.endswith('/broken'):
            raise IncompleteRead(b'partial', 100)
        return url, '<p>' + CLAIM * 3 + '</p>'
    web = WebRetriever(config, api_key='key', page_fetcher=fetch, robots_fetcher=lambda *_: '')
    items = web._search(CLAIM, 3, results_override=[{'url': URL + '/broken'}, {'url': URL}])
    assert items and all(i.evidence.url == URL for i in items)
    assert any(r.get('reason') and 'IncompleteRead' in r['reason'] for r in web.last_candidates)


def test_per_request_page_budget_preserves_later_query_capacity(config):
    config['fetching']['max_pages_per_request'] = 1
    config['fetching']['max_pages_per_claim'] = 2
    fetched = []
    web = WebRetriever(config, api_key='key',
        page_fetcher=lambda url, _: (fetched.append(url) or url, '<p>' + CLAIM * 3 + '</p>'), robots_fetcher=lambda *_: '')
    web._search(CLAIM, 3, results_override=[{'url': URL + '?noise'}, {'url': URL, 'title': CLAIM}])
    assert fetched == [URL]
    web._search(CLAIM, 3, results_override=[{'url': URL + '?next'}])
    assert fetched == [URL, URL + '?next']
