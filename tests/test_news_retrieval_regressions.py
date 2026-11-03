"""Real failure shapes: current news, long claims, missed articles and auditability."""
from datetime import date
from pathlib import Path

import pytest
import yaml

from src.fusion_retriever import FusionRetriever
from src.query_enrichment import TimeAwareRetriever, resolve_time_scope
from src.schemas import Evidence, RetrievedEvidence
from src.temporal_gate import TemporalGateRetriever
from src.topical_rerank import TopicalRerankRetriever
from src.web_retriever import WebRetriever, extract_passages


REFERENCE = date(2026, 11, 3)
GOLD = ("Giá vàng thế giới tăng mạnh, thoát đáy một năm. "
        "Mỗi ounce vàng có thời điểm tăng gần 100 USD trong phiên đầu tuần, "
        "lên sát 4.000 USD, nhờ giá dầu giảm gần 8%.")
PARLIAMENT = ("Ngày 3/11, Quốc hội thảo luận tại hội trường về 4 dự án luật liên quan "
              "đến trưng mua, trưng dụng tài sản; sở hữu trí tuệ; đấu giá tài sản và điện lực.")


@pytest.fixture
def cfg(tmp_path):
    config = yaml.safe_load(Path("configs/web_retrieval.yaml").read_text(encoding="utf-8"))
    config['enabled'] = True
    config['cache']['directory'] = str(tmp_path / 'cache')
    return config


def article(text, published='2026-11-03'):
    return f'<meta property="article:published_time" content="{published}"><article><p>{text}</p></article>'


@pytest.mark.parametrize('text,anchor', [
    ('Ngày 3/11, Quốc hội thảo luận', REFERENCE),
    ('Ngày 3 tháng 11, Quốc hội thảo luận', REFERENCE),
    ('Ngày 03/11/2020, Quốc hội thảo luận', date(2020, 11, 3)),
    ('Ngày 2020-11-03, Quốc hội thảo luận', date(2020, 11, 3)),
])
def test_explicit_date_anchors_publication_window(text, anchor):
    scope = resolve_time_scope(text, REFERENCE)
    assert scope.kind == 'dated' and scope.anchor == anchor
    assert scope.start <= anchor <= scope.end


def test_reference_year_not_machine_year_and_invalid_date():
    assert resolve_time_scope('Ngày 3/11 họp Quốc hội', date(2024, 11, 4)).anchor.year == 2024
    with pytest.raises(ValueError, match='không hợp lệ'):
        resolve_time_scope('Ngày 31/2 họp Quốc hội', REFERENCE)


def test_reference_date_forces_window_but_preserves_historical_year():
    assert resolve_time_scope('Giá vàng tăng mạnh', REFERENCE) is None
    assert resolve_time_scope('Giá vàng tăng mạnh', REFERENCE, force_reference=True).kind == 'reference'
    assert resolve_time_scope('Năm 2020 giá vàng tăng', REFERENCE, force_reference=True) is None
    assert resolve_time_scope(GOLD, REFERENCE).kind == 'today'


def test_query_selects_late_passage_before_cap_and_keeps_adjacent_context():
    noise = ''.join(f'<p>Thông tin nền số {i}. ' + 'Bối cảnh kinh tế khác được công bố. ' * 6 + '</p>' for i in range(5))
    parts = GOLD.split('. ', 1)
    html = '<article>' + noise + f'<p>{parts[0]}.</p><p>{parts[1]}</p></article>'
    _, passages = extract_passages(html, 120, 800, 3, query=GOLD)
    assert any('thoát đáy một năm' in p and '8%' in p for p in passages)


def test_weak_first_hit_does_not_stop_shorter_queries(cfg):
    calls = []
    def provider(payload, *_):
        calls.append(payload)
        return {'results': [{'url': 'https://vnexpress.net/' + ('weak' if len(calls) == 1 else 'exact')}]}
    def fetch(url, *_):
        return url, article('Giá vàng thế giới tăng lên sát 4.000 USD. ' * 4 if url.endswith('weak') else GOLD)
    web = WebRetriever(cfg, api_key='key', provider_request=provider, page_fetcher=fetch,
                       robots_fetcher=lambda *_: '')
    items = web.search_time_window(GOLD, 5, date(2026, 10, 24), REFERENCE)
    assert 2 <= len(calls) <= 3
    assert len(calls[1]['query']) < len(calls[0]['query'])
    assert items[0].evidence.url.endswith('/exact')
    assert any(i.evidence.url.endswith('/weak') for i in items)  # merge, don't replace


