"""Live source-recall diagnostic. Does not call a verifier or supply expected URLs to retrieval."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.query_enrichment import TimeAwareRetriever
from src.system_builder import load_dotenv, load_web_retriever
from src.topical_rerank import canonical_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'data/evaluation/web_news_discovery_smoke.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    data = json.loads(args.dataset.read_text(encoding='utf-8'))
    load_dotenv(ROOT / '.env')
    web, _ = load_web_retriever()
    request = web.provider_request
    last_request = 0.0
    def paced_request(*a):
        nonlocal last_request
        time.sleep(max(0.0, 6.2 - (time.monotonic() - last_request)))
        last_request = time.monotonic()
        return request(*a)
    web.provider_request = paced_request
    layer = TimeAwareRetriever(web, as_of=date.fromisoformat(data['as_of']), force_reference=True)
    report = {'dataset': str(args.dataset), 'description': data['description'], 'results': [],
              'started_at': datetime.now(timezone.utc).isoformat()}
    for case in data['cases'][:args.limit]:
        started = time.monotonic()
        layer.as_of = date.fromisoformat(case.get('as_of', data['as_of']))
        hits = layer.search(case['claim'], 5)
        expected = canonical_url(case['expected_url'])
        urls = list(dict.fromkeys(i.evidence.url for i in hits))
        row = {'id': case['id'], 'source_recall_at_5': any(canonical_url(url) == expected for url in urls),
               'urls': urls, 'seconds': round(time.monotonic() - started, 2),
               'status': web.last_status, 'error': web.last_error, 'attempts': web.last_attempts,
               'candidates': web.last_candidates}
        report['results'].append(row)
        report['source_recall_at_5'] = sum(r['source_recall_at_5'] for r in report['results']) / len(report['results'])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: row[k] for k in ('id', 'source_recall_at_5', 'seconds', 'error')}), flush=True)
    print(json.dumps({'source_recall_at_5': report['source_recall_at_5'], 'count': len(report['results'])}), flush=True)


if __name__ == '__main__':
    main()
