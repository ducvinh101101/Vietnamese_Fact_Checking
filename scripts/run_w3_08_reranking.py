"""Generate reproducible W3-08 reranked top-k evidence for frozen dev queries."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.io_utils import load_evidence_jsonl
from src.reranked_retriever import MetadataRerankedRetriever, generate_query
from src.retriever import BM25Retriever

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/reranked_retrieval.yaml")
    parser.add_argument("--queries", type=Path, default=ROOT / "data/evaluation/vifactcheck_retrieval_query_set_v1.jsonl")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/w3_08_reranked_dev_top3.jsonl")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    retriever = MetadataRerankedRetriever(BM25Retriever(load_evidence_jsonl(ROOT / config["corpus"])), config)
    records = [json.loads(line) for line in args.queries.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = [row for row in records if row["split"] == args.split]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected:
            query = generate_query(str(row["query"]))
            items = retriever.search(query, args.top_k)
            handle.write(json.dumps({"query_id": row["query_id"], "query": query, "results": [{"passage_id": item.evidence.passage_id, "url": item.evidence.url, "domain": item.evidence.domain, "published_at": item.evidence.published_at, "source_type": item.evidence.source_type, "score": round(item.score, 8)} for item in items]}, ensure_ascii=False) + "\n")
    print(f"W3-08 wrote {len(selected)} {args.split} queries to {args.output}")
if __name__ == "__main__": main()
