"""Chuẩn hóa VFND article-only cho nhánh content-risk E9.

VFND được tải riêng từ tag v1.1.1; không dùng social posts và không trộn
nhãn này với ViFactCheck claim--evidence labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "external" / "vfnd"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "vfnd_content" / "articles.parquet"
LABELS = {"Real": 0, "Fake": 1}


def normalise(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def build_records(source: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    root = source / "Fake_Real_Dataset"
    for label_name, label in LABELS.items():
        article_dir = root / label_name / "Article_Contents"
        if not article_dir.is_dir():
            raise FileNotFoundError(f"Không tìm thấy VFND article-only: {article_dir}")
        for path in sorted(article_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            title = normalise(raw.get("title"))
            body = normalise(raw.get("text"))
            url = normalise(raw.get("url"))
            domain = normalise(raw.get("source_domain")).lower()
            if not title or not body or not url or not domain:
                continue
            article_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            records.append({
                "article_id": article_id,
                "title": title,
                "body": body,
                "url": url,
                "source_domain": domain,
                "published_at": normalise(raw.get("date_publish")) or None,
                "label": label,
                "label_name": label_name.upper(),
                "source_file": path.name,
            })
    if not records:
        raise ValueError("Không có article VFND hợp lệ sau khi lọc")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=ROOT / "outputs" / "metrics" / "vfnd_content_audit.json")
    args = parser.parse_args()

    frame = pd.DataFrame(build_records(args.source))
    raw_records = len(frame)
    duplicate_urls = int(frame["url"].duplicated().sum())
    duplicate_texts = int((frame["title"] + "\n" + frame["body"]).duplicated().sum())
    for field in ("url", "article_id"):
        conflicting = frame.groupby(field)["label"].nunique().gt(1)
        if conflicting.any():
            raise ValueError(f"VFND article-only có {field} trùng nhưng khác nhãn")
    # Bản phát hành v1.1.1 có một article FAKE bị lặp nguyên URL/nội dung.
    # Giữ bản đầu tiên, nhưng lưu số lượng trong audit để không che giấu thay đổi.
    frame = frame.drop_duplicates(subset=["url"], keep="first")
    frame = frame.drop_duplicates(subset=["title", "body"], keep="first")
    if frame["source_domain"].isna().any():
        raise ValueError("VFND article-only thiếu source_domain")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    audit = {
        "dataset": "VFND article-only",
        "source_revision": "v1.1.1 / a52319a56236d810c8b03418c6721a26c004a117",
        "source_url": "https://github.com/VFND/VFND-vietnamese-fake-news-datasets/tree/v1.1.1",
        "license": "GPL-3.0",
        "task": "binary content-risk classification; separate from claim verification",
        "records_before_deduplication": raw_records,
        "records": int(len(frame)),
        "label_distribution": {str(key): int(value) for key, value in frame["label_name"].value_counts().sort_index().items()},
        "domains": int(frame["source_domain"].nunique()),
        "domains_per_label": {
            label: int(frame.loc[frame["label_name"] == label, "source_domain"].nunique())
            for label in sorted(frame["label_name"].unique())
        },
        "duplicate_urls": duplicate_urls,
        "duplicate_title_body": duplicate_texts,
        "note": "Domain is fully label-confounded in this release; E9 uses nested group CV by source_domain.",
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
