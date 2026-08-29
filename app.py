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
    )


st.set_page_config(page_title="Kiểm chứng thông tin tiếng Việt", page_icon="🔎")
st.title("🔎 Kiểm chứng thông tin tiếng Việt")
st.caption("MVP dùng BM25 và bộ kiểm chứng luật. Kết quả chỉ có giá trị hỗ trợ tham khảo.")

claim = st.text_area("Phát biểu cần kiểm chứng", placeholder="Nhập một phát biểu tiếng Việt…")
if st.button("Kiểm chứng", type="primary"):
    try:
        result, evidence_items = get_pipeline().run(claim)
        st.subheader(result.label)
        st.metric("Độ tin cậy (MVP)", f"{result.confidence:.0%}")
        st.write(result.explanation)
        st.subheader("Bằng chứng được truy xuất")
        for item in evidence_items:
            st.markdown(f"**{item.evidence.passage_id}** · điểm BM25: `{item.score:.2f}`")
            st.write(item.evidence.content)
            if item.evidence.url:
                st.caption(f"Nguồn: {item.evidence.source} — {item.evidence.url}")
    except ValueError as error:
        st.warning(str(error))
