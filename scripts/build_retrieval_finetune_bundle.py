"""Build train/dev-only RT-V1 experiment inputs; never include test text in ZIP."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAIR = ["Statement", "Evidence"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge_training(gold, additions, held_urls):
    for frame in (gold, additions):
        if frame[PAIR + ["Url", "labels"]].isna().any().any():
            raise ValueError("Missing training fields")
        if not frame.labels.isin([0, 1, 2]).all():
            raise ValueError("Invalid labels")
        if set(frame.Url) & held_urls:
            raise ValueError("Held-out claim URL in train")
    if set(additions.passage_url) & held_urls:
        raise ValueError("Held-out passage URL in train")
    if not additions.label_origin.eq("ai_silver").all() or not additions.review_status.eq("ai_reviewed").all():
        raise ValueError("This experiment expects explicitly reviewed AI silver only")
    if (gold.groupby(PAIR).labels.nunique() > 1).any():
        raise ValueError("Original train contains conflicting exact pairs; adjudicate first")
    gold = gold.drop_duplicates(PAIR).copy()
    known = gold.set_index(PAIR).labels.to_dict()
    mixed = pd.concat([gold[PAIR + ["labels"]], additions[PAIR + ["labels"]]], ignore_index=True)
    conflict_keys = set(mixed.groupby(PAIR).labels.nunique().loc[lambda n: n > 1].index)
    conflicts = additions[[tuple(r) in conflict_keys for r in additions[PAIR].itertuples(index=False, name=None)]].copy()
    clean = additions[[tuple(r) not in conflict_keys and tuple(r) not in known for r in additions[PAIR].itertuples(index=False, name=None)]].drop_duplicates(PAIR).copy()
    gold["label_origin"] = "original_gold_train"
    gold["sample_weight"] = 1.0
    clean["sample_weight"] = 0.5
    columns = PAIR + ["Url", "labels", "label_origin", "sample_weight"]
    combined = pd.concat([gold[columns], clean[columns]], ignore_index=True)
    return gold[columns], combined, conflicts, len(clean)


def main():
    split_dir = ROOT / "data/processed/vifactcheck_group_split"
    silver_path = ROOT / "data/processed/reviewed_retrieval/ai_silver_v1.parquet"
    silver_manifest = json.loads(silver_path.with_suffix(".manifest.json").read_text())
    if sha256(silver_path) != silver_manifest["output_sha256"]:
        raise ValueError("Silver file does not match export manifest")
    gold = pd.read_parquet(split_dir / "train.parquet")
    dev = pd.read_parquet(split_dir / "dev.parquet")
    test_urls = set(pd.read_parquet(split_dir / "test.parquet", columns=["Url"]).Url)
    if set(dev.Url) & test_urls:
        raise ValueError("Dev/test URL overlap")
    original, combined, conflicts, added = merge_training(gold, pd.read_parquet(silver_path), set(dev.Url) | test_urls)
    output = ROOT / "data/processed/retrieval_finetune_v1"
    archive_path = ROOT / "kaggle/retrieval_finetune_v1.zip"
    if output.exists() or archive_path.exists():
        raise FileExistsError("RT-V1 bundle exists; do not overwrite an experiment")
    output.mkdir(parents=True)
    original.to_parquet(output / "gold_train.parquet", index=False)
    combined.to_parquet(output / "train.parquet", index=False)
    shutil.copyfile(split_dir / "dev.parquet", output / "dev.parquet")
    conflicts.to_csv(output / "excluded_silver_conflicts.csv", index=False, encoding="utf-8-sig")
    files = [output / f for f in ("gold_train.parquet", "train.parquet", "dev.parquet", "excluded_silver_conflicts.csv")]
    manifest = {"experiment": "RT-V1 AI-silver augmentation, not human-reviewed gold",
                "source_train_sha256": sha256(split_dir / "train.parquet"), "silver_sha256": sha256(silver_path),
                "original_rows": len(gold), "deduplicated_gold_rows": len(original), "added_silver_rows": added,
                "excluded_conflicting_silver_rows": len(conflicts), "combined_rows": len(combined), "dev_rows": len(dev),
                "combined_label_counts": combined.labels.value_counts().sort_index().to_dict(),
                "sample_weight": {"original_gold_train": 1.0, "ai_silver": 0.5},
                "heldout_url_check": "passed for claim and passage URLs; test URL column used only to exclude leakage",
                "test_in_bundle": False, "files": {p.name: sha256(p) for p in files}}
    metadata = output / "MANIFEST.json"
    metadata.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for p in files + [metadata]:
            archive.write(p, p.name)
    print(json.dumps(manifest, indent=2))
    print(f"ZIP: {archive_path}")


if __name__ == "__main__":
    main()
