"""Offline validation of the W2-07 contract; no network or key access."""
from pathlib import Path
from urllib.parse import urlsplit

import yaml


def allowed_url(url, hosts):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == 'https' and parsed.hostname in hosts
                and parsed.username is None and parsed.password is None
                and parsed.port in (None, 443)
                and not any(c.isspace() or ord(c) < 32 for c in url)
                and '\\' not in url)
    except ValueError:
        return False


def validate(config):
    assert config['version'] == 1 and config['enabled'] is False
    provider = config['provider']
    assert provider['name'] == 'tavily'
    assert provider['endpoint'] == 'https://api.tavily.com/search'
    assert provider['method'] == 'POST'
    assert provider['api_key_env'] == 'TAVILY_API_KEY'
    assert provider['search_depth'] == 'basic'
    assert all(provider[k] is False for k in ['auto_parameters', 'include_answer', 'include_raw_content'])
    assert 1 <= provider['max_results'] <= 20
    policy = config['source_policy']
    assert policy['match'] == 'exact_hostname'
    assert all(policy[k] is True for k in ['https_only', 'revalidate_every_redirect', 'reject_private_ips', 'require_original_page_passage'])
    hosts = [s['host'] for s in policy['allowlist']]
    assert hosts and len(hosts) == len(set(hosts)) and len(hosts) <= 300
    for source in policy['allowlist']:
        host = source['host']
        assert host == host.lower() and '*' not in host and '/' not in host
        assert source['category'] in ['government', 'international', 'press', 'corporate']
        assert source['name'] and source['scope']
        assert allowed_url(source['reference'], hosts)
    limits = config['limits']
    assert 1 <= limits['requests_per_claim'] <= 3
    assert 0 < limits['monthly_credit_budget'] <= 900
    assert 0 < limits['requests_per_minute'] <= 10
    assert 0 < limits['timeout_seconds'] <= 30
    assert limits['max_retries'] <= 1 and limits['fail_to'] == 'local_only'
    discovery = config.get('discovery', {})
    if discovery:
        assert 1 <= discovery['max_feeds'] <= 16
        assert 1 <= discovery['max_candidates'] <= 10
        assert 60 <= discovery['ttl_seconds'] <= 900
        assert 0 < discovery['timeout_seconds'] <= 8
        assert all(allowed_url(url, hosts) for url in discovery['feeds'])
        catalog = discovery.get('feed_catalog', [])
        assert len({entry['url'] for entry in catalog}) == len(catalog)
        for entry in catalog:
            assert allowed_url(entry['url'], hosts)
            assert isinstance(entry.get('topics', []), list)
            assert all(isinstance(topic, str) and topic.strip() for topic in entry.get('topics', []))
        assert 0 <= discovery.get('core_feed_count', 4) <= discovery['max_feeds']
        assert all(url in discovery['feeds'] for url in discovery.get('feed_topics', {}))
        assert len(discovery.get('sitemap_templates', [])) <= 2
        assert all(allowed_url(template.format(date='2026-11-03', year=2026, month=11, day=3), hosts)
                   for template in discovery.get('sitemap_templates', []))
    fetching = config.get('fetching', {})
    if fetching:
        assert 1 <= fetching['workers'] <= 6
        assert 1 <= fetching['max_pages_per_claim'] <= 60
        assert 1 <= fetching['max_pages_per_request'] <= fetching['max_pages_per_claim']
        assert 0 < fetching['timeout_seconds'] <= limits['timeout_seconds']
    cache = config['cache']
    assert cache['directory'] == '.cache/web_retrieval'
    assert all(cache[k] is False for k in ['persist_provider_responses', 'persist_page_content', 'commit_to_git'])
    assert all(value is False for value in config['secrets'].values())
    extraction = config['extraction']
    assert 0 <= extraction['max_redirects'] <= 5
    assert 0 < extraction['max_page_bytes'] <= 2_000_000
    assert 80 <= extraction['minimum_passage_chars'] < extraction['maximum_passage_chars'] <= 2_000
    assert 1 <= extraction['max_passages_per_page'] <= 5
    return hosts


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'configs/web_retrieval.yaml'
    hosts = validate(yaml.safe_load(path.read_text(encoding='utf-8')))
    print(f'W2-07 config valid: Tavily, {len(hosts)} exact hosts, web disabled. No API call made.')
