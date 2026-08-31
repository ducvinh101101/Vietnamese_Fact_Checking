"""Kích hoạt checkpoint PhoBERT E2 trong pipeline và Streamlit."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    pipeline = '''from src.fact_checker import RuleBasedFactChecker
from src.io_utils import load_evidence_jsonl
from src.phobert_fact_checker import PhoBERTFactChecker
from src.preprocessing import normalize_text
from src.retriever import BM25Retriever
from src.schemas import RetrievedEvidence, VerificationResult


class FactCheckingPipeline:
    def __init__(self, evidence_path: str, top_k: int = 3, support_threshold: float = 0.45,
                 refute_markers: list[str] | None = None, engine: str = "rule_based",
                 model_path: str | None = None, vncorenlp_dir: str | None = None, max_length: int = 256) -> None:
        self.retriever = BM25Retriever(load_evidence_jsonl(evidence_path))
        if engine == "phobert":
            if not model_path or not vncorenlp_dir:
                raise ValueError("model_path và vncorenlp_dir là bắt buộc khi dùng PhoBERT")
            self.checker = PhoBERTFactChecker(model_path, vncorenlp_dir, max_length)
        elif engine == "rule_based":
            self.checker = RuleBasedFactChecker(support_threshold, refute_markers)
        else:
            raise ValueError(f"Verifier không hỗ trợ: {engine}")
        self.top_k = top_k

    def run(self, claim: str) -> tuple[VerificationResult, list[RetrievedEvidence]]:
        cleaned_claim = normalize_text(claim)
        if not cleaned_claim:
            raise ValueError("Phát biểu không được để trống")
        retrieved = self.retriever.search(cleaned_claim, self.top_k)
        return self.checker.verify(cleaned_claim, retrieved)
'''
    # `run` is completed below to keep the source compact while preserving a typed result.
    pipeline = pipeline.replace(
        "return self.checker.verify(cleaned_claim, retrieved)\n",
        "result = self.checker.verify(cleaned_claim, retrieved)\n        return result, retrieved\n",
    )
    (ROOT / "src" / "pipeline.py").write_text(pipeline, encoding="utf-8")

    app = '''from pathlib import Path

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
    )


st.set_page_config(page_title="Kiểm chứng thông tin tiếng Việt", page_icon="🔎")
st.title("🔎 Kiểm chứng thông tin tiếng Việt")
st.caption("BM25 truy xuất bằng chứng, PhoBERT-base kiểm chứng claim–evidence. Kết quả chỉ có giá trị hỗ trợ tham khảo.")

claim = st.text_area("Phát biểu cần kiểm chứng", placeholder="Nhập một phát biểu tiếng Việt…")
if st.button("Kiểm chứng", type="primary"):
    try:
        result, evidence_items = get_pipeline().run(claim)
        st.subheader(result.label)
        st.metric("Độ tin cậy", f"{result.confidence:.0%}")
        st.write(result.explanation)
        st.subheader("Bằng chứng được truy xuất")
        for item in evidence_items:
            st.markdown(f"**{item.evidence.passage_id}** · điểm BM25: `{item.score:.2f}`")
            st.write(item.evidence.content)
            if item.evidence.url:
                st.caption(f"Nguồn: {item.evidence.source} — {item.evidence.url}")
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
'''
    (ROOT / "app.py").write_text(app, encoding="utf-8")

    config = '''project:
  name: vietnamese-fact-checking-mvp
  seed: 42

paths:
  evidence_path: data/evidence/sample_evidence.jsonl
  outputs_dir: outputs

retrieval:
  method: bm25
  top_k: 3

verification:
  engine: phobert
  model_path: models/e2_phobert/best_model
  vncorenlp_dir: models/vncorenlp
  max_length: 256
  support_threshold: 0.45
  refute_markers:
    - "không"
    - "chưa"
    - "sai"
    - "bác bỏ"
    - "trái ngược"
'''
    (ROOT / "configs" / "config.yaml").write_text(config, encoding="utf-8")

    requirements = ROOT / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    for line in ("torch>=2.4", "transformers>=4.41,<4.47", "py_vncorenlp>=0.1.4"):
        if line not in text:
            text += f"\n{line}\n"
    requirements.write_text(text, encoding="utf-8")

    model_config = ROOT / "models" / "e2_phobert" / "best_model" / "config.json"
    metadata = json.loads(model_config.read_text(encoding="utf-8"))
    metadata["id2label"] = {"0": "SUPPORTED", "1": "REFUTED", "2": "NOT_ENOUGH_INFO"}
    metadata["label2id"] = {"SUPPORTED": 0, "REFUTED": 1, "NOT_ENOUGH_INFO": 2}
    model_config.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
