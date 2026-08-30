"""Tạo split 70/15/15 chống rò rỉ theo URL cho ViFactCheck."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from datasets import Dataset, load_from_disk
from sklearn.model_selection import StratifiedGroupKFold


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "vifactcheck"
OUTPUT_DIR = ROOT / "data" / "processed" / "vifactcheck_group_split"
REPORT = ROOT / "outputs" / "metrics" / "vifactcheck_group_split_report.json"
SEED = 42


def group_id(url: str) -> str:
    normalized = re.sub(r"\s+", " ", str(url).strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def distribution(frame: pd.DataFrame) -> dict[str, int]:
    return {str(label): int(count) for label, count in frame["labels"].value_counts().sort_index().items()}


def main() -> None:
    original = load_from_disk(str(RAW_DIR))
    frame = pd.concat([split.to_pandas() for split in original.values()], ignore_index=True)
    frame["group_id"] = frame["Url"].map(group_id)

    splitter = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=SEED)
    fold = pd.Series(index=frame.index, dtype="int64")
    for fold_number, (_, validation_index) in enumerate(splitter.split(frame, frame["labels"], groups=frame["group_id"])):
        fold.iloc[validation_index] = fold_number

    # 20 folds tương ứng gần đúng 5% mỗi fold: 14/3/3 = 70/15/15.
    split_map = {
        "train": set(range(0, 14)),
        "dev": set(range(14, 17)),
        "test": set(range(17, 20)),
    }
    split_frames = {name: frame[fold.isin(folds)].drop(columns=["group_id"]) for name, folds in split_map.items()}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, split_frame in split_frames.items():
        Dataset.from_pandas(split_frame, preserve_index=False).to_parquet(str(OUTPUT_DIR / f"{name}.parquet"))

    report = {
        "seed": SEED,
        "method": "StratifiedGroupKFold(n_splits=20); folds 14/3/3 for train/dev/test",
        "total_rows": len(frame),
        "total_unique_urls": int(frame["group_id"].nunique()),
        "splits": {
            name: {
                "rows": len(split_frame),
                "share": round(len(split_frame) / len(frame), 4),
                "unique_urls": int(split_frame["Url"].map(group_id).nunique()),
                "label_distribution": distribution(split_frame),
            }
            for name, split_frame in split_frames.items()
        },
        "cross_split_url_overlap": {
            "train__dev": len(set(split_frames["train"]["Url"].map(group_id)) & set(split_frames["dev"]["Url"].map(group_id))),
            "train__test": len(set(split_frames["train"]["Url"].map(group_id)) & set(split_frames["test"]["Url"].map(group_id))),
            "dev__test": len(set(split_frames["dev"]["Url"].map(group_id)) & set(split_frames["test"]["Url"].map(group_id))),
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
