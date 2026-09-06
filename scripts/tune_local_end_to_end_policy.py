"""Select rank-aware evidence aggregation only on the development split.

This is deliberately separate from W4-02: it never opens the held-out test
split.  It materializes each dev claim's BM25 top-k and calibrated verifier
probabilities, then chooses rank bias and abstention threshold by Macro-F1.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import yaml
from sklearn.metrics import classification_report, confusion_matrix, f1_score


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(ROOT / ".cache/huggingface"))

from src.io_utils import load_evidence_jsonl
from src.phobert_fact_checker import PhoBERTFactChecker
from src.retrieval_aware_policy import decide_rank_aware
from src.retriever import BM25Retriever


LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
ID_TO_LABEL = {0: "SUPPORTED", 1: "REFUTED", 2: "NOT_ENOUGH_INFO"}
RANK_BIASES = (0.0, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0)
THRESHOLDS = (0.0, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80)
OUTPUT_PREDICTIONS = ROOT / "outputs/predictions/e11_dev_rank_aware_candidates.csv"
OUTPUT_METRICS = ROOT / "outputs/metrics/e11_dev_rank_aware_policy.json"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def evaluate(frame: pd.DataFrame, rank_bias: float, threshold: float) -> dict[str, object]:
    predictions = [
        decide_rank_aware(json.loads(raw), rank_bias=rank_bias, decisive_min_confidence=threshold).label
        for raw in frame["candidate_probabilities"]
    ]
    truth = frame["gold_label"].tolist()
    report = classification_report(truth, predictions, labels=LABELS, output_dict=True, zero_division=0)
    return {
        "rank_bias": rank_bias,
        "decisive_min_confidence": threshold,
        "macro_f1": float(f1_score(truth, predictions, labels=LABELS, average="macro", zero_division=0)),
        "refuted_f1": float(report["REFUTED"]["f1-score"]),
        "nei_f1": float(report["NOT_ENOUGH_INFO"]["f1-score"]),
        "predictions": predictions,
        "report": report,
    }


def main() -> None:
    config_path = ROOT / "configs/config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    split_path = ROOT / "data/processed/vifactcheck_group_split/dev.parquet"
    corpus_path = ROOT / config["paths"]["evidence_path"]
    top_k = int(config["retrieval"]["top_k"])
    frame = pd.read_parquet(split_path)
    required = {"Statement", "Evidence", "Url", "labels"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Dev split thiếu cột: {sorted(missing)}")

    retriever = BM25Retriever(load_evidence_jsonl(corpus_path))
    checker = PhoBERTFactChecker(
        ROOT / config["verification"]["model_path"],
        ROOT / config["verification"]["vncorenlp_dir"],
        max_length=int(config["verification"]["max_length"]),
        temperature=float(config["verification"].get("temperature", 1.0)),
        decisive_min_confidence=0.0,
    )
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for number, row in enumerate(frame.itertuples(index=True), start=1):
        # Labels, URL and annotated evidence are not supplied to retrieval or verifier.
        retrieved = retriever.search(str(row.Statement), top_k=top_k)
        probabilities = checker.predict_probabilities_batch(
            str(row.Statement), [item.evidence.content for item in retrieved]
        )
        records.append({
            "source_row_id": str(row.Index),
            "gold_label": ID_TO_LABEL[int(row.labels)],
            "gold_url": str(row.Url),
            "claim": str(row.Statement),
            "annotated_evidence": str(row.Evidence),
            "candidate_probabilities": json.dumps(probabilities),
            "retrieved": json.dumps([
                {"rank": rank, "passage_id": item.evidence.passage_id, "url": item.evidence.url, "score": round(item.score, 8)}
                for rank, item in enumerate(retrieved, start=1)
            ], ensure_ascii=False),
        })
        if number % 50 == 0 or number == len(frame):
            print(f"Processed {number}/{len(frame)} dev claims", flush=True)

    candidates = pd.DataFrame(records)
    grid = [evaluate(candidates, bias, threshold) for bias in RANK_BIASES for threshold in THRESHOLDS]
    best = max(grid, key=lambda item: (item["macro_f1"], item["refuted_f1"], item["nei_f1"], -item["rank_bias"], -item["decisive_min_confidence"]))
    candidates["baseline_prediction"] = evaluate(candidates, 0.0, 0.0)["predictions"]
    candidates["selected_prediction"] = best["predictions"]
    candidates["selected_citation_rank"] = [
        decide_rank_aware(json.loads(raw), best["rank_bias"], best["decisive_min_confidence"]).evidence_index + 1
        for raw in candidates["candidate_probabilities"]
    ]
    OUTPUT_PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(OUTPUT_PREDICTIONS, index=False, encoding="utf-8")
    metrics = {
        "experiment": "E11-dev rank-aware local evidence aggregation",
        "protocol": "Grid selection on dev only; test split was not opened. Labels/evidence are withheld from runtime retrieval and verifier.",
        "artifacts": {
            "config_sha256_before_selection": sha256(config_path),
            "corpus_sha256": sha256(corpus_path),
            "dev_split_sha256": sha256(split_path),
            "candidates": str(OUTPUT_PREDICTIONS.relative_to(ROOT)),
        },
        "configuration": {"top_k": top_k, "temperature": float(config["verification"].get("temperature", 1.0))},
        "grid": [{key: item[key] for key in ("rank_bias", "decisive_min_confidence", "macro_f1", "refuted_f1", "nei_f1")} for item in grid],
        "baseline": {key: evaluate(candidates, 0.0, 0.0)[key] for key in ("rank_bias", "decisive_min_confidence", "macro_f1", "refuted_f1", "nei_f1")},
        "selected": {
            **{key: best[key] for key in ("rank_bias", "decisive_min_confidence", "macro_f1", "refuted_f1", "nei_f1")},
            "per_label": {
                label: {metric: round(float(best["report"][label][metric]), 6) for metric in ("precision", "recall", "f1-score", "support")}
                for label in LABELS
            },
            "confusion_matrix_rows_gold_columns_predicted": confusion_matrix(candidates["gold_label"], best["predictions"], labels=LABELS).tolist(),
        },
        "wall_seconds": round(time.perf_counter() - started, 4),
    }
    OUTPUT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline_macro_f1": metrics["baseline"]["macro_f1"], "selected": metrics["selected"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
