import json
from pathlib import Path

import pytest
import yaml

from scripts.check_retrieval_evaluation_protocol import validate


ROOT = Path(__file__).resolve().parents[1]


def load_config():
    return yaml.safe_load((ROOT / "configs/retrieval_evaluation.yaml").read_text(encoding="utf-8"))


def load_manifest():
    return json.loads((ROOT / "data/evaluation/vifactcheck_retrieval_query_set_v1_manifest.json").read_text(encoding="utf-8"))


def test_protocol_contract():
    validate(load_config(), load_manifest())


def test_rejects_ad_hoc_queries_or_test_selection():
    config = load_config()
    config["query_set"]["allow_ad_hoc_query_benchmark"] = True
    with pytest.raises(AssertionError):
        validate(config, load_manifest())
    config = load_config()
    config["query_set"]["development_split"] = "test"
    with pytest.raises(AssertionError):
        validate(config, load_manifest())
