"""Tạo dữ liệu RT-V3: verifier 3 nhãn được train trên CỬA SỔ CÂU thay vì câu gold.

Vì sao: RT-V2 học trên (claim, Evidence gold) – Evidence trung vị ~190 ký tự –
nhưng pipeline kiểm tra nguồn đưa vào cửa sổ 3 câu (~450 ký tự). Lệch phân phối
này đã làm hỏng lần train reranker đầu tiên (xem docs/SOURCE_ATTRIBUTION.md).

Cách tạo (giữ nguyên nhãn và trọng số của bundle RT-V2):

* mỗi cặp (Statement, Evidence) → cửa sổ (cấp bài, 3 câu, ≤700 ký tự) chứa
  Evidence với độ phủ ≥ 0.8; không tìm được cửa sổ nào thì GIỮ cặp gốc;
* thêm NEI "liên quan nhưng không phải nguồn" (trọng số 0.5) cho khoảng 1/3 số
  claim SUPPORTED/REFUTED: cửa sổ xếp hạng cao nhưng phủ < 0.3 Evidence gold và
  < 0.6 từ của claim (tránh gán NEI cho đoạn thật ra có nhắc lại claim).

Train lấy từ bundle RT-V2 (đã loại URL dev/test); dev là split dev (cửa sổ hóa
cùng cách, cùng phần NEI bổ sung). Không đọc test.

    python scripts/build_verifier_window_data.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

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


def windowize(frame: pd.DataFrame, retriever: HybridSourceRetriever, banned: set[str], rng: random.Random,
              nei_fraction: float) -> tuple[pd.DataFrame, dict[str, int]]:
    rows, stats = [], {"windowed": 0, "kept_original": 0, "added_related_nei": 0}
    for record in frame.itertuples():
        claim, evidence, url = str(record.Statement), str(record.Evidence), str(record.Url)
        weight = float(getattr(record, "sample_weight", 1.0))
        origin = str(getattr(record, "label_origin", "original_gold"))
        hits = [hit.evidence for hit in retriever.search(evidence, 10) if hit.evidence.url not in banned]
        scored = sorted(((coverage(evidence, w.content), w) for w in hits), key=lambda pair: -pair[0])
        if scored and scored[0][0] >= 0.8:
            window = scored[0][1]
            prefer_same = [w for value, w in scored if value >= 0.8 and w.url == url]
            window = prefer_same[0] if prefer_same else window
            rows.append({"Statement": claim, "Evidence": window.content, "Url": url, "labels": int(record.labels),
                         "label_origin": origin, "sample_weight": weight, "kind": "gold_window"})
            stats["windowed"] += 1
        else:
            rows.append({"Statement": claim, "Evidence": evidence, "Url": url, "labels": int(record.labels),
                         "label_origin": origin, "sample_weight": weight, "kind": "original_pair"})
            stats["kept_original"] += 1
        if int(record.labels) in (0, 1) and rng.random() < nei_fraction:
            for hit in retriever.search(claim, 20):
                window = hit.evidence
                if window.url in banned:
                    continue
                if coverage(evidence, window.content) < 0.3 and coverage(claim, window.content) < 0.6:
                    rows.append({"Statement": claim, "Evidence": window.content, "Url": url, "labels": 2,
                                 "label_origin": "related_window_nei", "sample_weight": 0.5,
                                 "kind": "related_not_source"})
                    stats["added_related_nei"] += 1
                    break
    return pd.DataFrame(rows).drop_duplicates(["Statement", "Evidence"]).reset_index(drop=True), stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=ROOT / "data/processed/retrieval_finetune_v2_balanced")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/verifier_windows_v3")
    parser.add_argument("--nei-fraction", type=float, default=0.33)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    split_dir = ROOT / "data/processed/vifactcheck_group_split"
    train = pd.read_parquet(args.source / "train.parquet")
    dev = pd.read_parquet(split_dir / "dev.parquet")
    dev_urls = set(dev.Url)
    test_urls = set(pd.read_parquet(split_dir / "test.parquet", columns=["Url"]).Url)
    train_urls = set(pd.read_parquet(split_dir / "train.parquet", columns=["Url"]).Url) | set(train.Url)
    if set(train.Url) & (dev_urls | test_urls):
        raise ValueError("Train trùng URL với dev/test")
    retriever = HybridSourceRetriever(
        load_evidence_jsonl(ROOT / "data/evidence/vifactcheck_passages_v2.jsonl"), window=3, stride=1,
        max_chars=700, window_scope="document", use_query_generation=False,
    )
    rng = random.Random(args.seed)
    train_rows, train_stats = windowize(train, retriever, dev_urls | test_urls, rng, args.nei_fraction)
    dev_rows, dev_stats = windowize(dev, retriever, train_urls | test_urls, rng, args.nei_fraction)

    args.output.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, frame in (("train.parquet", train_rows), ("dev.parquet", dev_rows)):
        path = args.output / name
        frame.to_parquet(path, index=False)
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = lambda frame: {  # noqa: E731
        "labels": {str(k): int(v) for k, v in frame.labels.value_counts().sort_index().items()},
        "kinds": {str(k): int(v) for k, v in frame.kind.value_counts().items()},
        "median_chars_by_label": {str(k): float(v) for k, v in frame.groupby("labels").Evidence.apply(lambda x: x.str.len().median()).items()},
    }
    manifest = {
        "experiment": "RT-V3 verifier on sentence windows",
        "files": files, "source_bundle": str(args.source.relative_to(ROOT)),
        "window": {"sentences": 3, "stride": 1, "max_chars": 700, "scope": "document"},
        "train": summary(train_rows) | train_stats, "dev": summary(dev_rows) | dev_stats,
        "test_read": False, "params": {"nei_fraction": args.nei_fraction, "seed": args.seed},
    }
    (args.output / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("train", "dev")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
