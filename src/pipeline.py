from src.fact_checker import RuleBasedFactChecker
from src.contracts import Retriever, Verifier
from src.io_utils import load_evidence_jsonl
from src.phobert_fact_checker import PhoBERTFactChecker
from src.preprocessing import normalize_text
from src.retriever import BM25Retriever
from src.schemas import RetrievedEvidence, VerificationResult


VALID_LABELS = {"SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"}


class FactCheckingPipeline:
    def __init__(self, evidence_path: str | None = None, top_k: int = 3, support_threshold: float = 0.45,
                 refute_markers: list[str] | None = None, engine: str = "rule_based",
                 model_path: str | None = None, vncorenlp_dir: str | None = None, max_length: int = 256,
                 retriever: Retriever | None = None, checker: Verifier | None = None) -> None:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
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
