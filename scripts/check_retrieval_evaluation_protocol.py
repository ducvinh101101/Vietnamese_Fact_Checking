"""Offline checks for the W2-10 protocol config and frozen query manifest."""

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def validate(config: dict, manifest: dict) -> None:
    assert config["version"] == 1
    assert config["query_set"]["allow_ad_hoc_query_benchmark"] is False
    assert config["query_set"]["development_split"] == "dev"
    assert config["query_set"]["held_out_split"] == "test"
    assert config["metrics"]["cutoff"] == [3, 5]
    assert config["metrics"]["url_level_baseline"]["report"] == ["Recall@3", "Recall@5", "MRR@5", "latency"]
    qrels = config["metrics"]["passage_qrels"]
    assert qrels["required_for"] == ["nDCG@5", "passage_Recall@3", "passage_Recall@5", "passage_MRR@5"]
    assert qrels["grades"] == {2: "directly supports_or_refutes_claim", 1: "relevant_context_but_not_sufficient_alone", 0: "nonrelevant"}
    assert manifest["total_queries"] == 2156
    assert manifest["splits"]["dev"]["queries"] == 1080
    assert manifest["splits"]["test"]["queries"] == 1076
    assert manifest["cross_split_gold_url_overlap"] == 0
    assert manifest["relevance"]["passage_qrels"].startswith("Pending")


def main() -> None:
    config_path = ROOT / "configs/retrieval_evaluation.yaml"
    manifest_path = ROOT / "data/evaluation/vifactcheck_retrieval_query_set_v1_manifest.json"
    records_path = ROOT / "data/evaluation/vifactcheck_retrieval_query_set_v1.jsonl"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate(config, manifest)
    assert sha256(records_path) == manifest["records_sha256"]
    for name, digest in manifest["inputs_sha256"].items():
        assert sha256(ROOT / name) == digest
    print("W2-10 protocol valid: frozen dev/test query set, URL metrics and pending passage-qrels.")


if __name__ == "__main__":
    main()
