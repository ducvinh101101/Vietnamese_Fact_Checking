"""Build a class-balanced RT-V2 train/dev bundle from the reviewed RT-V1 silver.

RT-V1 added far more NOT_ENOUGH_INFO than decisive AI-silver pairs.  This
builder preserves every original gold pair and deterministically caps each
AI-silver label at the least frequent reviewed label.  It never reads test
text into the bundle and refuses to overwrite an existing experiment.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_retrieval_finetune_bundle import merge_training


PAIR = ["Statement", "Evidence"]
LABELS = (0, 1, 2)


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def balanced_silver(combined: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int], int]:
    """Return all gold rows plus a deterministic, label-balanced silver subset."""
    gold = combined.loc[combined["label_origin"] == "original_gold_train"].copy()
    silver = combined.loc[combined["label_origin"] == "ai_silver"].copy()
    before = {str(label): int((silver["labels"] == label).sum()) for label in LABELS}
    cap = min(before.values())
    if cap == 0:
        raise ValueError("Each label needs at least one reviewed AI-silver pair")
    selected = pd.concat(
        [
            silver.loc[silver["labels"] == label].sample(n=cap, random_state=42 + label)
            for label in LABELS
        ],
        ignore_index=True,
    )
    output = pd.concat([gold, selected], ignore_index=True)
    if output.groupby(PAIR)["labels"].nunique().gt(1).any():
        raise ValueError("Balanced bundle contains conflicting exact pairs")
    return output, before, cap


def main() -> None:
    split_dir = ROOT / "data/processed/vifactcheck_group_split"
    silver_path = ROOT / "data/processed/reviewed_retrieval/ai_silver_v1.parquet"
    silver_manifest = json.loads(silver_path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if sha256(silver_path) != silver_manifest["output_sha256"]:
        raise ValueError("Silver file does not match export manifest")

    gold = pd.read_parquet(split_dir / "train.parquet")
    dev = pd.read_parquet(split_dir / "dev.parquet")
    test = pd.read_parquet(split_dir / "test.parquet", columns=["Url"])
    held_urls = set(dev["Url"]) | set(test["Url"])
    original, combined, conflicts, added = merge_training(
        gold, pd.read_parquet(silver_path), held_urls
    )
    balanced, before_counts, cap = balanced_silver(combined)

    output = ROOT / "data/processed/retrieval_finetune_v2_balanced"
    archive_path = ROOT / "kaggle/retrieval_finetune_v2_balanced.zip"
    if output.exists() or archive_path.exists():
        raise FileExistsError("RT-V2 bundle exists; do not overwrite an experiment")
    output.mkdir(parents=True)
    original.to_parquet(output / "gold_train.parquet", index=False)
    balanced.to_parquet(output / "train.parquet", index=False)
    shutil.copyfile(split_dir / "dev.parquet", output / "dev.parquet")
    conflicts.to_csv(output / "excluded_silver_conflicts.csv", index=False, encoding="utf-8-sig")

    files = [
        output / name
        for name in ("gold_train.parquet", "train.parquet", "dev.parquet", "excluded_silver_conflicts.csv")
    ]
    manifest = {
        "experiment": "RT-V2 class-balanced AI-silver augmentation",
        "source_train_sha256": sha256(split_dir / "train.parquet"),
        "silver_sha256": sha256(silver_path),
        "original_rows": len(gold),
        "rt_v1_clean_silver_rows": added,
        "balanced_silver_rows": int(len(balanced) - len(original)),
        "ai_silver_label_counts_before": before_counts,
        "ai_silver_per_label_cap": cap,
        "combined_rows": len(balanced),
        "combined_label_counts": {
            str(label): int((balanced["labels"] == label).sum()) for label in LABELS
        },
        "sample_weight": {"original_gold_train": 1.0, "ai_silver": 0.5},
        "selection": "Deterministic under-sampling of reviewed AI-silver by label; all original gold retained.",
        "heldout_url_check": "passed for claim and passage URLs; dev/test URLs excluded from train",
        "test_in_bundle": False,
        "files": {path.name: sha256(path) for path in files},
    }
    metadata = output / "MANIFEST.json"
    metadata.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files + [metadata]:
            archive.write(path, path.name)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"ZIP: {archive_path}")


if __name__ == "__main__":
    main()
