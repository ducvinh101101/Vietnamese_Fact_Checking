"""Giao diện Gradio (app_gradio.py): dựng được, render đúng nhãn, escape HTML từ nguồn."""

from __future__ import annotations

import pytest

gr = pytest.importorskip("gradio")

import app_gradio  # noqa: E402
from src.system_builder import SystemOptions, build_system  # noqa: E402


@pytest.fixture
def rule_based(monkeypatch):
    system = build_system(SystemOptions(mode="local", engine="rule_based"))
    monkeypatch.setattr(app_gradio, "get_system", lambda mode, as_of: system)
    return system


def test_ui_builds_with_all_modes_and_examples():
    demo = app_gradio.build_ui()
    assert isinstance(demo, gr.Blocks)
    assert set(app_gradio.MODES.values()) == {"local", "hybrid"}


def test_check_renders_verdict_citations_and_details(rule_based):
    claim = "Tổng thống Brazil Lula hoãn chuyến thăm 10 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn."
    verdict, citations, retrieved, summary, details = app_gradio.check(claim, "Kho local (đã đánh giá)", False, "")
    assert "verdict" in verdict and "BÁC BỎ" in verdict
    assert "Được trích dẫn" in citations and "vnexpress.net" in citations
    assert "Tìm thấy" in summary and details["settings"]["minimal_pair"] is True


def test_blank_claim_returns_empty_outputs(rule_based):
    assert app_gradio.check("   ", "Kho local (đã đánh giá)", False, "") == ("", "", "", "", {})


def test_evidence_html_is_escaped():
    item = {"passage_id": "p<1>", "content": "<script>alert(1)</script>", "score": 1.0, "source": "S&P",
            "url": "https://x.vn/a?b=1&c=\"2\"", "origin": "web"}
    html = app_gradio.render_evidence([item], {"p<1>"}, "trống")
    assert "<script>" not in html and "&lt;script&gt;" in html and "S&amp;P" in html
