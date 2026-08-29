from pathlib import Path

import pytest

from src.pipeline import FactCheckingPipeline


def test_pipeline_returns_evidence_and_valid_label():
    root = Path(__file__).parents[1]
    pipeline = FactCheckingPipeline(str(root / "data/evidence/sample_evidence.jsonl"))
    result, evidence = pipeline.run("Có thay đổi lịch học trên phạm vi toàn quốc")
    assert result.label in {"SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"}
    assert len(evidence) == 3


def test_pipeline_rejects_blank_claim():
    root = Path(__file__).parents[1]
    pipeline = FactCheckingPipeline(str(root / "data/evidence/sample_evidence.jsonl"))
    with pytest.raises(ValueError, match="không được để trống"):
        pipeline.run("   ")
