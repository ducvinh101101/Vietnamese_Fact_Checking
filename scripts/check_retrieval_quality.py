"""Kiểm tra chất lượng retrieval LOCAL trên tập truy vấn dev (URL-level + silver passage).

So sánh các cấu hình retriever đang dùng trong dự án trên CÙNG tập truy vấn:

* ``bm25_v1``          — BM25 trên corpus v1 (chế độ ``local`` của system_builder)
* ``bm25_v2``          — BM25 trên corpus v2
* ``reranked_v2``      — W3-08 MetadataRerankedRetriever trên corpus v2 (nhánh local của ``hybrid``)
* ``fusion_local_v2``  — FusionRetriever(reranked_v2, web=None): hybrid khi web tắt/lỗi

Chỉ chạy trên split ``dev`` theo ``configs/retrieval_evaluation.yaml`` (no_test_tuning).
Ngoài số liệu còn kiểm tra contract (<= top_k, score không tăng, passage_id duy nhất).

    python scripts/check_retrieval_quality.py --limit 300
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from statistics import mean

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fusion_retriever import FusionRetriever  # noqa: E402
from src.io_utils import load_evidence_jsonl  # noqa: E402
from src.reranked_retriever import MetadataRerankedRetriever  # noqa: E402
from src.retriever import BM25Retriever  # noqa: E402

QUERY_SET = ROOT / "data/evaluation/vifactcheck_retrieval_query_set_v1.jsonl"
CUTOFFS = (1, 3, 5)


def build_retrievers() -> dict[str, object]:
    rr = yaml.safe_load((ROOT / "configs/reranked_retrieval.yaml").read_text(encoding="utf-8"))
    v1 = BM25Retriever(load_evidence_jsonl(ROOT / "data/evidence/vifactcheck_passages.jsonl"))
    v2 = BM25Retriever(load_evidence_jsonl(ROOT / rr["corpus"]))
    reranked = MetadataRerankedRetriever(v2, rr)
    return {
        "bm25_v1": v1,
        "bm25_v2": v2,
        "reranked_v2": reranked,
        "fusion_local_v2": FusionRetriever(reranked, None, candidate_k=20),
    }


def evaluate(retriever, queries: list[dict], top_k: int) -> dict[str, object]:
    url_hits = {k: 0 for k in CUTOFFS}
    passage_hits = {k: 0 for k in CUTOFFS}
    reciprocal: list[float] = []
    latencies: list[float] = []
    violations: list[str] = []
    returned_count = 0
    for query in queries:
        start = time.perf_counter()
        result = retriever.search(query["query"], top_k)
        returned_count += bool(result)
        latencies.append((time.perf_counter() - start) * 1000)
        scores = [item.score for item in result]
        pids = [item.evidence.passage_id for item in result]
        if len(result) > top_k:
            violations.append(f"{query['query_id']}: >top_k")
        if any(scores[i] < scores[i + 1] for i in range(len(scores) - 1)):
            violations.append(f"{query['query_id']}: score tăng")
        if len(set(pids)) != len(pids):
            violations.append(f"{query['query_id']}: passage_id trùng")
        urls = [item.evidence.url for item in result]
        silver = set(query.get("silver_exact_passage_ids") or [])
        first = next((rank for rank, url in enumerate(urls, start=1) if url == query["gold_url"]), None)
        reciprocal.append(1 / first if first and first <= 5 else 0.0)
        for k in CUTOFFS:
            url_hits[k] += query["gold_url"] in urls[:k]
            passage_hits[k] += bool(silver & set(pids[:k]))
    n = len(queries)
    latencies.sort()
    return {
        "returned_count": returned_count,
        "empty_count": n - returned_count,
        "url_top1_accuracy_when_returned": round(url_hits[1] / max(1, returned_count), 4),
        **{f"url_recall@{k}": round(url_hits[k] / n, 4) for k in CUTOFFS},
        "url_mrr@5": round(mean(reciprocal), 4),
        **{f"silver_passage_recall@{k}": round(passage_hits[k] / n, 4) for k in CUTOFFS},
        "latency_ms_p50": round(latencies[n // 2], 2),
        "latency_ms_p95": round(latencies[min(n - 1, int(n * 0.95))], 2),
        "contract_violations": violations[:20],
        "contract_violation_count": len(violations),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console Windows cp1252
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=0, help="Số truy vấn dev tối đa (0 = tất cả)")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/metrics/retrieval_quality_check_dev.json")
    args = parser.parse_args()

    queries = [json.loads(line) for line in QUERY_SET.read_text(encoding="utf-8").splitlines() if line.strip()]
    dev = [q for q in queries if q["split"] == "dev"]
    if args.limit:
        dev = dev[: args.limit]

    started = time.perf_counter()
    retrievers = build_retrievers()
    build_seconds = round(time.perf_counter() - started, 2)

    report = {"split": "dev", "queries": len(dev), "top_k": args.top_k, "index_build_seconds": build_seconds,
              "metric_caveat": "URL-level: không phải passage-level gold; silver = passage khớp nguyên văn.",
              "retrievers": {}}
    for name, retriever in retrievers.items():
        report["retrievers"][name] = evaluate(retriever, dev, args.top_k)
        metrics = report["retrievers"][name]
        print(f"{name:16s} R@1={metrics['url_recall@1']:.3f} R@3={metrics['url_recall@3']:.3f} "
              f"R@5={metrics['url_recall@5']:.3f} MRR@5={metrics['url_mrr@5']:.3f} "
              f"silverR@5={metrics['silver_passage_recall@5']:.3f} p50={metrics['latency_ms_p50']}ms "
              f"violations={metrics['contract_violation_count']}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã ghi {args.output.resolve()}")
    return 1 if any(m["contract_violation_count"] for m in report["retrievers"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
