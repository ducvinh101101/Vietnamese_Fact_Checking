"""Discover recent publisher URLs from RSS/Atom, never use feed snippets as evidence."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html import unescape
import re
import time
import unicodedata
from typing import Callable
import xml.etree.ElementTree as ET

from src.query_enrichment import publication_date
from src.topical_rerank import eligible, relevance


def parse_feed(xml: str, limit: int = 200) -> list[dict[str, object]]:
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)', xml, re.I):
        raise ValueError('RSS chứa khai báo XML không được hỗ trợ')
    root = ET.fromstring(xml)
    entries = []
    if root.tag.rsplit('}', 1)[-1] == 'urlset':
        for item in root:
            loc = next((child.text for child in item if child.tag.rsplit('}', 1)[-1] == 'loc'), None)
            if loc:
                # Sitemap slugs are locators, never publication dates or evidence.
                title = loc.rsplit('/', 1)[-1].rsplit('.', 1)[0].replace('-', ' ')
                entries.append({'url': loc, 'title': title, 'description': '', 'published_date': '',
                                '_date_source': 'publisher_sitemap'})
            if len(entries) >= 1000:
                break
        return entries
    for item in root.iter():
        if item.tag.rsplit('}', 1)[-1] not in {'item', 'entry'}:
            continue
        fields = {child.tag.rsplit('}', 1)[-1]: child for child in item}
        def value(key):
            return ''.join(fields[key].itertext()).strip() if key in fields else ''
        link = fields.get('link')
        url = (link.get('href') or value('link')) if link is not None else ''
        title = unescape(value('title'))
        description = re.sub(r'<[^>]*>', ' ', unescape(value('description') or value('summary')))
        entries.append({'url': url, 'title': title, 'description': description,
                        'published_date': value('pubDate') or value('published') or value('updated'),
                        '_date_source': 'publisher_feed'})
        if len(entries) >= limit:
            break
    return entries


class NewsDiscovery:
    def __init__(self, config: dict, fetcher: Callable[[str, float], tuple[str, str]],
                 url_allowed: Callable[[str], bool], normalize_date: Callable):
        self.config = config
        self.fetcher = fetcher
        self.url_allowed = url_allowed
        self.normalize_date = normalize_date
        self.cache: dict[str, tuple[float, list[dict[str, object]]]] = {}
        self.last_feeds: list[dict[str, object]] = []

    def _load(self, url: str):
        try:
            if not self.url_allowed(url):
                raise ValueError('RSS ngoài allowlist')
            cached = self.cache.get(url)
            if cached and time.monotonic() - cached[0] < self.config.get('ttl_seconds', 300):
                return url, cached[1], None, True
            final_url, xml = self.fetcher(url, float(self.config.get('timeout_seconds', 4)))
            if not self.url_allowed(final_url):
                raise ValueError('RSS chuyển hướng ngoài allowlist')
            entries = parse_feed(xml)
            return url, entries, None, False
        except (RuntimeError, ValueError, ET.ParseError, OSError) as error:
            return url, [], str(error), False

    def search(self, claim: str, date_window: tuple[date, date] | None = None, *,
               sitemap_days: tuple[date, ...] = (), include_feeds: bool = True) -> list[dict[str, object]]:
        feeds = self.config.get('feeds', [])[:int(self.config.get('max_feeds', 6))] if include_feeds else []
        feeds = list(feeds)
        for template in self.config.get('sitemap_templates', [])[:2]:
            for day in sitemap_days[:2]:
                feeds.append(template.format(date=day.isoformat(), year=day.year, month=day.month, day=day.day))
        self.last_feeds = []
        candidates = {}
        # Fetch independent publisher feeds concurrently, with a per-feed timeout.
        with ThreadPoolExecutor(max_workers=min(6, len(feeds) or 1)) as pool:
            loaded = list(pool.map(self._load, feeds))
        for url, entries, error, cached in loaded:
            self.last_feeds.append({'url': url, 'entries': len(entries), 'error': error, 'cached': cached})
            if error:
                continue
            self.cache[url] = (time.monotonic() if not cached else self.cache[url][0], entries)
            for entry in entries:
                if not self.url_allowed(str(entry['url'])):
                    continue
                published = self.normalize_date(entry['published_date'])
                day = publication_date(published)
                if date_window and day and not date_window[0] <= day <= date_window[1]:
                    continue
                text = f"{entry['title']} {entry['description']}"
                def unaccent(value):
                    return ''.join(c for c in unicodedata.normalize('NFD', value.casefold().replace('đ', 'd'))
                                   if unicodedata.category(c) != 'Mn')
                sitemap = entry['_date_source'] == 'publisher_sitemap'
                query, candidate_text = (unaccent(claim), unaccent(text)) if sitemap else (claim, text)
                if not eligible(query, candidate_text, minimum_coverage=0.18 if sitemap else 0.35):
                    continue
                coverage = relevance(query, candidate_text)
                previous = candidates.get(entry['url'])
                if previous is None or coverage > previous[0]:
                    candidates[entry['url']] = (coverage, {**entry, 'published_date': published, 'score': 0.8})
        ranked = sorted(candidates.values(), key=lambda row: (-row[0], row[1]['url']))
        return [entry for _, entry in ranked[:int(self.config.get('max_candidates', 6))]]
