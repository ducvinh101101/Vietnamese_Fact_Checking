"""Evaluate the frozen local BM25 -> PhoBERT pipeline once on the held-out test split.

The label and annotated evidence are read only after a pipeline result is
produced.  Retrieval relevance is URL-level because ViFactCheck supplies an
annotated source URL rather than passage-level relevance judgments.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import argparse
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

from src.pipeline import FactCheckingPipeline


LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
ID_TO_LABEL = {0: "SUPPORTED", 1: "REFUTED", 2: "NOT_ENOUGH_INFO"}
DEFAULT_SPLIT = ROOT / "data/processed/vifactcheck_group_split/test.parquet"
DEFAULT_METRICS = ROOT / "outputs/metrics/w4_02_local_end_to_end_test.json"
DEFAULT_PREDICTIONS = ROOT / "outputs/predictions/w4_02_local_end_to_end_test.csv"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/config.yaml")
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--use-final-config", action="store_true",
                        help="Áp verification.evidence_view / minimal_pair / guard trong config. Mặc định TẮT để "
                             "tái lập đúng baseline RT-V2 đã khóa (W4-02). Chỉ dùng cho lần chạy cuối trên test.")
    args = parser.parse_args()
    args.split = args.split if args.split.is_absolute() else ROOT / args.split
    args.metrics = args.metrics if args.metrics.is_absolute() else ROOT / args.metrics
    args.predictions = args.predictions if args.predictions.is_absolute() else ROOT / args.predictions
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    corpus_path = ROOT / config["paths"]["evidence_path"]
    frame = pd.read_parquet(args.split)
    required = {"Statement", "Evidence", "Url", "labels"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Test split thiếu cột: {sorted(missing)}")

    final = config["verification"] if args.use_final_config else {}
    pipeline = FactCheckingPipeline(
        evidence_path=str(corpus_path),
        top_k=int(config["retrieval"]["top_k"]),
        engine=config["verification"]["engine"],
        model_path=str(ROOT / config["verification"]["model_path"]),
        vncorenlp_dir=str(ROOT / config["verification"]["vncorenlp_dir"]),
        max_length=int(config["verification"]["max_length"]),
        temperature=float(config["verification"].get("temperature", 1.0)),
        decisive_min_confidence=float(config["verification"].get("decisive_min_confidence", 0.0)),
        retrieval_rank_bias=float(config["verification"].get("retrieval_rank_bias", 0.0)),
        aggregation_model_path=str(ROOT / config["verification"]["aggregation_model_path"]) if config["verification"].get("aggregation_model_path") else None,
        evidence_view=final.get("evidence_view", "passage"),
        minimal_pair=bool(final.get("minimal_pair", False)),
        guard=bool(final.get("guard", False)),
    )

    records: list[dict[str, object]] = []
    latencies_ms: list[float] = []
    started_all = time.perf_counter()
    for number, row in enumerate(frame.itertuples(index=True), start=1):
        # Do not pass label, URL, or annotated evidence into the pipeline.
        started = time.perf_counter()
        result, retrieved = pipeline.run(str(row.Statement))
        latency_ms = (time.perf_counter() - started) * 1_000
        latencies_ms.append(latency_ms)

        retrieved_rows = [
            {
                "rank": rank,
                "passage_id": item.evidence.passage_id,
                "url": item.evidence.url,
                "score": round(item.score, 8),
            }
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
        if number % 50 == 0 or number == len(frame):
            print(f"Processed {number}/{len(frame)} evaluation claims", flush=True)

    prediction_frame = pd.DataFrame(records)
    y_true = prediction_frame["gold_label"].tolist()
    y_pred = prediction_frame["predicted_label"].tolist()
    report = classification_report(y_true, y_pred, labels=LABELS, output_dict=True, zero_division=0)
    metrics = {
        "benchmark": "Local end-to-end BM25 -> PhoBERT",
        "purpose": "Evaluation of the explicitly selected split/config. If this is dev or a previously inspected test, it is NOT independent quality evidence. No gold labels/evidence are passed to the pipeline.",
        "scope": {
            "pipeline": "normalized claim -> local BM25 top-k -> PhoBERT per retrieved passage -> calibrated three-way decision -> cited passage",
            "retrieval_relevance": "URL-level only: a retrieved passage is relevant when its URL equals the annotated ViFactCheck evidence URL.",
            "not_measured": "Web retrieval, hybrid retrieval, passage-level relevance, human factual correctness beyond dataset labels.",
        },
        "artifacts": {
            "config_sha256": sha256(config_path),
            "corpus_sha256": sha256(corpus_path),
            "test_split_sha256": sha256(args.split),
            "predictions": str(args.predictions.relative_to(ROOT)),
        },
        "configuration": {
            "retriever": config["retrieval"]["method"],
            "top_k": int(config["retrieval"]["top_k"]),
            "engine": config["verification"]["engine"],
            "temperature": float(config["verification"].get("temperature", 1.0)),
            "decisive_min_confidence": float(config["verification"].get("decisive_min_confidence", 0.0)),
            "retrieval_rank_bias": float(config["verification"].get("retrieval_rank_bias", 0.0)),
            "evidence_view": final.get("evidence_view", "passage"),
            "minimal_pair": bool(final.get("minimal_pair", False)),
            "guard": bool(final.get("guard", False)),
            "use_final_config": args.use_final_config,
            "aggregation_model_path": config["verification"].get("aggregation_model_path"),
            "aggregation_model_sha256": sha256(ROOT / config["verification"]["aggregation_model_path"]) if config["verification"].get("aggregation_model_path") else None,
        },
        "evaluation_split": {"path": str(args.split.relative_to(ROOT)), "queries": len(prediction_frame)},
        "classification": {
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
            "macro_f1": round(float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)), 6),
            "per_label": {
                label: {key: round(float(report[label][key]), 6) for key in ("precision", "recall", "f1-score", "support")}
                for label in LABELS
            },
            "confusion_matrix_rows_gold_columns_predicted": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
            "label_order": list(LABELS),
        },
        "retrieval_and_citation": {
            "gold_url_recall_at_top_k": round(float(prediction_frame["gold_url_retrieved_at_top_k"].mean()), 6),
            "citation_url_matches_gold_rate": round(float(prediction_frame["citation_url_matches_gold"].mean()), 6),
            "note": "These are URL-level proxy metrics, not proof that the cited passage entails the claim.",
        },
        "latency_ms": {
            "mean": round(mean(latencies_ms), 4),
            "p50": round(percentile(latencies_ms, 0.50), 4),
            "p95": round(percentile(latencies_ms, 0.95), 4),
            "total_wall_seconds": round(time.perf_counter() - started_all, 4),
        },
    }
    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    prediction_frame.to_csv(args.predictions, index=False, encoding="utf-8")
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"macro_f1": metrics["classification"]["macro_f1"], "queries": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
