"""Validation helpers for the Streamlit runtime configuration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml


class ConfigValidationError(ValueError):
    """Raised when the runtime configuration cannot safely start the app."""


_REQUIRED_KEYS = (
    ("paths", "evidence_path"),
    ("retrieval", "top_k"),
    ("verification", "engine"),
    ("verification", "model_path"),
    ("verification", "vncorenlp_dir"),
    ("verification", "max_length"),
    ("verification", "support_threshold"),
    ("verification", "refute_markers"),
)


def load_runtime_config(path: str | Path) -> dict:
    """Load and validate the minimal schema required by the demo application."""
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigValidationError(f"Không thể đọc file cấu hình: {config_path}") from error
    except yaml.YAMLError as error:
        raise ConfigValidationError(f"config.yaml không hợp lệ: {error}") from error

    if not isinstance(raw, dict):
        raise ConfigValidationError("config.yaml phải chứa một đối tượng cấu hình.")
    for section, key in _REQUIRED_KEYS:
        group = raw.get(section)
        if not isinstance(group, Mapping) or key not in group:
            raise ConfigValidationError(f"config.yaml thiếu khóa bắt buộc: {section}.{key}")
    if not isinstance(raw["retrieval"]["top_k"], int) or raw["retrieval"]["top_k"] < 1:
        raise ConfigValidationError("config.yaml: retrieval.top_k phải là số nguyên dương.")
    if not isinstance(raw["verification"]["max_length"], int) or raw["verification"]["max_length"] < 1:
        raise ConfigValidationError("config.yaml: verification.max_length phải là số nguyên dương.")
    if not isinstance(raw["verification"]["refute_markers"], list):
        raise ConfigValidationError("config.yaml: verification.refute_markers phải là một danh sách.")
    return raw
