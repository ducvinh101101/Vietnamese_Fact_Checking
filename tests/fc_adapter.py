"""Thin wrapper adapting the real pipeline to a single verify_claim(claim) callable."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from src.pipeline import FactCheckingPipeline
from src.runtime_config import load_runtime_config

ROOT = Path(__file__).resolve().parents[1]
_PIPELINE: FactCheckingPipeline | None = None
_INIT_ERROR: Exception | None = None
# Engine THỰC SỰ đang chạy sau khi dựng pipeline ("phobert" | "rule_based" | None).
# Quan trọng để test không "xanh giả": nếu yêu cầu phobert mà bị fallback rule_based
# thì phải lộ ra (xem tests/test_engine_integrity.py), thay vì âm thầm kiểm nhầm engine.
ACTIVE_ENGINE: str | None = None


def active_engine() -> str | None:
    """Engine thực sự của pipeline hiện tại (None nếu chưa dựng được)."""
    return ACTIVE_ENGINE


def _configure_utf8_console() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")


_configure_utf8_console()


def load_config():
    """Expose the production config loader to regression runners."""
    return load_runtime_config(ROOT / "configs" / "config.yaml")


def get_pipeline() -> FactCheckingPipeline:
    global _PIPELINE, _INIT_ERROR, ACTIVE_ENGINE
    if _PIPELINE is not None:
        return _PIPELINE
    if _INIT_ERROR is not None:
        raise _INIT_ERROR

    config_path = ROOT / "configs" / "config.yaml"
    config = load_runtime_config(config_path)

    verification = config["verification"]
    evidence_path = str(ROOT / config["paths"]["evidence_path"])
    top_k = int(config["retrieval"]["top_k"])
    support_threshold = float(verification.get("support_threshold", 0.45))
    refute_markers = verification.get("refute_markers")

    engine = os.environ.get("FC_ENGINE", verification.get("engine", "phobert"))

    try:
        if engine == "phobert":
            _PIPELINE = FactCheckingPipeline(
                evidence_path=evidence_path,
                top_k=top_k,
                support_threshold=support_threshold,
                refute_markers=refute_markers,
                engine="phobert",
                model_path=str(ROOT / verification["model_path"]),
                vncorenlp_dir=str(ROOT / verification["vncorenlp_dir"]),
                max_length=int(verification.get("max_length", 256)),
                temperature=float(verification.get("temperature", 1.0)),
                decisive_min_confidence=float(verification.get("decisive_min_confidence", 0.0)),
                retrieval_rank_bias=float(verification.get("retrieval_rank_bias", 0.0)),
                aggregation_model_path=str(ROOT / verification["aggregation_model_path"]) if verification.get("aggregation_model_path") else None,
            )
            ACTIVE_ENGINE = "phobert"
        else:
            _PIPELINE = FactCheckingPipeline(
                evidence_path=evidence_path,
                top_k=top_k,
                support_threshold=support_threshold,
                refute_markers=refute_markers,
                engine="rule_based",
            )
            ACTIVE_ENGINE = "rule_based"
        return _PIPELINE
    except Exception as exc:
        # If PhoBERT fails due to system DLL policy / missing Java and fallback allowed:
        if engine == "phobert" and os.environ.get("FC_FALLBACK_RULE_BASED", "1") == "1":
            print(f"[fc_adapter] PhoBERT initialization failed ({exc}). Falling back to rule_based for tests.")
            _PIPELINE = FactCheckingPipeline(
                evidence_path=evidence_path,
                top_k=top_k,
                support_threshold=support_threshold,
                refute_markers=refute_markers,
                engine="rule_based",
            )
            ACTIVE_ENGINE = "rule_based"
            return _PIPELINE
        _INIT_ERROR = exc
        raise exc


def verify_claim(claim: str) -> dict[str, Any]:
    """Execute end-to-end fact checking on a single claim string."""
    pipeline = get_pipeline()
    return pipeline.run_json(claim)
