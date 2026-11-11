from copy import deepcopy
from pathlib import Path
import json
from urllib.parse import urlsplit

import pytest
import yaml

from scripts.check_web_retrieval_config import allowed_url, validate


def config():
    return yaml.safe_load((Path(__file__).resolve().parents[1]/'configs/web_retrieval.yaml').read_text(encoding='utf-8'))


def test_contract():
    hosts = validate(config())
    assert len(hosts) >= 7
    assert {"baochinhphu.vn", "moh.gov.vn", "mofa.gov.vn", "www.who.int", "vnanet.vn", "vov.vn"}.issubset(hosts)


@pytest.mark.parametrize('url', [
    'https://vnexpress.net.evil.example/a', 'https://evilvnexpress.net',
    'https://vnexpress.net@evil.example', 'http://vnexpress.net',
    'https://127.0.0.1', 'https://vnexpress.net:8080',
    'https://vnexpress.net\\@evil.example', 'https://blog.vnexpress.net',
    'https://vnexpress.net\n.evil.example', 'https://[bad',
])
def test_rejects_unapproved_urls(url):
    assert not allowed_url(url, validate(config()))


def test_accepts_exact_host():
    assert allowed_url('https://VNEXPRESS.NET:443/a?q=1', validate(config()))


def test_rejects_accidental_enable_and_duplicate_host():
    for mutate in [lambda c: c.update(enabled=True),
                   lambda c: c['source_policy']['allowlist'].append(deepcopy(c['source_policy']['allowlist'][0]))]:
        c = config()
        mutate(c)
        with pytest.raises(AssertionError):
            validate(c)


def test_expanded_registry_has_audited_provenance_and_scoped_sources():
    cfg = config()
    sources = {s['host']: s for s in cfg['source_policy']['allowlist']}
    assert {'nso.gov.vn', 'moet.gov.vn', 'mst.gov.vn', 'suckhoedoisong.vn',
            'giaoducthoidai.vn', 'cand.vn', 'www.qdnd.vn', 'baocantho.com.vn',
            'www.worldbank.org', 'www.imf.org', 'www.adb.org', 'www.who.int'} <= sources.keys()
    audit = json.loads(Path('data/source_catalog/source_review_20261106.json').read_text(encoding='utf-8'))
    included = {r['host']: r for r in audit['records'] if r['included']}
    assert sources.keys() == included.keys()
    assert audit['total_hosts'] == len(sources)
    assert audit['added_hosts'] == len(sources) - audit['initial_hosts']
    for host, record in included.items():
        assert record.get('identity_match') or record.get('verification_method')
        assert record.get('url') or record.get('identity_reference')
    for source in sources.values():
        if source['category'] == 'corporate':
            assert source['scope']  # Corporate announcements retain their own publication scope.


def test_new_feed_catalog_was_parsed_and_routes_real_topics():
    from src.news_discovery import NewsDiscovery
    cfg = config()
    discovery = NewsDiscovery(cfg['discovery'], None, None, None)
    audit = json.loads(Path('data/source_catalog/feed_review_20261106.json').read_text(encoding='utf-8'))
    verified = {r.get('final_url', r['url']) for r in audit['records'] if r['status'] == 'ready'}
    assert all(entry['url'] in verified for entry in cfg['discovery']['feed_catalog'])
    assert audit['catalog_size'] == len(cfg['discovery']['feed_catalog'])
    for claim, expected_host in [
        ('Bệnh viện điều trị bệnh sốt xuất huyết', 'suckhoedoisong.vn'),
        ('Lãi suất và tỷ giá ngân hàng', 'thoibaonganhang.vn'),
        ('AI thúc đẩy chip bán dẫn toàn cầu', 'baovanhoa.vn'),
        ('Kinh tế tỉnh Lạng Sơn phát triển', 'baolangson.vn'),
    ]:
        feeds = discovery.select_feeds(claim)
        assert len(feeds) <= cfg['discovery']['max_feeds']
        assert expected_host in {urlsplit(u).hostname for u in feeds}


def test_rejects_feed_redirect_candidates_outside_reviewed_hosts():
    cfg = config()
    cfg['discovery']['feed_catalog'].append({'url': 'https://suckhoedoisong.vn.evil.example/rss', 'topics': []})
    with pytest.raises(AssertionError):
        validate(cfg)
