"""Giao diện Streamlit kiểm chứng thông tin tiếng Việt.

    py -3.13 -m streamlit run app.py

Hai chế độ (dựng chung bởi src/system_builder.py, giống hệt CLI):
* Kho local — pipeline đã đánh giá trên test (BM25 -> PhoBERT RT-V2 ensemble + minimal-pair).
* Local + web — thêm Tavily qua allowlist, neo thời gian cho claim thời sự, gộp URL, guard.
"""

from datetime import date
from pathlib import Path

import streamlit as st

from src.demo_cases import DEMO_CASES
from src.runtime_config import ConfigValidationError, load_runtime_config
from src.system_builder import FactCheckSystem, SystemOptions, build_system, load_dotenv


ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")   # TAVILY_API_KEY đặt trong .env được nhận mà không cần set tay

MODE_LABELS = {
    "local": "Kho local (đã đánh giá)",
    "hybrid": "Local + web (Tavily, allowlist)",
}
MODEL_LABELS = {
    "phobert": "PhoBERT Đề tài (Cục bộ CPU, < 0.3s)",
    "gemma": "LLM Gemma 4 (Google Cloud, Suy luận sâu)",
}
EXAMPLES = {"— Chọn ví dụ —": ""} | {
    f"{case['id']} · {case['title']} (kỳ vọng {case['expected']}{', chế độ web' if case['mode'] == 'hybrid' else ''})":
        case["claim"]
    for case in DEMO_CASES
}
LABEL_STYLE = {
    "SUPPORTED": ("✅", "success", "Bằng chứng ỦNG HỘ phát biểu"),
    "REFUTED": ("❌", "error", "Bằng chứng BÁC BỎ phát biểu"),
    "NOT_ENOUGH_INFO": ("❔", "info", "CHƯA ĐỦ bằng chứng để kết luận"),
}


@st.cache_resource(show_spinner="Đang nạp mô hình và kho bằng chứng…")
def get_system(mode: str, engine: str = "phobert", as_of: date | None = None) -> FactCheckSystem:
    config = load_runtime_config(ROOT / "configs" / "config.yaml")
    return build_system(SystemOptions(mode=mode, engine=engine, as_of=as_of), config=config, root=ROOT)


@st.cache_data(show_spinner=False, ttl=900)
def run_cached(mode: str, engine: str, claim: str, as_of: date | None = None) -> dict[str, object]:
    """Cache response JSON-safe theo (chế độ, model, claim); model được cache riêng. Web: hết hạn 15 phút."""
    return get_system(mode, engine, as_of).check(claim)


def show_evidence(item: dict, key_prefix: str) -> None:
    origin = "🌐 web" if item.get("origin") == "web" else "🗂️ local"
    st.markdown(f"{origin} · `{item['passage_id']}` · điểm `{float(item['score']):.2f}`")
    st.write(str(item["content"]))
    st.caption(
        f"{item['source']} · {item.get('domain') or 'domain không rõ'} · {item.get('source_type')} · "
        f"xuất bản: {item.get('published_at') or 'không rõ'} · truy xuất: {item.get('retrieved_at') or 'không rõ'}"
    )
    if item["url"]:
        st.link_button("Mở URL nguồn", str(item["url"]), key=f"{key_prefix}-{item['passage_id']}")


st.set_page_config(page_title="Kiểm chứng thông tin tiếng Việt", page_icon="🔎", layout="wide")
st.title("🔎 Kiểm chứng thông tin tiếng Việt")
st.caption("Retrieval → verifier (PhoBERT / LLM Gemma 4) → citation. Kết quả là hỗ trợ tham khảo; luôn mở nguồn gốc để kiểm tra.")
st.warning("⚠️ Bản thử nghiệm nghiên cứu, chưa xác nhận 80% ngoài thực tế. Luôn kiểm tra đối chiếu nguồn gốc trích dẫn.")

with st.sidebar:
    st.header("Cấu hình")
    model_engine = st.radio("Mô hình phán quyết", list(MODEL_LABELS), format_func=MODEL_LABELS.get)
    mode = st.radio("Nguồn bằng chứng", list(MODE_LABELS), format_func=MODE_LABELS.get)
    as_of = None
    if mode == "hybrid":
        if st.checkbox("Đặt ngày tham chiếu (mặc định: hôm nay)"):
            as_of = st.date_input("Ngày tham chiếu", value=date.today())
        st.caption("Claim thời sự (hôm nay, hiện nay, chức danh đương nhiệm…) chỉ nhận bằng chứng "
                   "đủ mới: theo ngày ≤ 10 ngày, hiện tại ≤ 365 ngày. Không rõ ngày đăng → bị loại.")
    st.divider()
    st.markdown(
        "**Chế độ kho local** là cấu hình đã đo trên test ViFactCheck: Macro-F1 **72,3%** "
        "(1.076 claim; test đã dùng nhiều lần nên là số tham khảo).\n\n"
        "**Chế độ web** chưa có phép đo trên tập có nhãn; dùng để minh họa claim thời sự."
    )
    st.caption("Đổi config/model: menu ⋮ → Clear cache (phím C), rồi chạy lại.")

