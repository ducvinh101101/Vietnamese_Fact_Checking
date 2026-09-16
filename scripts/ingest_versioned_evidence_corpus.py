"""W3-07: create a versioned, deduplicated evidence corpus with provenance.

The source JSONL remains untouched.  ``retrieved_at`` records when this local
corpus snapshot was ingested, not when an article was published or crawled.
``published_at`` is populated only when an unambiguous date is encoded in a URL.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "evidence" / "vifactcheck_passages.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "evidence" / "vifactcheck_passages_v2.jsonl"
DEFAULT_MANIFEST = ROOT / "data" / "evidence" / "vifactcheck_passages_v2_manifest.json"
DEFAULT_POLICY = ROOT / "configs" / "evidence_source_policy.yaml"
WHITESPACE = re.compile(r"\s+")
URL_DATE = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])([0-3]\d)(?!\d)")
BAO_CHINH_PHU_DATE = re.compile(r"102(\d{2})(0[1-9]|1[0-2])([0-3]\d)")
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid"}


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return sha256(handle.read()).hexdigest()


def normalize_content(value: object) -> str:
    return WHITESPACE.sub(" ", str(value or "")).strip()


def canonicalize_url(value: object) -> str:
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"URL không hợp lệ: {value!r}")
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    hostname = parsed.hostname.lower()
    netloc = hostname if parsed.port in (None, 80, 443) else f"{hostname}:{parsed.port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), netloc, path, urlencode(query, doseq=True), ""))


def published_at_from_url(url: str) -> str | None:
    parsed = urlsplit(url)
    match = URL_DATE.search(parsed.path)
    if match:
        year, month, day = map(int, match.groups())
    elif parsed.hostname == "baochinhphu.vn" and (legacy := BAO_CHINH_PHU_DATE.search(parsed.path)):
        year, month, day = 2000 + int(legacy.group(1)), int(legacy.group(2)), int(legacy.group(3))
    else:
        return None
    try:
        return date(year, month, day).isoformat() + "T00:00:00Z"
    except ValueError:
        return None


def parse_utc(value: str) -> str:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("--retrieved-at phải có timezone UTC")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def ingest(input_path: Path, policy_path: Path, retrieved_at: str, version: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    sources = policy.get("sources", {}) if isinstance(policy, dict) else {}
    if not isinstance(sources, dict):
        raise ValueError("Source policy không có bảng sources")

    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    missing_published_at = 0
    source_counts: dict[str, int] = {}
    input_records = 0
    for line_number, line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        input_records += 1
        raw = json.loads(line)
        required = {"document_id", "passage_id", "article_id", "content", "url"}
        missing = required - raw.keys()
        if missing:
            raise ValueError(f"Dòng {line_number} thiếu {sorted(missing)}")
        content = normalize_content(raw["content"])
        if not content:
            raise ValueError(f"Dòng {line_number} có content rỗng")
        canonical_url = canonicalize_url(raw["url"])
        domain = urlsplit(canonical_url).hostname or ""
        source_metadata = sources.get(domain)
        if not isinstance(source_metadata, dict):
            raise ValueError(f"Domain {domain!r} không có source policy exact-host")
        fingerprint = (canonical_url, content.casefold())
        if fingerprint in seen:
            duplicates += 1
            continue
        seen.add(fingerprint)
        published_at = published_at_from_url(canonical_url)
        missing_published_at += published_at is None
        source_counts[domain] = source_counts.get(domain, 0) + 1
        records.append({
            "document_id": str(raw["document_id"]),
            "passage_id": str(raw["passage_id"]),
            "content": content,
            "source": str(raw.get("source") or domain),
            "url": canonical_url,
            "original_url": str(raw["url"]),
            "domain": domain,
            "article_id": str(raw["article_id"]),
            "title": raw.get("title"),
            "published_at": published_at,
            "retrieved_at": retrieved_at,
            "source_type": source_metadata["source_type"],
            "authority_score": source_metadata["authority_score"],
            "schema_version": "2.0",
            "corpus_version": version,
        })
    manifest = {
        "schema_version": "2.0",
        "corpus_version": version,
        "input": display_path(input_path),
        "input_sha256": sha256_file(input_path),
        "source_policy": display_path(policy_path),
        "source_policy_sha256": sha256_file(policy_path),
        "ingestion_script": display_path(Path(__file__).resolve()),
        "ingestion_script_sha256": sha256_file(Path(__file__).resolve()),
        "deduplication": {
            "key": "canonical_url + normalized_content_casefold",
            "input_records": input_records,
            "output_records": len(records),
            "removed_duplicates": duplicates,
            "original_records_preserved": True,
        },
        "metadata": {
            "retrieved_at": retrieved_at,
            "retrieved_at_semantics": "UTC time that the local corpus snapshot was ingested; not article publication/crawl time.",
            "published_at_from_url": "Only unambiguous validated YYYYMMDD or Bao Chinh Phu 102YYMMDD URL dates.",
            "missing_published_at": missing_published_at,
            "source_counts": dict(sorted(source_counts.items())),
        },
        "documents": len({record["article_id"] for record in records}),
        "urls": len({record["url"] for record in records}),
        "passages": len(records),
        "git_commit": git_commit(),
    }
    return records, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--retrieved-at", required=True, help="ISO 8601 timestamp with UTC offset, e.g. 2026-09-16T11:00:00Z")
    parser.add_argument("--version", default="v2.0.0")
    args = parser.parse_args()
    retrieved_at = parse_utc(args.retrieved_at)
    records, manifest = ingest(args.input, args.source_policy, retrieved_at, args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    manifest["corpus"] = display_path(args.output)
    manifest["corpus_sha256"] = sha256_file(args.output)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passages": manifest["passages"], "urls": manifest["urls"], "duplicates": manifest["deduplication"]["removed_duplicates"], "corpus_sha256": manifest["corpus_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
