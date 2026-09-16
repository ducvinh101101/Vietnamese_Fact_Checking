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


@st.cache_data(show_spinner=False)
def run_cached(claim: str) -> dict[str, object]:
    """Cache a JSON-safe response; the model resource remains cached separately."""
    return get_pipeline().run_json(claim)


st.set_page_config(page_title="Kiểm chứng thông tin tiếng Việt", page_icon="🔎")
st.title("🔎 Kiểm chứng thông tin tiếng Việt")
st.caption("Retrieval → verifier → citation. Kết quả là hỗ trợ tham khảo; luôn mở nguồn gốc để kiểm tra.")

claim = st.text_area("Phát biểu cần kiểm chứng", placeholder="Nhập một phát biểu tiếng Việt…", max_chars=2000)
if st.button("Kiểm chứng", type="primary"):
    try:
        response = run_cached(claim)
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
        st.caption("Pipeline và kết quả claim được cache trong phiên Streamlit; sửa config/model cần bấm Clear cache rồi chạy lại.")
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
