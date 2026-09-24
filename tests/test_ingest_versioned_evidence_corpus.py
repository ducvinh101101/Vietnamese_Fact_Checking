import importlib.util
import json
from pathlib import Path

import pytest


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "ingest_versioned_evidence_corpus.py"
    spec = importlib.util.spec_from_file_location("versioned_ingestion", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_ingestion_canonicalizes_deduplicates_and_keeps_honest_time_metadata(tmp_path):
    module = load_module()
    input_path = tmp_path / "input.jsonl"
    policy_path = tmp_path / "policy.yaml"
    record = {
        "document_id": "doc-1", "passage_id": "p-1", "article_id": "doc-1",
        "content": "  Nội dung đủ dài để kiểm tra khử trùng.  ",
        "url": "https://baochinhphu.vn/example-102230315123456.htm?utm_source=test",
    }
    duplicate = {**record, "passage_id": "p-2", "content": "Nội dung   đủ dài để kiểm tra khử trùng."}
    input_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in (record, duplicate)) + "\n", encoding="utf-8")
    policy_path.write_text("sources:\n  baochinhphu.vn:\n    source_type: government\n    authority_score: 0.95\n", encoding="utf-8")

    records, manifest = module.ingest(input_path, policy_path, "2026-09-16T11:00:00Z", "v2.0.0")

    assert len(records) == 1
    assert records[0]["url"] == "https://baochinhphu.vn/example-102230315123456.htm"
    assert records[0]["published_at"] == "2023-03-15T00:00:00Z"
    assert records[0]["retrieved_at"] == "2026-09-16T11:00:00Z"
    assert records[0]["source_type"] == "government"
    assert manifest["deduplication"]["removed_duplicates"] == 1


def test_ingestion_rejects_unreviewed_source_domain(tmp_path):
    module = load_module()
    input_path = tmp_path / "input.jsonl"
    policy_path = tmp_path / "policy.yaml"
    input_path.write_text(json.dumps({"document_id": "d", "passage_id": "p", "article_id": "d", "content": "text", "url": "https://unknown.example/a"}) + "\n", encoding="utf-8")
    policy_path.write_text("sources: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source policy"):
        module.ingest(input_path, policy_path, "2026-09-16T11:00:00Z", "v2.0.0")
