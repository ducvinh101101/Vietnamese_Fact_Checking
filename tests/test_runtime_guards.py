from pathlib import Path

import pytest

from src.fact_checker import RuleBasedFactChecker
from src.phobert_fact_checker import PhoBERTFactChecker
from src.runtime_config import ConfigValidationError, load_runtime_config
from src.schemas import Evidence, RetrievedEvidence


def _evidence(content: str) -> RetrievedEvidence:
    return RetrievedEvidence(Evidence("doc", "passage-1", content), 1.0)


def test_rule_based_nei_has_no_decisive_citation():
    result = RuleBasedFactChecker(support_threshold=0.9).verify(
        "Thủ đô Việt Nam là Hà Nội", [_evidence("Giá vàng hôm nay tăng mạnh")]
    )
    assert result.label == "NOT_ENOUGH_INFO"
    assert result.evidence_ids == []


def test_phobert_fails_early_when_model_path_is_missing(tmp_path: Path):
    with pytest.raises(RuntimeError, match="Không tìm thấy thư mục model PhoBERT"):
        PhoBERTFactChecker(tmp_path / "missing-model", tmp_path)


def test_phobert_fails_early_when_vncorenlp_path_is_missing(tmp_path: Path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    with pytest.raises(RuntimeError, match="Không tìm thấy thư mục VnCoreNLP"):
        PhoBERTFactChecker(model_dir, tmp_path / "missing-vncorenlp")


def test_runtime_config_names_missing_key(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text("paths: {}\nretrieval: {}\nverification: {}\n", encoding="utf-8")
    with pytest.raises(ConfigValidationError, match=r"paths.evidence_path"):
        load_runtime_config(config)
