from src.fact_checker import RuleBasedFactChecker
from src.contracts import Retriever, Verifier
from src.evidence_focus import VIEWS
from src.input_guard import is_instruction_like_claim
from src.minimal_pair import MinimalPairVerifier
from src.io_utils import load_evidence_jsonl
from src.phobert_fact_checker import PhoBERTFactChecker
from src.pipeline_output import build_pipeline_output
from src.preprocessing import normalize_text
from src.retriever import BM25Retriever
from src.schemas import RetrievedEvidence, VerificationResult
from src.verdict_guard import GuardedVerifier


VALID_LABELS = {"SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"}


class FactCheckingPipeline:
    def __init__(self, evidence_path: str | None = None, top_k: int = 3, support_threshold: float = 0.45,
                 refute_markers: list[str] | None = None, engine: str = "rule_based",
                 model_path: str | None = None, vncorenlp_dir: str | None = None, max_length: int = 256,
                 temperature: float = 1.0, decisive_min_confidence: float = 0.0,
                 retrieval_rank_bias: float = 0.0,
                 retriever: Retriever | None = None, checker: Verifier | None = None,
                 aggregation_model_path: str | None = None,
                 evidence_view: str = "passage", guard: bool = False, minimal_pair: bool = False,
                 guard_focus_coverage: float = 0.6) -> None:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        if evidence_view not in VIEWS:
            raise ValueError(f"evidence_view không hợp lệ: {evidence_view!r}; chọn một trong {VIEWS}")
        if retriever is not None:
            self.retriever = retriever
        else:
            if not evidence_path:
                raise ValueError("evidence_path là bắt buộc khi không truyền retriever")
            self.retriever = BM25Retriever(load_evidence_jsonl(evidence_path))

        if checker is not None:
            self.checker = checker
        elif engine == "phobert":
            if not model_path or not vncorenlp_dir:
                raise ValueError("model_path và vncorenlp_dir là bắt buộc khi dùng PhoBERT")
            self.checker = PhoBERTFactChecker(
                model_path, vncorenlp_dir, max_length, temperature, decisive_min_confidence, retrieval_rank_bias,
                aggregation_model_path=aggregation_model_path, evidence_view=evidence_view,
            )
        elif engine == "rule_based":
            self.checker = RuleBasedFactChecker(support_threshold, refute_markers)
        else:
            raise ValueError(f"Verifier không hỗ trợ: {engine}")
        # Lớp hậu kiểm tùy chọn (mặc định TẮT để giữ nguyên số liệu RT-V2 đã khóa):
        # * guard: hạ verdict thiếu căn cứ xuống NEI. Thiết kế cho claim thời sự nhánh web;
        #   trên dev ViFactCheck nó hạ nhầm nhiều verdict đúng hơn là chặn được (xem báo cáo).
        # * minimal_pair: luật cặp-tối-thiểu (src/minimal_pair.py), trung tính trên dev.
        if guard:
            self.checker = GuardedVerifier(self.checker, focus_coverage=guard_focus_coverage)
        if minimal_pair:
            self.checker = MinimalPairVerifier(self.checker)
        self.guard, self.minimal_pair = guard, minimal_pair
        self.top_k = top_k

    def run(self, claim: str) -> tuple[VerificationResult, list[RetrievedEvidence]]:
        cleaned_claim = normalize_text(claim)
        if not cleaned_claim:
            raise ValueError("Phát biểu không được để trống")
        if is_instruction_like_claim(cleaned_claim):
            return VerificationResult(
                label="NOT_ENOUGH_INFO",
                confidence=1.0,
                evidence_ids=[],
                explanation="Đầu vào chứa chỉ dẫn can thiệp vào quy trình kiểm chứng, không phải phát biểu cần kiểm tra.",
            ), []
        retrieved = self.retriever.search(cleaned_claim, self.top_k)
        if len(retrieved) > self.top_k:
            raise RuntimeError("Retriever trả về nhiều evidence hơn top_k")
        if any(
            retrieved[index].score < retrieved[index + 1].score
            for index in range(len(retrieved) - 1)
        ):
            raise RuntimeError("Retriever phải sắp evidence theo score giảm dần")
        result = self.checker.verify(cleaned_claim, retrieved)
        if result.label not in VALID_LABELS:
            raise RuntimeError(f"Verifier trả nhãn không hợp lệ: {result.label}")
        if not 0 <= result.confidence <= 1:
            raise RuntimeError("Verifier trả confidence ngoài khoảng 0–1")
        retrieved_ids = {item.evidence.passage_id for item in retrieved}
        if not set(result.evidence_ids).issubset(retrieved_ids):
            raise RuntimeError("Verifier trả evidence_id không thuộc evidence đã truy xuất")
        return result, retrieved

    def run_json(self, claim: str) -> dict[str, object]:
        """Run the pipeline and serialize its verdict/evidence audit trail."""
        result, retrieved = self.run(claim)
        return build_pipeline_output(result, retrieved)
