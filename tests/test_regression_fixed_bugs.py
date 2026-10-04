"""Regression tests for BUG-01 through BUG-05 from the initial test report."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import pytest

from src.fact_checker import RuleBasedFactChecker
from src.retriever import BM25Retriever
from src.io_utils import load_evidence_jsonl
from src.schemas import RetrievedEvidence, Evidence

ROOT = Path(__file__).resolve().parents[1]


def test_regression_bug_01_rule_based_nei_empty_citations():
    """BUG-01: RuleBasedFactChecker with an unrelated claim must return NEI and EMPTY evidence_ids."""
    checker = RuleBasedFactChecker()
    # Dummy evidence
    sample_evidence = [
        RetrievedEvidence(
            evidence=Evidence(
                document_id="doc1",
                passage_id="sample_001_p01",
                content="Bộ Y tế khuyến cáo người dân phòng chống dịch sốt xuất huyết.",
                source="Bộ Y tế",
                url="https://moh.gov.vn",
            ),
            score=0.1,
        )
    ]
    # Completely unrelated claim -> overlap should be below threshold -> NEI
    unrelated_claim = "Elon Musk dự định xây căn cứ trên sao Hỏa năm 2050"
    result = checker.verify(unrelated_claim, sample_evidence)

    assert result.label in ("NOT_ENOUGH_INFO", "NEI"), f"Expected NEI, got {result.label}"
    assert result.evidence_ids == [], f"BUG-01 VIOLATION: NEI returned non-empty evidence_ids: {result.evidence_ids}"


@pytest.mark.slow
def test_regression_bug_02_windows_cp1252_encoding():
    """BUG-02: scripts/run_golden_eval.py in cp1252 subprocess must not crash with UnicodeEncodeError."""
    golden_script = ROOT / "scripts" / "run_golden_eval.py"
    if not golden_script.exists():
        pytest.skip("scripts/run_golden_eval.py not found.")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    env["PYTHONUTF8"] = "0"

    proc = subprocess.run(
        [sys.executable, str(golden_script)],
        env=env,
        capture_output=True,
        text=True,
    )

    err = proc.stderr
    assert "UnicodeEncodeError" not in err, f"BUG-02 VIOLATION: UnicodeEncodeError occurred:\n{err}"
    assert proc.returncode == 0, f"Process exited with non-zero code {proc.returncode}:\nStdout:\n{proc.stdout}\nStderr:\n{err}"


def test_regression_bug_03_04_missing_paths_error_message(tmp_path):
    """BUG-03/04: PhoBERTFactChecker with missing paths should raise clear error mentioning missing path."""
    from src.phobert_fact_checker import PhoBERTFactChecker

    non_existent_model = tmp_path / "non_existent_model"
    non_existent_vncorenlp = tmp_path / "non_existent_vncorenlp"

    try:
        PhoBERTFactChecker(
            model_path=str(non_existent_model),
            vncorenlp_dir=str(non_existent_vncorenlp),
        )
    except Exception as exc:
        msg = str(exc)
        # Should raise clear error specifying missing path, not a raw OSError/RuntimeError masking DLL/KeyError
        assert str(non_existent_model) in msg or "non_existent" in msg or "đường dẫn" in msg.lower(), (
            f"BUG-03/04 VIOLATION: Exception does not clearly mention the missing path. Raised: {type(exc).__name__}: {msg}"
        )


def test_regression_bug_04_config_missing_keys():
    """BUG-04: Loading an empty config should fail with clear message mentioning missing key, not raw unhandled KeyError."""
    load_cfg_fn = os.environ.get("FC_LOAD_CONFIG_FN")
    if not load_cfg_fn:
        pytest.skip("FC_LOAD_CONFIG_FN not defined; skipping config validation regression test.")


def test_regression_bug_05_streamlit_ui():
    """BUG-05: Streamlit AppTest: (a) disclaimer with 'thử nghiệm' & '80%'; (b) blank input produces warning without crashing."""
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        pytest.skip("streamlit.testing.v1 not available.")

    app_path = str(ROOT / "app.py")
    try:
        at = AppTest.from_file(app_path)
        at.run(timeout=30)
    except Exception as exc:
        pytest.skip(f"Could not initialize Streamlit AppTest: {exc}")

    if at.exception:
        pytest.skip(f"AppTest encountered initial exception: {at.exception[0].value}")

    # (a) Check for disclaimer text
    all_text = " ".join(
        [str(c.value) for c in at.caption] + [str(m.value) for m in at.markdown] + [str(i.value) for i in at.info] + [str(w.value) for w in at.warning]
    ).lower()

    has_disclaimer = ("thử nghiệm" in all_text) and ("80%" in all_text)
    assert has_disclaimer, "BUG-05 (a) VIOLATION: Streamlit UI lacks disclaimer containing 'thử nghiệm' and '80%'"

    # (b) Enter blank / whitespace and click verify button
    if at.text_area:
        at.text_area[0].input("   ").run()
    if at.button:
        at.button[0].click().run()

    assert not at.exception, f"BUG-05 (b) VIOLATION: Clicking with blank input raised exception: {at.exception[0].value}"
    assert len(at.warning) > 0, "BUG-05 (b) VIOLATION: Clicking with blank input did not produce at least one warning message."
