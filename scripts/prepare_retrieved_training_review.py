"""Prepare TRAIN-only retrieved pairs for human labeling before fine-tuning.

A different source URL is NOT sufficient evidence for assigning NEI.
All retrieved pair labels stay blank until a reviewer reads the passage.
"""
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.io_utils import load_evidence_jsonl
from src.retriever import BM25Retriever


def main():
    directory = ROOT / "data/processed/vifactcheck_group_split"
    train = pd.read_parquet(directory / "train.parquet")
    held_urls = set(pd.read_parquet(directory / "dev.parquet").Url) | set(pd.read_parquet(directory / "test.parquet").Url)
    assert not set(train.Url) & held_urls
    corpus_path = ROOT / "data/evidence/vifactcheck_passages.jsonl"
    corpus = [item for item in load_evidence_jsonl(corpus_path) if item.url in set(train.Url)]
    retriever = BM25Retriever(corpus)
    # Fixed 60 claims per class, prefer distinct URLs; no selection using test failures.
    train = train.assign(selection_key=train.Statement.map(lambda s: hashlib.sha256(s.encode()).hexdigest()))
    chosen = pd.concat([train[train.labels == label].sort_values("selection_key").drop_duplicates("Url").head(60) for label in range(3)])
    rows = []
    for i, row in enumerate(chosen.itertuples(), 1):
        claim_id = hashlib.sha256(str(row.Statement).encode()).hexdigest()[:20]
        for rank, hit in enumerate(retriever.search(row.Statement, 3), 1):
            rows.append({"pair_id": claim_id + ":" + hit.evidence.passage_id,
                         "split": "train", "claim": row.Statement,
                         "claim_source_url": row.Url, "annotated_evidence": row.Evidence,
                         "original_gold_pair_label": int(row.labels),
                         "rank": rank, "passage_id": hit.evidence.passage_id,
                         "passage": hit.evidence.content, "passage_url": hit.evidence.url,
                         "bm25_score": hit.score, "reviewed_pair_label": "",
                         "reviewer": "", "review_notes": "", "review_status": "pending"})
        if i % 30 == 0:
            print(f"Prepared {i}/{len(chosen)} train claims", flush=True)
    output = ROOT / "data/evaluation/train_retrieved_pair_review.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("Review file exists; refusing to overwrite annotations")
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8-sig")
    report = {"claims": len(chosen), "pairs": len(rows), "train_corpus_passages": len(corpus),
              "heldout_urls_excluded": True, "ready_for_training": False,
              "reason": "Retrieved pairs require human relation labels; URL mismatch is not an NEI label.",
              "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    (ROOT / "outputs/metrics/train_retrieved_pair_review_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
