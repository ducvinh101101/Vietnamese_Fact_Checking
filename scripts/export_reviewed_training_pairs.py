"""Validate reviewed TRAIN passages against source data before training export."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABEL_IDS = {"SUPPORTED": 0, "REFUTED": 1, "NOT_ENOUGH_INFO": 2}


def validate_reviews(reviews, train, corpus, held_urls, allow_ai_reviewed=False):
    required = {"pair_id", "split", "claim", "claim_source_url", "passage_id", "passage", "passage_url",
                "reviewed_pair_label", "reviewer", "review_notes", "review_status"}
    if required - set(reviews):
        raise ValueError("Thiếu cột review bắt buộc")
    if reviews.pair_id.duplicated().any():
        raise ValueError("Trùng pair_id")
    allowed = {"approved", "ai_reviewed"} if allow_ai_reviewed else {"approved"}
    approved = reviews[reviews.review_status.isin(allowed)].copy()
    if approved.empty:
        raise ValueError("Chưa có cặp approved; không được huấn luyện từ nhãn pending")
    train_pairs = set(zip(train.Statement, train.Url))
    for row in approved.itertuples():
        if row.split != "train" or (row.claim, row.claim_source_url) not in train_pairs:
            raise ValueError("Claim không thuộc train")
        if row.claim_source_url in held_urls or row.passage_url in held_urls:
            raise ValueError("Phát hiện URL dev/test trong training review")
        evidence = corpus.get(row.passage_id)
        if evidence is None or evidence["content"] != row.passage or evidence.get("url", "") != row.passage_url:
            raise ValueError("Passage review không khớp corpus gốc")
        if row.reviewed_pair_label not in LABEL_IDS:
            raise ValueError("Nhãn reviewed_pair_label không hợp lệ")
        if any(pd.isna(value) or not str(value).strip() for value in (row.reviewer, row.review_notes)):
            raise ValueError("Cần reviewer và lý do cho mỗi nhãn approved")
    return pd.DataFrame({"Statement": approved.claim, "Evidence": approved.passage,
                         "Url": approved.claim_source_url, "labels": approved.reviewed_pair_label.map(LABEL_IDS),
                         "pair_id": approved.pair_id, "passage_id": approved.passage_id,
                         "passage_url": approved.passage_url, "reviewer": approved.reviewer,
                         "review_notes": approved.review_notes,
                         "review_status": approved.review_status,
                         "label_origin": approved.review_status.map({"approved": "human_review", "ai_reviewed": "ai_silver"})})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, default=ROOT / "data/evaluation/train_retrieved_pair_review.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/reviewed_retrieval/train_pairs.parquet")
    parser.add_argument("--allow-ai-reviewed", action="store_true", help="Explicitly export AI silver labels for experiments, NOT human gold")
    args = parser.parse_args()
    directory = ROOT / "data/processed/vifactcheck_group_split"
    train = pd.read_parquet(directory / "train.parquet")
    held_urls = set(pd.read_parquet(directory / "dev.parquet").Url) | set(pd.read_parquet(directory / "test.parquet").Url)
    corpus_path = ROOT / "data/evidence/vifactcheck_passages.jsonl"
    with corpus_path.open(encoding="utf-8") as handle:
        corpus = {p["passage_id"]: p for line in handle if line.strip() for p in [json.loads(line)]}
    reviewed = validate_reviews(pd.read_csv(args.reviews, keep_default_na=False), train, corpus, held_urls, args.allow_ai_reviewed)
    if (reviewed.groupby(["Statement", "Evidence"]).labels.nunique() > 1).any():
        raise ValueError("Conflicting labels for identical claim/passage; adjudication required")
    reviewed = reviewed.drop_duplicates(["Statement", "Evidence"])
    if args.output.exists() or args.output.with_suffix(".manifest.json").exists():
        raise FileExistsError("Output đã tồn tại; chọn đường dẫn phiên bản mới")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    reviewed.to_parquet(args.output, index=False)
    manifest = {"exported_pairs": len(reviewed), "label_origin_counts": reviewed.label_origin.value_counts().to_dict(),
                "allow_ai_reviewed": args.allow_ai_reviewed, "review_file_sha256": hashlib.sha256(args.reviews.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                "purpose": "Train additions; AI silver is not human gold. Merge with original train, never use for validation/test"}
    args.output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
