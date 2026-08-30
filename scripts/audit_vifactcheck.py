"""Tải và audit ViFactCheck; lưu dữ liệu thô và báo cáo tái lập được."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from datasets import load_dataset


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "vifactcheck"
REPORT = ROOT / "outputs" / "metrics" / "vifactcheck_audit.json"
DATASET_ID = "tranthaihoa/vifactcheck"


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def digest(value: str) -> str:
    return hashlib.sha256(normalized(value).encode("utf-8")).hexdigest()


def main() -> None:
    dataset = load_dataset(DATASET_ID)
    dataset.save_to_disk(str(RAW_DIR))
    split_frames = {name: split.to_pandas() for name, split in dataset.items()}
    required = {"Statement", "Context", "Evidence", "Url", "labels"}
    report: dict[str, object] = {
        "dataset_id": DATASET_ID,
        "splits": {},
        "missing_required_columns": {},
        "label_mapping": {"0": "SUPPORTED", "1": "REFUTED", "2": "NOT_ENOUGH_INFO"},
    }
    all_rows = []
    for name, frame in split_frames.items():
        missing = sorted(required - set(frame.columns))
        report["missing_required_columns"][name] = missing
        report["splits"][name] = {
            "rows": len(frame),
            "label_distribution": {str(key): int(value) for key, value in frame["labels"].value_counts().sort_index().items()},
            "missing_statement": int(frame["Statement"].isna().sum()),
            "missing_context": int(frame["Context"].isna().sum()),
            "missing_evidence": int(frame["Evidence"].isna().sum()),
            "duplicate_statement_within_split": int(frame["Statement"].map(normalized).duplicated().sum()),
            "duplicate_url_within_split": int(frame["Url"].map(normalized).duplicated().sum()),
        }
        current = frame[["Statement", "Context", "Evidence", "Url", "labels"]].copy()
        current["split"] = name
        current["url_hash"] = current["Url"].map(digest)
        current["context_hash"] = current["Context"].map(digest)
        all_rows.append(current)

    combined = pd.concat(all_rows, ignore_index=True)
    overlap: dict[str, dict[str, int]] = {}
    split_names = list(split_frames)
    for index, left in enumerate(split_names):
        for right in split_names[index + 1:]:
            left_rows = combined[combined["split"] == left]
            right_rows = combined[combined["split"] == right]
            overlap[f"{left}__{right}"] = {
                "shared_normalized_url": len(set(left_rows["url_hash"]) & set(right_rows["url_hash"])),
                "shared_normalized_context": len(set(left_rows["context_hash"]) & set(right_rows["context_hash"])),
            }
    report["cross_split_overlap"] = overlap
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
