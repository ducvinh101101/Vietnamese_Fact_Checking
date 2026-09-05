"""Build the frozen W2-10 ViFactCheck retrieval query set and manifest."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/evidence/vifactcheck_passages.jsonl"
SPLITS = {
    "dev": ROOT / "data/processed/vifactcheck_group_split/dev.parquet",
    "test": ROOT / "data/processed/vifactcheck_group_split/test.parquet",
}
OUTPUT = ROOT / "data/evaluation/vifactcheck_retrieval_query_set_v1.jsonl"
MANIFEST = ROOT / "data/evaluation/vifactcheck_retrieval_query_set_v1_manifest.json"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def normalize_text(value: object) -> str:
    return re.sub(r"[^0-9a-zà-ỹ]+", " ", str(value).lower()).strip()


def exact_passage_matches(evidence: object, passages: list[dict[str, str]]) -> list[str]:
    normalized_evidence = normalize_text(evidence)
    if not normalized_evidence:
        return []
    return [
        passage["passage_id"]
        for passage in passages
        if normalized_evidence in normalize_text(passage["content"])
        or normalize_text(passage["content"]) in normalized_evidence
    ]


def load_corpus(path: Path) -> tuple[dict[str, list[dict[str, str]]], dict[str, str]]:
    by_url: dict[str, list[dict[str, str]]] = defaultdict(list)
    article_by_url: dict[str, str] = {}
    seen_passages: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = json.loads(line)
            required = {"passage_id", "content", "url", "article_id"}
            missing = required - raw.keys()
            if missing:
                raise ValueError(f"Corpus line {line_number} missing {sorted(missing)}")
            passage_id = str(raw["passage_id"])
            url = str(raw["url"])
            article_id = str(raw["article_id"])
            if passage_id in seen_passages:
                raise ValueError(f"Duplicate passage_id: {passage_id}")
            if not url:
                raise ValueError(f"Empty URL on passage {passage_id}")
            if url in article_by_url and article_by_url[url] != article_id:
                raise ValueError(f"URL maps to more than one article_id: {url}")
            seen_passages.add(passage_id)
            article_by_url[url] = article_id
            by_url[url].append({"passage_id": passage_id, "content": str(raw["content"])})
    return by_url, article_by_url


def build_records() -> tuple[list[dict[str, object]], dict[str, object]]:
    by_url, article_by_url = load_corpus(CORPUS)
    records: list[dict[str, object]] = []
    split_urls: dict[str, set[str]] = {}
    input_hashes = {str(CORPUS.relative_to(ROOT)): sha256(CORPUS)}
    for split, path in SPLITS.items():
        frame = pd.read_parquet(path)
        required = {"index", "Statement", "Evidence", "Url"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{split} split missing {sorted(missing)}")
        if frame["index"].duplicated().any() or frame["Statement"].isna().any() or frame["Url"].isna().any():
            raise ValueError(f"{split} split has duplicate IDs or missing required values")
        split_urls[split] = set(frame["Url"].astype(str))
        input_hashes[str(path.relative_to(ROOT))] = sha256(path)
        for row in frame.itertuples(index=False):
            source_row_id = str(row.index)
            gold_url = str(row.Url)
            if gold_url not in article_by_url:
                raise ValueError(f"Gold URL absent from corpus: {gold_url}")
            records.append({
                "query_id": f"vifactcheck:{split}:{source_row_id}",
                "query_set_version": "v1",
                "split": split,
                "source_row_id": source_row_id,
                "query": str(row.Statement),
                "gold_url": gold_url,
                "gold_article_id": article_by_url[gold_url],
                "silver_exact_passage_ids": exact_passage_matches(row.Evidence, by_url[gold_url]),
                "passage_qrels_status": "pending_human_review",
            })
    if split_urls["dev"] & split_urls["test"]:
        raise ValueError("Dev/test URLs overlap")
    if len({str(record["query_id"]) for record in records}) != len(records):
        raise ValueError("Query IDs are not unique")
    summary = {
        "schema_version": "1.0",
        "query_set_version": "v1",
        "relevance": {
            "url_level": "Gold URL/article ID is complete for every query.",
            "silver_exact_passage": "Exact normalized evidence-to-passage matches; candidate only, not human qrels.",
            "passage_qrels": "Pending independent human review before passage metrics/nDCG.",
        },
        "inputs_sha256": input_hashes,
        "splits": {
            split: {
                "queries": sum(record["split"] == split for record in records),
                "unique_gold_urls": len(split_urls[split]),
                "silver_exact_passage_queries": sum(record["split"] == split and bool(record["silver_exact_passage_ids"]) for record in records),
            }
            for split in SPLITS
        },
        "cross_split_gold_url_overlap": len(split_urls["dev"] & split_urls["test"]),
        "query_id_format": "vifactcheck:{split}:{source_row_id}",
        "split_roles": {"dev": "model/configuration selection", "test": "one held-out final report"},
    }
    return records, summary


def main() -> None:
    records, summary = build_records()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    summary["records_sha256"] = sha256(OUTPUT)
    summary["total_queries"] = len(records)
    summary["source_row_id_distribution"] = dict(Counter(record["split"] for record in records))
    MANIFEST.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"queries": len(records), "manifest": str(MANIFEST.relative_to(ROOT)), "splits": summary["splits"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
