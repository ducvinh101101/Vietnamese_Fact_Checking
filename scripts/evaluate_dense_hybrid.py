"""W2-04: frozen E5/FAISS and equal-weight RRF against existing BM25.

Run from the repository root. Models and vectors stay in .cache/, results
in outputs/retrieval/w2_04/. No production retriever is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))

import numpy as np
import pandas as pd

from src.io_utils import load_evidence_jsonl
from src.retriever import BM25Retriever


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rrf(first, second, constant=60):
    scores = {}
    for ranking in (first, second):
        for rank, index in enumerate(ranking, 1):
            index = int(index)
            scores[index] = scores.get(index, 0.0) + 1.0 / (constant + rank)
    return sorted(scores, key=lambda index: (-scores[index], index))


def metrics(ranks, latencies):
    ranks = np.asarray(ranks)
    return {
        "recall_at_3": float(np.mean((ranks > 0) & (ranks <= 3))),
        "recall_at_5": float(np.mean((ranks > 0) & (ranks <= 5))),
        "mrr_at_5": float(np.mean([1 / r if 0 < r <= 5 else 0 for r in ranks])),
        "latency_ms": {"mean": float(np.mean(latencies)),
                       "p50": float(np.percentile(latencies, 50)),
                       "p95": float(np.percentile(latencies, 95))},
    }


def main():
    import faiss
    import torch
    from transformers import AutoModel, AutoTokenizer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    faiss.omp_set_num_threads(args.threads)
    torch.manual_seed(0)
    corpus = ROOT / "data/evidence/vifactcheck_passages.jsonl"
    split = ROOT / f"data/processed/vifactcheck_group_split/{args.split}.parquet"
    output = ROOT / "outputs/retrieval/w2_04"
    output.mkdir(parents=True, exist_ok=True)
    items = load_evidence_jsonl(corpus)
    frame = pd.read_parquet(split)
    if frame.empty or frame[["Statement", "Url"]].isna().any().any():
        raise ValueError("Empty split or missing queries/gold URLs")
    urls = {item.url for item in items}
    if not set(frame.Url).issubset(urls):
        raise ValueError("Gold URL missing from corpus")
    ids = {item.passage_id: i for i, item in enumerate(items)}
    if len(ids) != len(items):
        raise ValueError("Duplicate passage IDs")
    model_hashes = {p.name: sha256(p) for p in sorted(args.model_path.glob('*'))
                    if p.is_file() and p.suffix in ('.json', '.safetensors')}
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    model = AutoModel.from_pretrained(args.model_path, local_files_only=True).eval()

    def encode(texts):
        batch = tokenizer(texts, max_length=512, padding=True, truncation=True, return_tensors="pt")
        with torch.inference_mode():
            hidden = model(**batch).last_hidden_state
            masked = hidden.masked_fill(~batch['attention_mask'][..., None].bool(), 0.0)
            pooled = masked.sum(dim=1) / batch['attention_mask'].sum(dim=1)[..., None]
            return torch.nn.functional.normalize(pooled, p=2, dim=1).numpy().astype('float32')

    key = hashlib.sha256(json.dumps([sha256(corpus), model_hashes, 512, 'passage: '], sort_keys=True).encode()).hexdigest()
    cache = ROOT / '.cache' / 'w2_04' / f'{key}.npy'
    cached = cache.exists()
    started = time.perf_counter()
    if cached:
        vectors = np.load(cache, allow_pickle=False)
    else:
        chunks = []
        for start in range(0, len(items), 16):
            chunks.append(encode(['passage: ' + item.content for item in items[start:start+16]]))
            if start % 256 == 0:
                print(f'Encoded {min(start+16,len(items))}/{len(items)} passages', flush=True)
        vectors = np.concatenate(chunks)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, vectors)
    embedding_seconds = time.perf_counter() - started
    if vectors.shape[0] != len(items) or not np.isfinite(vectors).all():
        raise ValueError('Invalid vectors')
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    # Check exact FAISS search against brute-force dot products, ignoring tie order.
    distances, neighbors = index.search(vectors[:3], 5)
    for row in range(3):
        expected = np.sort(vectors @ vectors[row])[-5:][::-1]
        np.testing.assert_allclose(distances[row], expected, atol=1e-5)
    bm25 = BM25Retriever(items)
    encode(['query: khởi động'])  # excluded warm-up
    ranks = {name: [] for name in ('bm25', 'dense', 'hybrid_rrf')}
    latencies = {name: [] for name in ranks}
    with (output / f'{args.split}_predictions.jsonl').open('w', encoding='utf-8') as handle:
        for number, row in enumerate(frame.itertuples()):
            start = time.perf_counter()
            lexical = [ids[r.evidence.passage_id] for r in bm25.search(str(row.Statement), top_k=100)]
            lexical_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            query = encode(['query: ' + str(row.Statement)])
            _, found = index.search(query, min(100, len(items)))
            dense = found[0].tolist()
            dense_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            hybrid = rrf(lexical, dense)
            hybrid_ms = lexical_ms + dense_ms + (time.perf_counter() - start) * 1000
            record = {'query_id': str(row.Index), 'gold_url': str(row.Url), 'methods': {}}
            for name, ranking, latency in [('bm25', lexical, lexical_ms), ('dense', dense, dense_ms), ('hybrid_rrf', hybrid, hybrid_ms)]:
                top = ranking[:5]
                rank = next((i for i, idx in enumerate(top, 1) if items[idx].url == row.Url), 0)
                ranks[name].append(rank)
                latencies[name].append(latency)
                record['methods'][name] = {'first_relevant_rank_at_5': rank, 'latency_ms': latency,
                    'passage_ids': [items[idx].passage_id for idx in top]}
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
            if number % 100 == 0:
                print(f'Evaluated {number+1}/{len(frame)} {args.split} queries', flush=True)
    report = {
        'split': args.split, 'queries': len(frame), 'corpus_passages': len(items),
        'relevance': 'URL-level hit rate in top-k passages, matching W2-01; not passage-gold accuracy',
        'model': 'intfloat/multilingual-e5-small', 'revision': args.model_path.name,
        'model_sha256': model_hashes, 'corpus_sha256': sha256(corpus), 'split_sha256': sha256(split),
        'parameters': {'pooling': 'masked mean + L2 normalisation', 'max_length': 512,
                       'faiss': 'IndexFlatIP', 'rrf_constant': 60, 'candidate_depth': 100,
                       'rrf_weights': [1, 1], 'threads': args.threads},
        'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                        'device': 'cpu', 'packages': {p: importlib.metadata.version(p) for p in ['torch', 'transformers', 'faiss-cpu', 'numpy', 'rank-bm25']}},
        'git_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        'script_sha256': sha256(__file__),
        'passage_embedding_seconds': embedding_seconds, 'embedding_cache_used': cached,
        'latency_scope': 'Sequential warm CPU queries; dense includes encoding and FAISS search; hybrid includes BM25+dense+fusion; corpus encoding/index construction excluded',
        'metrics': {name: metrics(ranks[name], latencies[name]) for name in ranks},
        'selection_rule': 'On dev only: replace BM25 only if Recall@5 and MRR@5 both strictly improve; otherwise retain BM25. Fixed parameters, no test tuning.',
    }
    report['eligible_on_dev'] = [name for name in ('dense', 'hybrid_rrf')
        if all(report['metrics'][name][m] > report['metrics']['bm25'][m] for m in ('recall_at_5', 'mrr_at_5'))] if args.split == 'dev' else None
    (output / f'{args.split}_metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report['metrics'], indent=2), flush=True)


if __name__ == '__main__':
    main()
