"""Đọc lại trang báo cho một bản ghi web – KHÔNG gọi Tavily (0 credit).

Bản ghi (`--snapshot` của evaluate_source_attribution_realworld.py) lưu danh sách URL provider trả cho từng claim
(trace.search_results, ~20 URL/claim) nhưng pipeline chỉ đọc `max_pages` trang và giữ vài đoạn/trang. Script này
tải lại các trang đó (vẫn qua allowlist, robots.txt, chặn IP nội bộ) để:

* lưu **mọi đoạn của từng bài** (`documents`) cho bản tóm tắt cả bài (src/article_digest.py);
* thử đọc nhiều trang hơn (`--max-pages 6,10` → một bản ghi cho mỗi giá trị).

Trang nay không tải được (bài bị gỡ, lỗi mạng) → giữ các đoạn đã ghi trước đó của trang ấy.

    python scripts/reread_web_snapshot.py .cache/realdev_web_snapshot.jsonl --max-pages 6,10
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas import Evidence, RetrievedEvidence
from src.source_attribution_factory import load_config
from src.web_retriever import WebRetrievalError, WebRetriever


def provider_results(trace: dict) -> list[dict]:
    """Dựng lại danh sách kết quả provider theo đúng thứ tự xen kẽ các truy vấn như WebRetriever.search."""
    batches: dict[int, list[dict]] = defaultdict(list)
    for item in trace.get("search_results", []):
        batches[int(item.get("query_index", 0))].append(item)
    ordered = [sorted(batches[q], key=lambda item: int(item.get("rank", 0))) for q in sorted(batches)]
    width = max((len(batch) for batch in ordered), default=0)
    return [{"url": batch[i]["url"], "title": batch[i].get("title")}
            for i in range(width) for batch in ordered if i < len(batch) and batch[i].get("url")]


class MemoFetcher:
    """Tải mỗi URL một lần cho mọi claim/biến thể (bài trùng giữa các claim cùng sự việc)."""

    def __init__(self, fetch) -> None:
        self.fetch, self.cache, self.fetched = fetch, {}, 0

    def __call__(self, url: str, timeout: float):
        if url not in self.cache:
            self.fetched += 1
            try:
                self.cache[url] = ("ok", self.fetch(url, timeout))
            except WebRetrievalError as error:
                self.cache[url] = ("error", error)
        status, value = self.cache[url]
        if status == "error":
            raise value
        return value


def reread(record: dict, web: WebRetriever, top_k: int) -> dict:
    if record.get("status") != "ok" or not record.get("trace", {}).get("search_results"):
        return record
    old_trace = record["trace"]
    web.last_trace = {"queries": list(old_trace.get("queries", [])), "provider_error": old_trace.get("provider_error"),
                      "search_results": list(old_trace["search_results"]), "pages": []}
    results = web.read_pages(record["claim"], provider_results(old_trace), top_k)
    documents = dict(web.last_documents)
    # Trang đã đọc được trước đây mà nay lỗi → giữ đoạn cũ của trang đó.
    failed = {page["url"] for page in web.last_trace["pages"] if page.get("outcome") == "fetch_failed"}
    kept = [RetrievedEvidence(Evidence(**item["evidence"]), float(item["score"])) for item in record["results"]
            if item["evidence"]["url"] in failed or item["evidence"].get("document_id") in failed]
    for item in kept:
        documents.setdefault(item.evidence.document_id, []).append(item.evidence.content)
    merged = sorted([*results, *kept], key=lambda item: (-item.score, item.evidence.passage_id))[:top_k]
    return {"claim_id": record["claim_id"], "claim": record["claim"], "status": "ok" if merged else web.last_status,
            "trace": web.last_trace, "results": [{"evidence": asdict(i.evidence), "score": i.score} for i in merged],
            "documents": documents, "reread": {"kept_old_pages": len({i.evidence.document_id for i in kept})}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--max-pages", default="", help="vd. 6,10 – mỗi giá trị một bản ghi (mặc định: theo config)")
    parser.add_argument("--output-prefix", type=Path, default=None, help="mặc định: <snapshot> bỏ .jsonl")
    args = parser.parse_args()

    config = load_config()
    web_config = config["web_retrieval"]
    variants = [int(v) for v in args.max_pages.split(",") if v] or [int(web_config["extraction"]["max_pages"])]
    top_k = int(config["decision"]["candidate_k"])
    records = [json.loads(line) for line in args.snapshot.read_text(encoding="utf-8").splitlines() if line.strip()]
    prefix = args.output_prefix or args.snapshot.with_suffix("")
    memo = None
    for pages in variants:
        cfg = dict(web_config, extraction=dict(web_config["extraction"], max_pages=pages))
        web = WebRetriever(cfg, api_key="not-used-no-provider-call")
        memo = memo or MemoFetcher(web.page_fetcher)
        web.page_fetcher = memo
        out = Path(f"{prefix}_reread_p{pages}.jsonl")
        started = time.perf_counter()
        with out.open("w", encoding="utf-8") as handle:
            for index, record in enumerate(records, start=1):
                handle.write(json.dumps(reread(record, web, top_k), ensure_ascii=False) + "\n")
                if index % 20 == 0:
                    print(f"  p{pages}: {index}/{len(records)} claim, {memo.fetched} trang đã tải, "
                          f"{time.perf_counter() - started:.0f}s", flush=True)
        print(f"Đã ghi {out}")


if __name__ == "__main__":
    main()