example = st.selectbox("Ví dụ nhanh", list(EXAMPLES))
claim = st.text_area("Phát biểu cần kiểm chứng", value=EXAMPLES[example],
                     placeholder="Nhập một phát biểu tiếng Việt…", max_chars=2000)
if st.button("Kiểm chứng", type="primary"):
    if not claim.strip():
        st.warning("Vui lòng nhập phát biểu cần kiểm chứng.")
    else:
        try:
            system = get_system(mode, model_engine, as_of)
            if system.fallback_reason:
                st.warning(
                    "PhoBERT hiện bị Windows Application Control chặn; hệ thống đang chạy chế độ "
                    "demo rule-based. Kết quả chỉ dùng để kiểm tra luồng, không dùng để đánh giá chất lượng mô hình."
                )
            if mode == "hybrid" and system.web_status:
                (st.info if system.settings.get("web") else st.warning)(system.web_status)
            with st.spinner("Đang truy xuất bằng chứng và kiểm chứng…"):
                response = run_cached(mode, model_engine, claim, as_of)
            verdict = response["verdict"]
            retrieval = response["retrieval"]
            citations = response["citations"]
            diagnostics = response.get("diagnostics", {})
            icon, kind, meaning = LABEL_STYLE.get(str(verdict["label"]), ("", "info", ""))
            getattr(st, kind)(f"{icon} **{verdict['label']}** — {meaning}")
            col_score, col_mode, col_eng = st.columns(3)
            col_score.metric("Điểm mô hình", f"{float(verdict['confidence']):.2f}")
            col_mode.metric("Nguồn bằng chứng", MODE_LABELS[mode])
            col_eng.metric("Mô hình", MODEL_LABELS[model_engine].split()[0])
            st.caption("Điểm mô hình không phải xác suất thông tin đúng trong thực tế.")
            st.write(str(verdict["explanation"]))
            if diagnostics.get("minimal_pair_reason"):
                st.info(f"Luật cặp-tối-thiểu đã điều chỉnh verdict ({diagnostics['minimal_pair_reason']}): "
                        "phát biểu gần trùng một câu trong nguồn nhưng khác số/chiều/phủ định, hoặc trùng nguyên văn.")
            if diagnostics.get("guard_reason"):
                st.info(f"Guard đã hạ verdict xuống NEI: {diagnostics['guard_reason']}.")
            gate = diagnostics.get("temporal_gate")
            if gate:
                st.info(
                    f"Claim thời sự ({'theo ngày' if gate['recency_class'] == 'today' else 'hiện tại'}): chỉ nhận "
                    f"bằng chứng từ {gate['cutoff']} (cửa sổ {gate['window_days']} ngày). Giữ {gate['kept']}; "
                    f"loại {gate['dropped_stale']} quá cũ, {gate['dropped_undated']} không rõ ngày, "
                    f"{gate['dropped_future']} sau ngày tham chiếu."
                )
            if diagnostics.get("web_error"):
                st.warning(f"Nhánh web lỗi, đã lùi về kho local: {diagnostics['web_error']}")

            st.subheader("Nhánh verifier: citation dùng cho kết luận")
            if not citations:
                st.info("Chưa có đoạn được dùng để xác nhận hoặc bác bỏ phát biểu.")
            for item in citations:
                show_evidence(item, "cite")
            cited_ids = {str(item["passage_id"]) for item in citations}
            with st.expander(f"Nhánh retrieval: {retrieval['retrieved_count']} passage đã tìm thấy"):
                for item in retrieval["evidence"]:
                    marker = "Được verifier trích dẫn" if item["passage_id"] in cited_ids else "Candidate, chưa được trích dẫn"
                    st.markdown(f"**{marker}**")
                    show_evidence(item, "url")
            if gate and gate["dropped"]:
                with st.expander(f"Bằng chứng bị neo thời gian loại ({len(gate['dropped'])})"):
                    for row in gate["dropped"]:
                        st.caption(f"[{row['reason']}] ({row['origin']}) {row['source']} · "
                                   f"{(row['published_at'] or 'không rõ')[:10]} · {row['url']}")
            with st.expander("Chi tiết kỹ thuật (để báo cáo/gỡ lỗi)"):
                st.json({"settings": diagnostics.get("settings"), "web_enriched_query": diagnostics.get("web_enriched_query"),
                         "schema_version": response.get("schema_version")})
            st.caption("Pipeline và kết quả claim được cache trong phiên Streamlit; sửa config/model cần bấm Clear cache rồi chạy lại.")
        except (RuntimeError, ValueError, ConfigValidationError) as error:
            st.error(str(error))
