"""Evaluate the existing BM25 retriever on the ViFactCheck grouped split.

The ViFactCheck labels identify the source article URL for each annotated
evidence.  This benchmark therefore measures URL-level retrieval: a result is
relevant when one of its passages originates from that URL.  It deliberately
does not present this as a passage-level gold benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.io_utils import load_evidence_jsonl
from src.retriever import BM25Retriever


DEFAULT_CORPUS = Path("data/evidence/vifactcheck_passages.jsonl")
DEFAULT_SPLIT = Path("data/processed/vifactcheck_group_split/test.parquet")
DEFAULT_METRICS = Path("outputs/metrics/bm25_retrieval_test.json")
DEFAULT_PREDICTIONS = Path("outputs/retrieval/bm25_retrieval_test_top5.jsonl")
DEFAULT_AUDIT = Path("data/evaluation/bm25_retrieval_audit_queries.jsonl")


def normalise_text(value: object) -> str:
    """Normalise Vietnamese text enough for a transparent coverage audit."""
    return re.sub(r"[^0-9a-zà-ỹ]+", " ", str(value).lower()).strip()


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def stable_audit_indices(query_ids: list[str], count: int = 10) -> set[int]:
    ranked = sorted(
        enumerate(query_ids),
        key=lambda item: hashlib.sha256(item[1].encode("utf-8")).hexdigest(),
    )
    return {index for index, _ in ranked[:count]}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if args.top_k < 5:
        raise ValueError("W2-01 requires --top-k >= 5 to report Recall@3 and Recall@5.")

    frame = pd.read_parquet(args.split)
    required_columns = {"Statement", "Evidence", "Url"}
    missing = required_columns.difference(frame.columns)
    if missing:
        raise ValueError(f"Split is missing required columns: {sorted(missing)}")

    evidence_items = load_evidence_jsonl(args.corpus)
    passages_by_url: dict[str, list[str]] = defaultdict(list)
    for item in evidence_items:
        passages_by_url[item.url].append(normalise_text(item.content))

    index_started = time.perf_counter()
    retriever = BM25Retriever(evidence_items)
    index_seconds = time.perf_counter() - index_started

    query_ids = [str(value) for value in frame.index]
    audit_indices = stable_audit_indices(query_ids)
    predictions: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    reciprocal_ranks: list[float] = []
    hits_at_3: list[float] = []
    hits_at_5: list[float] = []
    latencies_ms: list[float] = []
    exact_passage_gold = 0

    for row_number, row in enumerate(frame.itertuples(index=True)):
        query_id = str(row.Index)
        statement = str(row.Statement)
        gold_url = str(row.Url)
        gold_evidence = normalise_text(row.Evidence)
        gold_passages = passages_by_url.get(gold_url, [])
        exact_match = any(
            gold_evidence in passage or passage in gold_evidence for passage in gold_passages
        )
        exact_passage_gold += int(exact_match)

        started = time.perf_counter()
        ranked = retriever.search(statement, top_k=args.top_k)
        latency_ms = (time.perf_counter() - started) * 1_000
        latencies_ms.append(latency_ms)
        result_urls = [result.evidence.url for result in ranked]
        first_rank = next((rank for rank, url in enumerate(result_urls, start=1) if url == gold_url), None)
        hits_at_3.append(float(first_rank is not None and first_rank <= 3))
        hits_at_5.append(float(first_rank is not None and first_rank <= 5))
        reciprocal_ranks.append(1 / first_rank if first_rank is not None else 0.0)

        record = {
            "query_id": query_id,
            "gold_url": gold_url,
            "exact_evidence_to_passage_match": exact_match,
            "first_relevant_rank_at_5": first_rank,
            "latency_ms": round(latency_ms, 4),
            "results": [
                {
                    "rank": rank,
                    "passage_id": result.evidence.passage_id,
                    "url": result.evidence.url,
                    "score": round(result.score, 8),
                }
                for rank, result in enumerate(ranked, start=1)
            ],
        }
        predictions.append(record)
        if row_number in audit_indices:
            audit_rows.append({"statement": statement, "evidence": str(row.Evidence), **record})

    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    with args.predictions.open("w", encoding="utf-8") as handle:
        for record in predictions:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    audit_rows.sort(key=lambda record: str(record["query_id"]))
    write_json(args.audit, audit_rows)
    metrics = {
        "benchmark": "W2-01 BM25 retrieval baseline",
        "relevance_definition": "URL-level: a retrieved passage is relevant when its URL equals the annotated ViFactCheck evidence URL.",
        "scope_note": "This is not a passage-level gold metric. Exact annotated-evidence-to-passage coverage is reported separately.",
        "corpus": {"path": str(args.corpus), "passages": len(evidence_items), "urls": len(passages_by_url)},
        "evaluation_split": {"path": str(args.split), "queries": len(frame), "unique_gold_urls": int(frame["Url"].nunique())},
        "metrics": {
            "recall_at_3": round(mean(hits_at_3), 6),
            "recall_at_5": round(mean(hits_at_5), 6),
            "mrr_at_5": round(mean(reciprocal_ranks), 6),
            "latency_ms": {
                "mean": round(mean(latencies_ms), 4),
                "p50": round(percentile(latencies_ms, 0.50), 4),
                "p95": round(percentile(latencies_ms, 0.95), 4),
            },
        },
        "gold_coverage": {
            "urls_present_in_corpus": int(sum(url in passages_by_url for url in frame["Url"].unique())),
            "unique_gold_urls": int(frame["Url"].nunique()),
            "exact_evidence_to_passage_matches": exact_passage_gold,
            "exact_evidence_to_passage_coverage": round(exact_passage_gold / len(frame), 6),
        },
        "index_build_seconds": round(index_seconds, 4),
        "retriever": "src.retriever.BM25Retriever (rank-bm25)",
        "audit": {"path": str(args.audit), "queries": len(audit_rows), "selection": "ten lowest SHA-256(query_id) values; deterministic"},
        "predictions": {"path": str(args.predictions), "top_k": args.top_k},
    }
    write_json(args.metrics, metrics)
    print(json.dumps(metrics["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