def test_general_fallback_keeps_press_and_filters_by_original_page_date(cfg):
    calls = []
    def provider(payload, *_):
        calls.append(payload)
        if payload['topic'] == 'news':
            return {'results': []}
        assert 'vnexpress.net' in payload['include_domains']
        return {'results': [{'url': 'https://vnexpress.net/exact'}]}
    web = WebRetriever(cfg, api_key='key', provider_request=provider,
                       page_fetcher=lambda url, *_: (url, article(GOLD)), robots_fetcher=lambda *_: '')
    assert web.search_time_window(GOLD, 5, date(2026, 10, 24), REFERENCE)
    assert len(calls) == 3
    assert web.last_attempts[-1]['stage'] == 'general_fallback'


def test_direct_url_bypasses_index_and_key_but_not_date_or_allowlist(cfg):
    fetched = []
    def fetch(url, *_):
        fetched.append(url)
        return url, article(PARLIAMENT)
    web = WebRetriever(cfg, api_key='', provider_request=lambda *_: pytest.fail('No API request needed'),
                       page_fetcher=fetch, robots_fetcher=lambda *_: '')
    items = web.search_time_window(PARLIAMENT, 3, date(2026, 10, 24), REFERENCE,
                                   source_urls=('https://congly.vn/article', 'https://evil.example/article'))
    assert items and fetched == ['https://congly.vn/article']
    assert any('allowlist' in str(r.get('reason')) for r in web.last_candidates)
    assert web.last_attempts[0]['stage'] == 'direct_urls'


def test_direct_url_stale_or_robots_denied_remains_rejected(cfg):
    web = WebRetriever(cfg, api_key='', page_fetcher=lambda url, *_: (url, article(GOLD, '2023-01-01')),
                       robots_fetcher=lambda *_: '')
    assert not web.search_time_window(GOLD, 3, date(2026, 10, 24), REFERENCE,
                                      source_urls=('https://vnexpress.net/old',))
    assert 'ngoài cửa sổ' in web.last_candidates[0]['reason']
    web.robots_fetcher = lambda *_: 'User-agent: *\nDisallow: /'
    assert not web.search(GOLD, source_urls=('https://vnexpress.net/blocked',))
    assert 'robots.txt' in web.last_candidates[0]['reason']


def test_queries_remain_within_budget_and_metadata_resets(cfg):
    calls = []
    web = WebRetriever(cfg, api_key='key', provider_request=lambda payload, *_: calls.append(payload) or {'results': []})
    assert not web.search(GOLD)
    assert len(calls) <= cfg['limits']['requests_per_claim']
    web.api_key = ''
    assert not web.search('Khẳng định khác')
    assert web.last_candidates == [] and web.last_error is None
    assert len(web.last_attempts) == 1 and web.last_status == 'missing_api_key'


def test_full_chain_removes_undated_and_old_local_and_preserves_claim(cfg):
    web = WebRetriever(cfg, api_key='key', provider_request=lambda *_: {'results': [{'url': 'https://vnexpress.net/exact'}]},
                       page_fetcher=lambda url, *_: (url, article(GOLD)), robots_fetcher=lambda *_: '')
    layer = TimeAwareRetriever(web, as_of=REFERENCE, force_reference=True)
    class Local:
        def search(self, claim, top_k):
            assert claim == GOLD
            return [RetrievedEvidence(Evidence(f'old-{i}', f'old-{i}', GOLD, published_at=published,
                                                url=f'https://dantri.com.vn/old-{i}'), 100)
                    for i, published in enumerate((None, '2023-01-01'))]
    gate = TemporalGateRetriever(FusionRetriever(Local(), layer), as_of=REFERENCE,
                                 window_today=10, force_reference=True)
    results = TopicalRerankRetriever(gate).search(GOLD, 5)
    assert results and all(r.evidence.url.startswith('https://vnexpress.net/') for r in results)
    assert gate.last_dropped_stale == 1 and gate.last_dropped_undated == 1
    assert gate.last_cutoff == layer.last_scope.start and gate.last_end == layer.last_scope.end


def test_historical_exact_date_uses_its_own_window():
    class Web:
        def search_time_window(self, claim, top_k, start_date, end_date, **kwargs):
            assert start_date == date(2023, 3, 5) and end_date == date(2023, 3, 25)
            return []
    TimeAwareRetriever(Web(), as_of=REFERENCE).search('Giá xăng ngày 15/3/2023 tăng')


def test_web_and_gate_agree_on_vietnam_date_at_timezone_boundary(cfg):
    web = WebRetriever(cfg, api_key='', page_fetcher=lambda url, *_: (url, article(GOLD, '2026-11-04T00:30:00+14:00')),
                       robots_fetcher=lambda *_: '')
    items = web.search_time_window(GOLD, 3, date(2026, 10, 24), REFERENCE,
                                   source_urls=('https://vnexpress.net/tz',))
    assert items
    class Inner:
        def search(self, *_):
            return items
    assert TemporalGateRetriever(Inner(), as_of=REFERENCE).search(GOLD)
