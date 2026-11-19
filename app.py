from pathlib import Path

import streamlit as st
import yaml

from src.env_loader import load_dotenv
from src.pipeline import FactCheckingPipeline


ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
SOURCE_MODE = "Kiểm tra nguồn (có nguồn thực tế hay không)"
LEGACY_MODE = "Kiểm chứng RT-V2 (SUPPORTED/REFUTED/NEI – pipeline cũ)"
LABEL_STYLE = {"SOURCE_FOUND": st.success, "SOURCE_CONFLICT": st.warning, "NO_SOURCE": st.error}


def load_yaml(name: str) -> dict:
    with (ROOT / "configs" / name).open(encoding="utf-8") as file:
        return yaml.safe_load(file)


@st.cache_resource
def get_checker():
    """Một instance PhoBERT RT-V2 dùng chung cho cả hai chế độ (VnCoreNLP chỉ nạp được một lần)."""
    from src.phobert_fact_checker import PhoBERTFactChecker

    verification = load_yaml("config.yaml")["verification"]
    return PhoBERTFactChecker(
        ROOT / verification["model_path"], ROOT / verification["vncorenlp_dir"], verification["max_length"],
        verification.get("temperature", 1.0), verification.get("decisive_min_confidence", 0.0),
        verification.get("retrieval_rank_bias", 0.0),
        aggregation_model_path=str(ROOT / verification["aggregation_model_path"]) if verification.get("aggregation_model_path") else None,
    )


@st.cache_resource
def get_pipeline() -> FactCheckingPipeline:
    config = load_yaml("config.yaml")
    verification = config["verification"]
    checker = get_checker() if verification["engine"] == "phobert" else None
    return FactCheckingPipeline(
        evidence_path=str(ROOT / config["paths"]["evidence_path"]),
        top_k=config["retrieval"]["top_k"],
        support_threshold=verification["support_threshold"],
        refute_markers=verification["refute_markers"],
        engine=verification["engine"],
        checker=checker,
    )


@st.cache_resource
def get_source_pipeline():
    from src.source_attribution_factory import build_pipeline, load_config

    config = load_config()
    verifier = get_checker() if config["verifier"].get("enabled") else None
    return build_pipeline(config, verifier=verifier, use_verifier=verifier is not None)


@st.cache_data(show_spinner=False)
def run_cached(claim: str) -> dict[str, object]:
    """Cache a JSON-safe response; the model resource remains cached separately."""
    return get_pipeline().run_json(claim)


@st.cache_data(show_spinner=False)
def run_source_cached(claim: str) -> dict[str, object]:
    return get_source_pipeline().run_json(claim)


def show_source_result(response: dict) -> None:
    verdict = response["verdict"]
    LABEL_STYLE[str(verdict["label"])](f"**{verdict['label_text']}** · `{verdict['label']}`")
    st.write(str(verdict["explanation"]))
    sources = verdict["independent_sources"]
    col1, col2 = st.columns(2)
    col1.metric("Điểm khớp", f"{float(verdict['confidence']):.2f}")
    col2.metric("Số nguồn độc lập", len(sources))
    st.caption("Điểm khớp không phải xác suất phát biểu đúng; luôn mở nguồn để đọc đối chiếu.")
    with st.expander("Truy vấn đã dùng"):
        for query in response["queries"]:
            st.code(query, language=None)

    st.subheader("Nhánh verifier: nguồn được dùng cho kết luận")
    if not response["citations"]:
        st.info("Không có đoạn nào đủ điều kiện làm nguồn cho phát biểu này.")
    for item in response["citations"]:
        st.markdown(f"**{item['source']}** · {item.get('domain') or ''} · liên quan `{item['relevance']:.2f}`")
        st.write(str(item["content"]))
        details = []
        if item["matched_details"]:
            details.append("✅ khớp: " + ", ".join(item["matched_details"]))
        if item["conflicting_details"]:
            details.append("⚠️ lệch: " + ", ".join(item["conflicting_details"]))
        if item["missing_details"]:
            details.append("… không nhắc tới: " + ", ".join(item["missing_details"]))
        for line in details:
            st.caption(line)
        st.caption(f"Xuất bản: {item.get('published_at') or 'không rõ'} · truy xuất: {item.get('retrieved_at') or 'kho cục bộ'}")
        if item["url"]:
            st.link_button("Mở nguồn", str(item["url"]), key=f"cite-{item['passage_id']}")

    assessed = response["retrieval"]["assessed"]
    with st.expander(f"Nhánh retrieval: {response['retrieval']['retrieved_count']} ứng viên, {len(assessed)} đoạn đã đánh giá"):
        status_text = {"supports": "Xác nhận", "conflicts": "Lệch/mâu thuẫn", "related": "Liên quan, chưa đủ",
                       "unrelated": "Không liên quan"}
        for item in assessed:
            st.markdown(f"**{status_text[item['status']]}** · `{item['passage_id']}` · liên quan `{item['relevance']:.2f}`")
            if item["verifier_probabilities"]:
                st.caption("RT-V2: " + ", ".join(f"{k} {v:.2f}" for k, v in item["verifier_probabilities"].items()))
            st.write(str(item["content"]))
            if item["url"]:
                st.link_button("Mở URL nguồn", str(item["url"]), key=f"url-{item['passage_id']}")


