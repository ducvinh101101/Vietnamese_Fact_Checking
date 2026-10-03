"""Run a reproducible technical smoke test for the W3-01 local pipeline.

This verifies claim -> BM25 retrieval -> PhoBERT verification -> citation
provenance. It is not an end-to-end quality benchmark.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(ROOT / ".cache/huggingface"))

from src.pipeline import FactCheckingPipeline


LABELS = {0: "SUPPORTED", 1: "REFUTED", 2: "NOT_ENOUGH_INFO"}
OUTPUT = ROOT / "outputs/metrics/w3_01_end_to_end_smoke.json"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def select_cases(frame: pd.DataFrame) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for label_id, label in LABELS.items():
        candidates = frame.loc[frame["labels"] == label_id].sort_values("index")
        if candidates.empty:
            raise ValueError(f"Test split thiếu label {label}")
        row = candidates.iloc[0]
        selected.append({
            "source_row_id": str(row["index"]),
            "expected_dataset_label": label,
            "claim": str(row["Statement"]),
        })
    return selected


def main() -> None:
    config_path = ROOT / "configs/config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    test_path = ROOT / "data/processed/vifactcheck_group_split/test.parquet"
    corpus_path = ROOT / config["paths"]["evidence_path"]
    frame = pd.read_parquet(test_path)
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
    )
    runs = []
    for case in select_cases(frame):
        result, retrieved = pipeline.run(str(case["claim"]))
        ids = {item.evidence.passage_id for item in retrieved}
        if result.label not in LABELS.values() or not 0 <= result.confidence <= 1:
            raise RuntimeError("Pipeline trả verdict/confidence không hợp lệ")
        if not set(result.evidence_ids).issubset(ids):
            raise RuntimeError("Citation không thuộc evidence đã truy xuất")
        runs.append({
            "source_row_id": case["source_row_id"],
            "expected_dataset_label": case["expected_dataset_label"],
            "observed_pipeline_label": result.label,
            "confidence": result.confidence,
            "citation_ids": result.evidence_ids,
            "retrieved": [
                {"passage_id": item.evidence.passage_id, "url": item.evidence.url, "score": round(item.score, 8)}
                for item in retrieved
            ],
        })
    payload = {
        "purpose": "Technical W3-01 smoke test; not accuracy/Macro-F1/retrieval benchmark.",
        "config_sha256": sha256(config_path),
        "corpus_sha256": sha256(corpus_path),
        "test_split_sha256": sha256(test_path),
        "corpus_passages": 5845,
        "top_k": int(config["retrieval"]["top_k"]),
        "engine": config["verification"]["engine"],
        "runs": runs,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"W3-01 smoke passed: {len(runs)} frozen claims, citation provenance verified.")


if __name__ == "__main__":
    main()
