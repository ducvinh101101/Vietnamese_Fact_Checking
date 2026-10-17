"""Hệ thống dựng chung cho giao diện và CLI (src/system_builder.py). Không cần mạng/GPU."""

from __future__ import annotations

from datetime import date

import pytest

from src.schemas import Evidence, RetrievedEvidence
from src.system_builder import SystemOptions, build_system, load_dotenv


class FakeWeb:
    """Web retriever giả: trả một bài mới (có ngày) về giá xăng bán lẻ."""
    def __init__(self, published_at="2026-10-10T15:00:00+07:00"):
        self.published_at = published_at
        self.calls = []

    def search(self, claim, top_k=3):
        self.calls.append(claim)
        return [RetrievedEvidence(Evidence(
            document_id="web-doc-1", passage_id="web-1",
            content="Giá xăng RON 95 bán lẻ tăng 500 đồng/lít từ 15h chiều nay theo kỳ điều hành của liên bộ.",
            source="Báo Điện tử Chính phủ", url="https://baochinhphu.vn/gia-xang-tang.htm",
            published_at=self.published_at, source_type="government"), 1.0)]


class Exploding:
    def search(self, claim, top_k=3):
        raise RuntimeError("tavily down")


def test_options_reject_unknown_mode_and_bad_top_k():
    with pytest.raises(ValueError):
        SystemOptions(mode="cloud")
    with pytest.raises(ValueError):
        SystemOptions(top_k=0)


def test_local_mode_matches_evaluated_config_and_returns_json_contract():
    system = build_system(SystemOptions(mode="local", engine="rule_based"))
    assert system.mode == "local" and system.settings["top_k"] == 3
    response = system.check("Hà Nội là thủ đô của Việt Nam")
    assert response["schema_version"] == "w3-03/v1"
    assert response["verdict"]["label"] in {"SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"}
    assert all(item["origin"] == "local" for item in response["retrieval"]["evidence"])
    assert response["diagnostics"]["mode"] == "local"


def test_hybrid_uses_web_evidence_for_time_sensitive_claim_and_reports_gate():
    web = FakeWeb()
    system = build_system(SystemOptions(mode="hybrid", engine="rule_based", as_of=date(2026, 10, 11)),
                          web_retriever=web)
    response = system.check("Giá xăng tăng từ chiều nay")
    origins = {item["origin"] for item in response["retrieval"]["evidence"]}
    assert "web" in origins
    gate = response["diagnostics"]["temporal_gate"]
    assert gate["recency_class"] == "today" and gate["kept"] >= 1
    # truy vấn web được chèn ngày tham chiếu, claim gửi verifier giữ nguyên
    assert web.calls and "11/10/2026" in web.calls[0]
    assert response["diagnostics"]["web_enriched_query"].endswith("ngày 11/10/2026")


def test_hybrid_drops_stale_web_evidence_for_time_sensitive_claim():
    system = build_system(SystemOptions(mode="hybrid", engine="rule_based", as_of=date(2026, 10, 11)),
                          web_retriever=FakeWeb(published_at="2023-03-13T10:00:00+07:00"))
    response = system.check("Giá xăng tăng từ chiều nay")
    assert all(item["origin"] != "web" for item in response["retrieval"]["evidence"])
    assert response["verdict"]["label"] == "NOT_ENOUGH_INFO" and response["citations"] == []
    assert response["diagnostics"]["temporal_gate"]["dropped_stale"] >= 1


def test_hybrid_falls_back_to_local_when_web_errors():
    system = build_system(SystemOptions(mode="hybrid", engine="rule_based"), web_retriever=Exploding())
    response = system.check("Hà Nội là thủ đô của Việt Nam")
    assert "tavily down" in response["diagnostics"]["web_error"]


def test_hybrid_without_key_runs_local_only(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    system = build_system(SystemOptions(mode="hybrid", engine="rule_based"))
    assert system.settings["web"] is False and "TAVILY_API_KEY" in system.web_status
    assert system.check("Hà Nội là thủ đô của Việt Nam")["verdict"]["label"] in {
        "SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"}


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nXLNNTN_A=from_file\nXLNNTN_B='quoted'\n", encoding="utf-8")
    monkeypatch.setenv("XLNNTN_A", "from_env")
    monkeypatch.delenv("XLNNTN_B", raising=False)
    load_dotenv(env)
    import os
    assert os.environ["XLNNTN_A"] == "from_env" and os.environ["XLNNTN_B"] == "quoted"
    monkeypatch.delenv("XLNNTN_B", raising=False)
