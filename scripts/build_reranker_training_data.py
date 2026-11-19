"""Tạo dữ liệu train cho reranker PhoBERT (cross-encoder nhị phân: liên quan / không).

Nhãn "liên quan" KHÁC nhãn đúng/sai: đoạn bác bỏ claim vẫn là đoạn liên quan
(nó là nguồn nói về cùng sự việc). Vì vậy:

* dương (1): (Statement, Evidence gold) của claim SUPPORTED và REFUTED;
* âm khó (0): cửa sổ câu do ``HybridSourceRetriever`` xếp hạng cao nhưng
  thuộc bài KHÁC (URL khác) – đúng loại nhiễu reranker phải loại;
* âm trong bài (0): cửa sổ cùng bài nhưng gần như không chứa câu gold;
* âm ngẫu nhiên (0): một cửa sổ bất kỳ, giữ cho model không quên trường hợp dễ.
NEI bị loại: Evidence của NEI liên quan chủ đề nhưng không đủ, dễ gây nhiễu nhãn.

Train lấy từ split train; dev từ split dev. Cửa sổ âm không bao giờ lấy từ bài
thuộc split dev/test khi tạo train (tránh rò rỉ). Không đọc test.

    python scripts/build_reranker_training_data.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.hybrid_retriever import HybridSourceRetriever
from src.io_utils import load_evidence_jsonl
from src.vi_text import content_syllables


def coverage(gold: str, passage: str) -> float:
    terms = set(content_syllables(gold))
    return len(terms & set(content_syllables(passage))) / max(1, len(terms))


def build_pairs(frame: pd.DataFrame, retriever: HybridSourceRetriever, banned_urls: set[str], rng: random.Random,
                hard: int, in_article: int, random_negatives: int) -> pd.DataFrame:
    windows = [item for item in retriever.evidence_items if item.url not in banned_urls]
    by_url: dict[str, list] = {}
    for item in windows:
        by_url.setdefault(item.url, []).append(item)
    rows = []
    usable = frame[frame.labels.isin([0, 1]) & frame.Evidence.notna()]
    for record in usable.itertuples():
        claim, gold, url = str(record.Statement), str(record.Evidence), str(record.Url)
        rows.append({"query": claim, "passage": gold, "label": 1, "kind": "gold", "Url": url})
        candidates = retriever.search(claim, 30)
        negatives = [c.evidence for c in candidates if c.evidence.url != url and c.evidence.url not in banned_urls]
        for evidence in negatives[:hard]:
            rows.append({"query": claim, "passage": evidence.content, "label": 0, "kind": "hard_other_article", "Url": url})
        same = [w for w in by_url.get(url, []) if coverage(gold, w.content) < 0.3]
        for evidence in rng.sample(same, min(in_article, len(same))):
            rows.append({"query": claim, "passage": evidence.content, "label": 0, "kind": "same_article_other_part", "Url": url})
        for _ in range(random_negatives):
            evidence = rng.choice(windows)
            if evidence.url != url:
                rows.append({"query": claim, "passage": evidence.content, "label": 0, "kind": "random", "Url": url})
    return pd.DataFrame(rows).drop_duplicates(["query", "passage"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/reranker_v1")
    parser.add_argument("--hard", type=int, default=3)
    parser.add_argument("--in-article", type=int, default=1)
    parser.add_argument("--random", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    split_dir = ROOT / "data/processed/vifactcheck_group_split"
    train = pd.read_parquet(split_dir / "train.parquet")
    dev = pd.read_parquet(split_dir / "dev.parquet")
    test_urls = set(pd.read_parquet(split_dir / "test.parquet", columns=["Url"]).Url)
    if set(train.Url) & (set(dev.Url) | test_urls):
        raise ValueError("Train trùng URL với dev/test")
    retriever = HybridSourceRetriever(load_evidence_jsonl(ROOT / "data/evidence/vifactcheck_passages_v2.jsonl"), window=3)
    rng = random.Random(args.seed)
    train_pairs = build_pairs(train, retriever, set(dev.Url) | test_urls, rng, args.hard, args.in_article, args.random)
    dev_pairs = build_pairs(dev, retriever, test_urls | set(train.Url), rng, args.hard, args.in_article, args.random)

    args.output.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, frame in (("train.parquet", train_pairs), ("dev.parquet", dev_pairs)):
        path = args.output / name
        frame.to_parquet(path, index=False)
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "task": "binary relevance reranker (claim, passage) -> {0: unrelated, 1: related}",
        "files": files,
        "counts": {name: frame.kind.value_counts().to_dict() for name, frame in (("train", train_pairs), ("dev", dev_pairs))},
        "positives_from_labels": ["SUPPORTED", "REFUTED"],
        "test_read": False,
        "params": vars(args) | {"output": str(args.output)},
    }
    (args.output / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    archive = ROOT / "kaggle/reranker_v1.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in [*files, "MANIFEST.json"]:
            bundle.write(args.output / name, name)
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    print(f"Đã ghi {args.output} và {archive}")


if __name__ == "__main__":
    main()
