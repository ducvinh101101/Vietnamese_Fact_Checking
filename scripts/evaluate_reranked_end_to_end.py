"""W4-05 / W5-02: đánh giá end-to-end với retriever rerank cục bộ (W3-08).

Chạy đúng giao thức của evaluate_local_end_to_end.py nhưng thay BM25 thuần bằng
``MetadataRerankedRetriever`` trên corpus v2 có metadata. Mục đích là đo tầng
"reranked-local" tách riêng để so với tầng "BM25-local", KHÔNG trộn web (fusion
vẫn là hạng mục riêng chưa có).

    py -3.13 scripts/evaluate_reranked_end_to_end.py --config configs/reranked_end_to_end.yaml --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/reranked_e2e_dev.json --predictions outputs/predictions/reranked_e2e_dev.csv

Nhãn/URL/evidence annotation chỉ được đọc SAU khi pipeline đã cho kết quả. Không
truyền chúng vào pipeline. Relevance vẫn là URL-level proxy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean

import pandas as pd
import yaml
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(ROOT / ".cache/huggingface"))

LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
ID_TO_LABEL = {0: "SUPPORTED", 1: "REFUTED", 2: "NOT_ENOUGH_INFO"}


def sha256(path: Path) -> str:
    import hashlib
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def build_reranked_pipeline(config: dict, root: Path = ROOT) -> FactCheckingPipeline:
    """Dựng pipeline với retriever rerank tiêm vào; verifier giữ nguyên config."""
    # Lazy import: giữ module load được (để test run_evaluation) khi chưa có torch/rank_bm25.
    from src.io_utils import load_evidence_jsonl
    from src.pipeline import FactCheckingPipeline
    from src.reranked_retriever import MetadataRerankedRetriever
    from src.retriever import BM25Retriever

    corpus_path = root / config["paths"]["evidence_path"]
    base = BM25Retriever(load_evidence_jsonl(corpus_path))
    retriever = MetadataRerankedRetriever(base, config["retrieval"]["reranked"])
    verification = config["verification"]
    return FactCheckingPipeline(
        retriever=retriever,
        top_k=int(config["retrieval"]["top_k"]),
        engine=verification["engine"],
        model_path=str(root / verification["model_path"]),
        vncorenlp_dir=str(root / verification["vncorenlp_dir"]),
        max_length=int(verification["max_length"]),
        temperature=float(verification.get("temperature", 1.0)),
        decisive_min_confidence=float(verification.get("decisive_min_confidence", 0.0)),
        retrieval_rank_bias=float(verification.get("retrieval_rank_bias", 0.0)),
        aggregation_model_path=str(root / verification["aggregation_model_path"]) if verification.get("aggregation_model_path") else None,
    )


def run_evaluation(pipeline, frame: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Chạy pipeline trên từng claim và trả (khối classification, prediction_frame).

    Pure so với I/O: nhận pipeline (có thể là stub) và DataFrame, nên test được
    mà không cần model thật.
    """
    required = {"Statement", "Evidence", "Url", "labels"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Split thiếu cột: {sorted(missing)}")

    records: list[dict[str, object]] = []
    latencies_ms: list[float] = []
    for row in frame.itertuples(index=True):
        started = time.perf_counter()
        result, retrieved = pipeline.run(str(row.Statement))
        latency_ms = (time.perf_counter() - started) * 1_000
        latencies_ms.append(latency_ms)
        retrieved_rows = [
            {"rank": rank, "passage_id": item.evidence.passage_id, "url": item.evidence.url, "score": round(item.score, 8)}
            for rank, item in enumerate(retrieved, start=1)
        ]
        citation_rows = [item for item in retrieved_rows if item["passage_id"] in result.evidence_ids]
        gold_url = str(row.Url)
        first_gold_rank = next((item["rank"] for item in retrieved_rows if item["url"] == gold_url), None)
        records.append({
            "source_row_id": str(row.Index),
            "gold_label": ID_TO_LABEL[int(row.labels)],
            "predicted_label": result.label,
            "confidence": result.confidence,
            "gold_url": gold_url,
            "claim": str(row.Statement),
            "annotated_evidence": str(row.Evidence),
            "first_gold_url_rank_at_top_k": first_gold_rank,
            "gold_url_retrieved_at_top_k": first_gold_rank is not None,
            "citation_url_matches_gold": any(item["url"] == gold_url for item in citation_rows),
            "citation_ids": json.dumps(result.evidence_ids, ensure_ascii=False),
            "retrieved": json.dumps(retrieved_rows, ensure_ascii=False),
            "latency_ms": round(latency_ms, 4),
        })

    prediction_frame = pd.DataFrame(records)
    y_true = prediction_frame["gold_label"].tolist()
    y_pred = prediction_frame["predicted_label"].tolist()
    report = classification_report(y_true, y_pred, labels=LABELS, output_dict=True, zero_division=0)
    classification = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)), 6),
        "per_label": {
            label: {key: round(float(report[label][key]), 6) for key in ("precision", "recall", "f1-score", "support")}
            for label in LABELS
        },
        "confusion_matrix_rows_gold_columns_predicted": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
        "label_order": list(LABELS),
        "retrieval_and_citation": {
            "gold_url_recall_at_top_k": round(float(prediction_frame["gold_url_retrieved_at_top_k"].mean()), 6),
            "citation_url_matches_gold_rate": round(float(prediction_frame["citation_url_matches_gold"].mean()), 6),
        },
        "latency_ms": {
            "mean": round(mean(latencies_ms), 4),
            "p50": round(percentile(latencies_ms, 0.50), 4),
            "p95": round(percentile(latencies_ms, 0.95), 4),
        },
    }
    return classification, prediction_frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/reranked_end_to_end.yaml")
    parser.add_argument("--split", type=Path, default=ROOT / "data/processed/vifactcheck_group_split/dev.parquet")
    parser.add_argument("--metrics", type=Path, default=ROOT / "outputs/metrics/reranked_e2e_dev.json")
    parser.add_argument("--predictions", type=Path, default=ROOT / "outputs/predictions/reranked_e2e_dev.csv")
    args = parser.parse_args()
    for attribute in ("config", "split", "metrics", "predictions"):
        value = getattr(args, attribute)
        setattr(args, attribute, value if value.is_absolute() else ROOT / value)

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    corpus_path = ROOT / config["paths"]["evidence_path"]
    frame = pd.read_parquet(args.split)
    pipeline = build_reranked_pipeline(config)
    classification, prediction_frame = run_evaluation(pipeline, frame)

    metrics = {
        "benchmark": "Reranked-local end-to-end (W3-08) -> PhoBERT",
        "purpose": "Đo tầng reranked-local tách riêng để so với BM25-local. Dev/test đã xem không phải bằng chứng chất lượng độc lập.",
        "scope": {
            "pipeline": "claim -> BM25 candidates -> source/time filter -> lexical+authority rerank -> dedup top-k -> PhoBERT -> policy -> citation",
            "retrieval_relevance": "URL-level proxy only.",
            "not_measured": "Web retrieval, fusion local+web, passage-level relevance.",
        },
        "artifacts": {
            "config_sha256": sha256(args.config),
            "corpus_sha256": sha256(corpus_path),
            "split_sha256": sha256(args.split),
            "predictions": str(args.predictions.relative_to(ROOT)),
        },
        "configuration": {
            "retriever": "reranked_metadata_w3_08",
            "candidate_k": config["retrieval"]["reranked"]["candidate_k"],
            "top_k": int(config["retrieval"]["top_k"]),
            "engine": config["verification"]["engine"],
            "model_path": config["verification"]["model_path"],
        },
        "evaluation_split": {"path": str(args.split.relative_to(ROOT)), "queries": len(prediction_frame)},
        "classification": classification,
    }
    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    prediction_frame.to_csv(args.predictions, index=False, encoding="utf-8")
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"macro_f1": classification["macro_f1"], "queries": len(prediction_frame)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
