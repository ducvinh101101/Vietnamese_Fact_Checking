from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from scripts.check_web_retrieval_config import allowed_url, validate


def config():
    return yaml.safe_load((Path(__file__).resolve().parents[1]/'configs/web_retrieval.yaml').read_text(encoding='utf-8'))


def test_contract():
    assert len(validate(config())) == 3


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
