"""Chạy app.py thật bằng Streamlit AppTest, thay pipeline nặng (PhoBERT, Tavily) bằng kho nhỏ + web giả."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest

import src.source_attribution_factory as factory
from src.hybrid_retriever import FusedRetriever, HybridSourceRetriever
from src.schemas import Evidence
from src.source_attribution import AttributionThresholds, SourceAttributionPipeline
from src.source_reranker import LexicalSourceScorer

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CORPUS = [
    Evidence(document_id="d1", passage_id="d1-p1", source="Tuổi Trẻ", url="https://tuoitre.vn/b", domain="tuoitre.vn",
             source_type="news", content="Giá xăng RON 95 giảm 500 đồng mỗi lít từ chiều nay. Liên Bộ điều hành."),
    Evidence(document_id="d2", passage_id="d2-p1", source="Thanh Niên", url="https://thanhnien.vn/c",
             domain="thanhnien.vn", source_type="news",
             content="Đội tuyển Việt Nam thắng Thái Lan 2-0 tại Mỹ Đình. Huấn luyện viên hài lòng."),
]


class WebRetriever:
    """Web giả: trạng thái lần lượt lấy từ ``statuses`` (lặp lại phần tử cuối)."""

    def __init__(self, statuses):
        self.statuses, self.calls, self.last_status = list(statuses), 0, "not_run"

    def search(self, claim, top_k=3):
        self.last_status = self.statuses[min(self.calls, len(self.statuses) - 1)]
        self.calls += 1
        return []


def start_app(monkeypatch, statuses=("ok",)):
    web = WebRetriever(statuses)

    def build_pipeline(*_args, **_kwargs):
        retriever = FusedRetriever([HybridSourceRetriever(CORPUS, window=1), web])
        return SourceAttributionPipeline(retriever, LexicalSourceScorer(), None,
                                         AttributionThresholds(relevance=0.4, lexical_support=0.6))

    monkeypatch.setattr(factory, "build_pipeline", build_pipeline)
    monkeypatch.setattr(factory, "build_verifier", lambda *_a, **_k: None)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at, web


def check(at, claim):
    at.text_area(key="claim").input(claim)
    next(button for button in at.button if button.label == "Kiểm tra nguồn").click()
    at.run()
    assert not at.exception, at.exception
    return at.session_state["result"]["response"]


@pytest.fixture(autouse=True)
def isolate_app():
    """Xóa cache Streamlit; khôi phục biến môi trường (app.py gọi load_dotenv → TAVILY_API_KEY)."""
    import os

    import streamlit as st

    environ = dict(os.environ)
    st.cache_data.clear()
    st.cache_resource.clear()
    yield
    st.cache_data.clear()
    st.cache_resource.clear()
    os.environ.clear()
    os.environ.update(environ)


def test_second_check_uses_the_newly_typed_claim(monkeypatch):
    at, _web = start_app(monkeypatch)
    first = check(at, "Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert first["verdict"]["label"] == "SOURCE_FOUND"
    second = check(at, "Việt Nam thắng Thái Lan 2-0 tại Mỹ Đình")
    assert at.session_state["result"]["claim"] == "Việt Nam thắng Thái Lan 2-0 tại Mỹ Đình"
    assert second["citations"][0]["domain"] == "thanhnien.vn"


def test_web_failure_retries_once_warns_and_is_not_cached(monkeypatch):
    at, web = start_app(monkeypatch, ["pages_unreachable"])
    response = check(at, "Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert response["retrieval"]["web_status"] == "pages_unreachable"
    assert web.calls == 2  # lần đầu + thử lại một lần
    assert any("chưa tra được web" in warning.value for warning in at.warning)
    check(at, "Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert web.calls == 4  # kết quả lỗi không được cache → tra lại


def test_transient_failure_then_success_is_cached_without_warning(monkeypatch):
    at, web = start_app(monkeypatch, ["local_only", "ok"])
    response = check(at, "Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert response["retrieval"]["web_status"] == "ok"
    assert not any("chưa tra được web" in warning.value for warning in at.warning)
    check(at, "Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert web.calls == 2  # lần thành công đã được cache


def test_rate_limit_is_not_retried(monkeypatch):
    at, web = start_app(monkeypatch, ["rate_limited"])
    check(at, "Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert web.calls == 1
    assert any("giới hạn số lần tìm web" in warning.value for warning in at.warning)
