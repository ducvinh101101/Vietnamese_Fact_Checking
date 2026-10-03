"""Golden test (pytest) — chạy toàn bộ golden cases của chuỗi web -> xác minh.

Deterministic: dùng bằng chứng dựng sẵn, không mạng/PhoBERT. Dùng chung logic với
scripts/run_golden_eval.py để một nguồn sự thật."""

from __future__ import annotations

import sys
from pathlib import Path

# Cho phép import module trong scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_golden_eval import evaluate_case, load_cases


def test_all_golden_cases_pass():
    defaults, cases = load_cases()
    assert cases, "Không nạp được golden cases"
    failures = []
    for case in cases:
        r = evaluate_case(case, defaults)
        if not r["ok"]:
            failures.append(f"{r['id']}: " + "; ".join(r["failures"]))
    assert not failures, "Golden FAIL:\n" + "\n".join(failures)


def test_golden_covers_key_issues():
    """Bộ golden phải phủ các mắt xích trọng yếu của nhánh web."""
    _, cases = load_cases()
    ids = {c["id"] for c in cases}
    required = {
        "fresh_retail_support", "stale_only_nei", "mixed_direction_guard",
        "offtopic_world_oil_guard", "current_wide_window_support",
        "url_collapse_pick_retail", "undated_web_dropped", "web_empty_fallback_local",
    }
    missing = required - ids
    assert not missing, f"Golden thiếu case cho: {missing}"
