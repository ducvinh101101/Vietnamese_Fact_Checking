"""Verifier PhoBERT E2 đã fine-tune cho cặp claim–evidence."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os
import shutil
import sys
from math import isfinite

from src.decision_policy import DecisionPolicy
from src.retrieval_aware_policy import decide_rank_aware
from src.learned_evidence_policy import LearnedEvidencePolicy
from src.schemas import RetrievedEvidence, VerificationResult


_DLL_DIRECTORY_HANDLES: list[object] = []


def prepare_torch_dll_path() -> None:
    """Workaround cho runtime Windows không tự thêm torch/lib vào DLL search path."""
    if os.name != "nt":
        return
    for base in map(Path, sys.path):
        torch_lib = base / "torch" / "lib"
        if torch_lib.exists():
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(torch_lib)))
            return


def prepare_java_runtime() -> None:
    """Use the project-local Java runtime when Java is not installed system-wide."""
    if os.name != "nt" or os.environ.get("JAVA_HOME"):
        return
    java_root = Path(__file__).resolve().parents[1] / "tools" / "java17"
    executable = next(java_root.glob("**/bin/java.exe"), None) if java_root.exists() else None
    if executable is None:
        return
    java_home = executable.parent.parent
    os.environ["JAVA_HOME"] = str(java_home)
    os.environ["PATH"] = f"{executable.parent}{os.pathsep}{os.environ.get('PATH', '')}"


class PhoBERTFactChecker:
    label_map = {0: "SUPPORTED", 1: "REFUTED", 2: "NOT_ENOUGH_INFO"}

    def __init__(self, model_path: str | Path, vncorenlp_dir: str | Path, max_length: int = 256,
                 temperature: float = 1.0, decisive_min_confidence: float = 0.0,
                 retrieval_rank_bias: float = 0.0, aggregation_model_path: str | Path | None = None) -> None:
        model_dir = Path(model_path)
        segmenter_dir = Path(vncorenlp_dir)
        if not model_dir.is_dir():
            raise RuntimeError(f"Không tìm thấy thư mục model PhoBERT: {model_dir}")
        if not segmenter_dir.is_dir():
            raise RuntimeError(f"Không tìm thấy thư mục VnCoreNLP: {segmenter_dir}")
        try:
            prepare_torch_dll_path()
            prepare_java_runtime()
            import py_vncorenlp
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ModuleNotFoundError as error:
            raise RuntimeError(
                f"Thiếu thư viện Python '{error.name}'. Cần cài torch, transformers và py_vncorenlp để chạy PhoBERT."
            ) from error
        except ImportError as error:
            raise RuntimeError(f"Không thể khởi tạo thư viện PhoBERT: {error}") from error
        except OSError as error:
            raise RuntimeError(
                "Không thể nạp thư viện native của PhoBERT/Torch. Hãy kiểm tra DLL Microsoft Visual C++ "
                f"hoặc Windows Application Control. Chi tiết: {error}"
            ) from error
        if shutil.which("java") is None:
            raise RuntimeError("Không tìm thấy Java. Hãy cài Java 17 hoặc đặt JAVA_HOME trước khi chạy VnCoreNLP.")
        self.torch = torch
        self.max_length = max_length
        self.decision_policy = DecisionPolicy(temperature, decisive_min_confidence)
        self.retrieval_rank_bias = retrieval_rank_bias
        self.aggregation_policy = LearnedEvidencePolicy(aggregation_model_path) if aggregation_model_path else None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir), use_fast=False)
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(self.device)
        self.model.eval()
        self.segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(segmenter_dir.resolve()))

    @lru_cache(maxsize=2_048)
    def _segment(self, text: str) -> str:
        return " ".join(self.segmenter.word_segment(text))

    def predict_logits(self, claim: str, evidence: str) -> list[float]:
        return self.predict_logits_batch(claim, [evidence])[0]

    def predict_logits_batch(self, claim: str, evidences: list[str]) -> list[list[float]]:
        """Score all retrieved passages for one claim in a single model call."""
        if not evidences:
            return []
        segmented_claim = self._segment(claim)
        inputs = self.tokenizer(
            [segmented_claim] * len(evidences), [self._segment(evidence) for evidence in evidences],
            padding=True, truncation=True,
            max_length=self.max_length, return_tensors="pt",
        ).to(self.device)
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits
        return [[float(value) for value in row] for row in logits.detach().cpu().tolist()]

    def predict_probabilities_batch(self, claim: str, evidences: list[str]) -> list[list[float]]:
        """Return calibrated three-way probabilities for ranked candidates."""
        return [self.decision_policy.probabilities(logits) for logits in self.predict_logits_batch(claim, evidences)]

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        # BM25 zero-score hits do not establish even lexical relevance.
        if any(not isfinite(item.score) for item in evidence_items):
            raise ValueError("Điểm retrieval phải hữu hạn")
        evidence_items = [item for item in evidence_items if item.score > 0 and item.evidence.content.strip()]
        if not evidence_items:
            return VerificationResult("NOT_ENOUGH_INFO", 0.0, [], "Không tìm thấy đoạn có điểm truy xuất dương trong kho hiện có; chưa đủ bằng chứng để kết luận.")
        probabilities = self.predict_probabilities_batch(claim, [item.evidence.content for item in evidence_items])
        if self.aggregation_policy is not None and len(evidence_items) == 3:
            decision = self.aggregation_policy.decide(probabilities, [item.score for item in evidence_items])
        else:
            decision = decide_rank_aware(
                probabilities,
                rank_bias=self.retrieval_rank_bias,
                decisive_min_confidence=self.decision_policy.decisive_min_confidence,
            )
        label, confidence = decision.label, decision.confidence
        explanation = {
            "SUPPORTED": "PhoBERT đánh giá phát biểu được bằng chứng đã trích dẫn ủng hộ.",
            "REFUTED": "PhoBERT đánh giá phát biểu mâu thuẫn với bằng chứng đã trích dẫn.",
            "NOT_ENOUGH_INFO": "PhoBERT không tìm thấy bằng chứng đủ mạnh để kết luận ủng hộ hoặc bác bỏ.",
        }[label]
        if decision.reason == "low_confidence":
            explanation = "Điểm tổng hợp chưa đạt ngưỡng kết luận; cần kiểm tra thêm bằng chứng."
        elif decision.reason == "no_agreeing_passage":
            explanation = "Kết quả tổng hợp không được nhãn của passage nào xác nhận; chưa đủ bằng chứng để kết luận."
        if self.aggregation_policy is not None and len(evidence_items) == 3:
            explanation += " Điểm tổng hợp chưa được hiệu chỉnh trên dữ liệu thực tế; citation cần được đọc kiểm tra."
        citation_ids = [] if label == "NOT_ENOUGH_INFO" else [evidence_items[decision.evidence_index].evidence.passage_id]
        return VerificationResult(label, round(confidence, 4), citation_ids, explanation)
