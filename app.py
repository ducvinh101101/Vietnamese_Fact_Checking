from pathlib import Path

import streamlit as st
import yaml

from src.pipeline import FactCheckingPipeline


ROOT = Path(__file__).parent


@st.cache_resource
def get_pipeline() -> FactCheckingPipeline:
    with (ROOT / "configs" / "config.yaml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    verification = config["verification"]
    return FactCheckingPipeline(
        evidence_path=str(ROOT / config["paths"]["evidence_path"]),
        top_k=config["retrieval"]["top_k"],
        support_threshold=verification["support_threshold"],
        refute_markers=verification["refute_markers"],
        engine=verification["engine"],
        model_path=str(ROOT / verification["model_path"]),
        vncorenlp_dir=str(ROOT / verification["vncorenlp_dir"]),
        max_length=verification["max_length"],
        temperature=verification.get("temperature", 1.0),
        decisive_min_confidence=verification.get("decisive_min_confidence", 0.0),
        retrieval_rank_bias=verification.get("retrieval_rank_bias", 0.0),
        aggregation_model_path=str(ROOT / verification["aggregation_model_path"]) if verification.get("aggregation_model_path") else None,
    )


st.set_page_config(page_title="Kiểm chứng thông tin tiếng Việt", page_icon="🔎")
st.title("🔎 Kiểm chứng thông tin tiếng Việt")
st.caption("BM25 truy xuất bằng chứng, PhoBERT-base kiểm chứng claim–evidence. Kết quả chỉ có giá trị hỗ trợ tham khảo.")

claim = st.text_area("Phát biểu cần kiểm chứng", placeholder="Nhập một phát biểu tiếng Việt…", max_chars=2000)
if st.button("Kiểm chứng", type="primary"):
    try:
        result, evidence_items = get_pipeline().run(claim)
        st.subheader(result.label)
        if result.label != "NOT_ENOUGH_INFO":
            st.metric("Điểm mô hình", f"{result.confidence:.2f}")
            st.caption("Điểm mô hình không phải xác suất thông tin đúng trong thực tế.")
        st.write(result.explanation)
        cited = [item for item in evidence_items if item.evidence.passage_id in result.evidence_ids]
        st.subheader("Đoạn được dùng cho kết luận")
        if not cited:
            st.info("Chưa có đoạn được dùng để xác nhận hoặc bác bỏ phát biểu.")
        for item in cited:
            st.markdown(f"**{item.evidence.passage_id}** · điểm BM25: `{item.score:.2f}`")
            st.write(item.evidence.content)
            if item.evidence.url:
                st.caption(f"Nguồn: {item.evidence.source} — {item.evidence.url}")
        remaining = [item for item in evidence_items if item.evidence.passage_id not in result.evidence_ids and item.score > 0]
        if remaining:
            with st.expander("Các đoạn khác được tìm thấy — cần đọc kiểm tra"):
                for item in remaining:
                    st.write(item.evidence.content)
                    if item.evidence.url:
                        st.caption(item.evidence.url)
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