def show_legacy_result(response: dict) -> None:
    verdict = response["verdict"]
    retrieval = response["retrieval"]
    citations = response["citations"]
    st.subheader(str(verdict["label"]))
    st.metric("Điểm mô hình", f"{float(verdict['confidence']):.2f}")
    st.caption("Điểm mô hình không phải xác suất thông tin đúng trong thực tế.")
    st.write(str(verdict["explanation"]))
    st.subheader("Nhánh verifier: citation dùng cho kết luận")
    if not citations:
        st.info("Chưa có đoạn được dùng để xác nhận hoặc bác bỏ phát biểu.")
    cited_ids = {str(item["passage_id"]) for item in citations}
    for item in citations:
        st.markdown(f"**{item['passage_id']}** · điểm retrieval: `{float(item['score']):.2f}`")
        st.write(str(item["content"]))
        st.caption(f"{item['source']} · {item.get('domain') or 'domain không rõ'} · truy xuất: {item.get('retrieved_at') or 'không rõ'}")
        if item["url"]:
            st.link_button("Mở nguồn", str(item["url"]))
    with st.expander(f"Nhánh retrieval: {retrieval['retrieved_count']} passage đã tìm thấy"):
        for item in retrieval["evidence"]:
            marker = "Được verifier trích dẫn" if item["passage_id"] in cited_ids else "Candidate, chưa được trích dẫn"
            st.markdown(f"**{marker}** · `{item['passage_id']}` · score `{float(item['score']):.2f}`")
            st.write(str(item["content"]))
            st.caption(f"{item['source']} · {item.get('source_type')} · xuất bản: {item.get('published_at') or 'không rõ'}")
            if item["url"]:
                st.link_button("Mở URL nguồn", str(item["url"]), key=f"url-{item['passage_id']}")


st.set_page_config(page_title="Kiểm tra nguồn thông tin tiếng Việt", page_icon="🔎")
st.title("🔎 Kiểm tra nguồn thông tin tiếng Việt")
mode = st.radio("Chế độ", [SOURCE_MODE, LEGACY_MODE], horizontal=False)
if mode == SOURCE_MODE:
    st.caption("Tìm xem phát biểu có nguồn thực tế (báo chí, cơ quan nhà nước) nói cùng nội dung hay không. "
               "Web search cần TAVILY_API_KEY; thiếu key thì chỉ tra kho cục bộ.")
else:
    st.caption("Retrieval → verifier → citation. Kết quả là hỗ trợ tham khảo; luôn mở nguồn gốc để kiểm tra.")

claim = st.text_area("Phát biểu cần kiểm tra", placeholder="Nhập một phát biểu tiếng Việt…", max_chars=2000)
if st.button("Kiểm tra", type="primary"):
    try:
        with st.spinner("Đang tìm nguồn…"):
            if mode == SOURCE_MODE:
                show_source_result(run_source_cached(claim))
            else:
                show_legacy_result(run_cached(claim))
        st.caption("Pipeline và kết quả claim được cache trong phiên Streamlit; sửa config/model cần bấm Clear cache rồi chạy lại.")
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
