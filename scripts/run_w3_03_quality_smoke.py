"""Run the W3-03 no-evidence JSON output smoke check with the configured pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
sys.path.insert(0, str(ROOT))

from src.pipeline import FactCheckingPipeline  # noqa: E402


NO_EVIDENCE_CLAIM = "zxqv987xyz qqqzzzxvv"
OUTPUT = ROOT / "outputs" / "metrics" / "w3_03_json_output_smoke.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    config_path = ROOT / "configs" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verification = config["verification"]
    pipeline = FactCheckingPipeline(
        evidence_path=str(ROOT / config["paths"]["evidence_path"]),
        top_k=config["retrieval"]["top_k"],
        engine=verification["engine"],
        model_path=str(ROOT / verification["model_path"]),
        vncorenlp_dir=str(ROOT / verification["vncorenlp_dir"]),
        max_length=verification["max_length"],
        temperature=verification.get("temperature", 1.0),
        decisive_min_confidence=verification.get("decisive_min_confidence", 0.0),
        retrieval_rank_bias=verification.get("retrieval_rank_bias", 0.0),
        aggregation_model_path=str(ROOT / verification["aggregation_model_path"])
        if verification.get("aggregation_model_path") else None,
    )
    response = pipeline.run_json(NO_EVIDENCE_CLAIM)
    if response["verdict"]["label"] != "NOT_ENOUGH_INFO":
        raise RuntimeError("No-evidence smoke phải trả NOT_ENOUGH_INFO")
    if response["citations"]:
        raise RuntimeError("No-evidence smoke không được trả citation")
    if response["retrieval"]["positive_score_count"] != 0:
        raise RuntimeError("No-evidence smoke không được có evidence điểm dương")

    report = {
        "purpose": "W3-03 JSON/citation/no-evidence technical smoke; not a quality benchmark.",
        "config_sha256": sha256(config_path),
        "corpus_sha256": sha256(ROOT / config["paths"]["evidence_path"]),
        "claim_sha256": hashlib.sha256(NO_EVIDENCE_CLAIM.encode("utf-8")).hexdigest(),
        "schema_version": response["schema_version"],
        "verdict": response["verdict"],
        "retrieved_count": response["retrieval"]["retrieved_count"],
        "positive_score_count": response["retrieval"]["positive_score_count"],
        "citation_count": len(response["citations"]),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("W3-03 smoke passed: no-evidence response is NEI with no citations.")


if __name__ == "__main__":
    main()
