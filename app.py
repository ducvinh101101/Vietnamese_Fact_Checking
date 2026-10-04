from pathlib import Path

import streamlit as st

from src.pipeline import FactCheckingPipeline
from src.runtime_config import ConfigValidationError, load_runtime_config


ROOT = Path(__file__).parent


@st.cache_resource
def get_pipeline() -> tuple[FactCheckingPipeline, str | None]:
    config = load_runtime_config(ROOT / "configs" / "config.yaml")
    verification = config["verification"]
    pipeline_options = dict(
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
        evidence_view=verification.get("evidence_view", "passage"),
        # minimal_pair trung tính trên dev (Δ Macro-F1 +0.1, CI [-0.2, +0.5]) và sửa các ca claim
        # chỉ khác một số/chiều/phủ định so với nguồn. guard hạ nhầm verdict đúng trên dev
        # (Δ Macro-F1 -10) nên mặc định TẮT ở đây; bật bằng verification.guard nếu cần.
        guard=verification.get("guard", False),
        minimal_pair=verification.get("minimal_pair", True),
    )
    try:
        return FactCheckingPipeline(**pipeline_options), None
    except RuntimeError as error:
        # Keep the UI usable on managed Windows machines where Application Control
        # blocks torch's native extension. Never hide the degraded mode from users.
        if verification["engine"] != "phobert" or "Application Control policy has blocked" not in str(error):
            raise
        fallback = FactCheckingPipeline(
            evidence_path=pipeline_options["evidence_path"],
            top_k=pipeline_options["top_k"],
            support_threshold=pipeline_options["support_threshold"],
            refute_markers=pipeline_options["refute_markers"],
            engine="rule_based",
        )
        return fallback, str(error)


@st.cache_data(show_spinner=False)
def run_cached(claim: str) -> dict[str, object]:
    """Cache a JSON-safe response; the model resource remains cached separately."""
    pipeline, _ = get_pipeline()
    return pipeline.run_json(claim)


st.set_page_config(page_title="Kiểm chứng thông tin tiếng Việt", page_icon="🔎")
st.title("🔎 Kiểm chứng thông tin tiếng Việt")
st.caption("Retrieval → verifier → citation. Kết quả là hỗ trợ tham khảo; luôn mở nguồn gốc để kiểm tra.")
st.warning("⚠️ Bản thử nghiệm nghiên cứu, chưa xác nhận 80% ngoài thực tế. Luôn kiểm tra đối chiếu nguồn gốc trích dẫn.")

claim = st.text_area("Phát biểu cần kiểm chứng", placeholder="Nhập một phát biểu tiếng Việt…", max_chars=2000)
if st.button("Kiểm chứng", type="primary"):
    if not claim.strip():
        st.warning("Vui lòng nhập phát biểu cần kiểm chứng.")
    else:
        try:
            _, fallback_reason = get_pipeline()
            if fallback_reason:
                st.warning(
                    "PhoBERT hiện bị Windows Application Control chặn; hệ thống đang chạy chế độ "
                    "demo rule-based. Kết quả chỉ dùng để kiểm tra luồng, không dùng để đánh giá chất lượng mô hình."
                )
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
        except (RuntimeError, ValueError, ConfigValidationError) as error:
            st.error(str(error))
