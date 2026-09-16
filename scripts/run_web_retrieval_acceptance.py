"""Run W3-05 live acceptance checks without writing an API key or page text.

Run this from the user's own PowerShell session, where TAVILY_API_KEY is set.
The resulting JSON is intentionally local-only and contains hashes rather than
claims or passage text, so it is safe to share with a reviewer if needed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.web_retriever import WebRetriever


DEFAULT_QUERIES = (
    "thông tin chính thức của Chính phủ Việt Nam",
    "World Health Organization Vietnam health guidance",
    "tin tức Việt Nam VnExpress",
)


def digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def load_config() -> tuple[dict[str, object], str]:
    config_path = ROOT / "configs" / "web_retrieval.yaml"
    raw = config_path.read_bytes()
    loaded = yaml.safe_load(raw)
    if not isinstance(loaded, dict):
        raise ValueError("Cấu hình web retrieval không hợp lệ")
    config = deepcopy(loaded)
    config["enabled"] = True
    config["cache"] = dict(config["cache"])
    config["cache"]["directory"] = str(ROOT / ".cache" / "web_retrieval")
    return config, digest(raw.decode("utf-8"))


def report_for_queries(queries: list[str], top_k: int) -> tuple[dict[str, object], bool]:
    config, config_sha256 = load_config()
    retriever = WebRetriever(config)
    allowed_domains = sorted(entry["host"] for entry in config["source_policy"]["allowlist"])
    runs: list[dict[str, object]] = []
    domains: set[str] = set()
    all_queries_returned_evidence = True
    seen_content_by_url: dict[str, set[str]] = {}
    duplicate_content = False

    for query in queries:
        evidence = retriever.search(query, top_k=top_k)
        items = []
        for item in evidence:
            source = item.evidence
            domains.add(source.domain)
            content_sha256 = digest(source.content)
            if content_sha256 in seen_content_by_url.setdefault(source.url, set()):
                duplicate_content = True
            seen_content_by_url[source.url].add(content_sha256)
            items.append({
                "passage_id": source.passage_id,
                "url": source.url,
                "domain": source.domain,
                "title": source.title,
                "source": source.source,
                "source_type": source.source_type,
                "fetched_at": source.retrieved_at,
                "content_sha256": content_sha256,
                "content_chars": len(source.content),
            })
        all_queries_returned_evidence = all_queries_returned_evidence and bool(items)
        runs.append({"query_sha256": digest(query), "status": retriever.last_status, "evidence": items})

    policy_ok = (
        len(queries) >= 3
        and all_queries_returned_evidence
        and len(domains) >= 2
        and domains.issubset(set(allowed_domains))
        and not duplicate_content
    )
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": config_sha256,
        "allowed_domains": allowed_domains,
        "queries": runs,
        "acceptance": {
            "minimum_queries": 3,
            "each_query_has_evidence": all_queries_returned_evidence,
            "minimum_distinct_domains": 2,
            "distinct_domains": sorted(domains),
            "all_domains_allowlisted": domains.issubset(set(allowed_domains)),
            "no_duplicate_content_per_url": not duplicate_content,
            "passed": policy_ok,
        },
    }
    return report, policy_ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", help="Query to validate; repeat at least three times.")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "web_retrieval" / "acceptance_report.json")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k phải lớn hơn 0")
    queries = args.query or list(DEFAULT_QUERIES)
    if len(queries) < 3:
        parser.error("Cần ít nhất ba --query để nghiệm thu W3-05")
    report, passed = report_for_queries(queries, args.top_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized acceptance report: {args.output}")
    print(f"Acceptance passed: {passed}")
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
