"""Offline integrity checks for the W3-07 versioned evidence corpus."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from scripts.ingest_versioned_evidence_corpus import canonicalize_url, normalize_content


CORPUS = ROOT / "data" / "evidence" / "vifactcheck_passages_v2.jsonl"
MANIFEST = ROOT / "data" / "evidence" / "vifactcheck_passages_v2_manifest.json"
POLICY = ROOT / "configs" / "evidence_source_policy.yaml"


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return sha256(handle.read()).hexdigest()


def validate(corpus_path: Path = CORPUS, manifest_path: Path = MANIFEST, policy_path: Path = POLICY) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    allowed = set(policy["sources"])
    assert manifest["schema_version"] == "2.0"
    assert manifest["corpus_sha256"] == sha256_file(corpus_path)
    assert manifest["source_policy_sha256"] == sha256_file(policy_path)
    assert manifest["deduplication"]["key"] == "canonical_url + normalized_content_casefold"
    assert manifest["metadata"]["retrieved_at_semantics"].startswith("UTC time")

    seen: set[tuple[str, str]] = set()
    passage_ids: set[str] = set()
    rows = 0
    missing_published_at = 0
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows += 1
        required = {"document_id", "passage_id", "content", "url", "original_url", "domain", "article_id", "retrieved_at", "source_type", "authority_score", "schema_version", "corpus_version"}
        assert required.issubset(row)
        assert row["passage_id"] not in passage_ids
        passage_ids.add(row["passage_id"])
        assert row["domain"] in allowed
        assert row["source_type"] == policy["sources"][row["domain"]]["source_type"]
        assert row["authority_score"] == policy["sources"][row["domain"]]["authority_score"]
        assert row["retrieved_at"] == manifest["metadata"]["retrieved_at"]
        assert row["url"] == canonicalize_url(row["original_url"])
        fingerprint = (row["url"], normalize_content(row["content"]).casefold())
        assert fingerprint not in seen
        seen.add(fingerprint)
        missing_published_at += row["published_at"] is None
    assert rows == manifest["passages"]
    assert missing_published_at == manifest["metadata"]["missing_published_at"]
    return manifest


def main() -> None:
    manifest = validate()
    print(f"W3-07 corpus valid: {manifest['passages']} passages, {manifest['urls']} URLs, {manifest['deduplication']['removed_duplicates']} duplicate removed.")


if __name__ == "__main__":
    main()
