"""Independently recompute W2-04 quality metrics from saved passage IDs."""
import hashlib
import json
from pathlib import Path

import pandas as pd


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'outputs/retrieval/w2_04'
    report = json.loads((folder / 'dev_metrics.json').read_text(encoding='utf-8'))
    corpus = root / 'data/evidence/vifactcheck_passages.jsonl'
    items = [json.loads(line) for line in corpus.read_text(encoding='utf-8').splitlines()]
    urls = {item['passage_id']: item['url'] for item in items}
    frame = pd.read_parquet(root / 'data/processed/vifactcheck_group_split/dev.parquet')
    rows = [json.loads(line) for line in (folder/'dev_predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == len(frame) == report['queries']
    assert [row['query_id'] for row in rows] == [str(i) for i in frame.index]
    for name in ('bm25', 'dense', 'hybrid_rrf'):
        ranks = []
        for record, gold in zip(rows, frame.Url):
            assert record['gold_url'] == gold
            prediction = record['methods'][name]
            ids = prediction['passage_ids']
            assert len(ids) == len(set(ids)) == 5
            rank = next((i for i, pid in enumerate(ids, 1) if urls[pid] == gold), 0)
            assert rank == prediction['first_relevant_rank_at_5']
            assert prediction['latency_ms'] > 0
            ranks.append(rank)
        recalculated = {
            'recall_at_3': sum(0 < r <= 3 for r in ranks)/len(rows),
            'recall_at_5': sum(r > 0 for r in ranks)/len(rows),
            'mrr_at_5': sum(1/r if r else 0 for r in ranks)/len(rows),
        }
        for metric, value in recalculated.items():
            assert abs(report['metrics'][name][metric] - value) < 1e-12
    for path, expected in [(corpus, report['corpus_sha256']),
                           (root/'data/processed/vifactcheck_group_split/dev.parquet', report['split_sha256']),
                           (root/'scripts/evaluate_dense_hybrid.py', report['script_sha256'])]:
        with path.open('rb') as handle:
            assert hashlib.file_digest(handle, 'sha256').hexdigest() == expected
    print(f'Validated {len(rows)} queries, all three rankings/metrics, corpus/split/script hashes.')


if __name__ == '__main__':
    main()
