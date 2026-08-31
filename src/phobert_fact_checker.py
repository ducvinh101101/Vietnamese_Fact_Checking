"""Verifier PhoBERT E2 đã fine-tune cho cặp claim–evidence."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os
import sys

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

    def __init__(self, model_path: str | Path, vncorenlp_dir: str | Path, max_length: int = 256) -> None:
        try:
            prepare_torch_dll_path()
            prepare_java_runtime()
            import py_vncorenlp
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as error:
            raise RuntimeError("Cần cài torch, transformers và py_vncorenlp để chạy PhoBERT.") from error
        self.torch = torch
        self.max_length = max_length
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_path), use_fast=False)
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_path)).to(self.device)
        self.model.eval()
        self.segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(Path(vncorenlp_dir).resolve()))

    @lru_cache(maxsize=2_048)
    def _segment(self, text: str) -> str:
        return " ".join(self.segmenter.word_segment(text))

    def _predict_pair(self, claim: str, evidence: str) -> tuple[str, float]:
        inputs = self.tokenizer(
            self._segment(claim), self._segment(evidence), truncation=True,
            max_length=self.max_length, return_tensors="pt",
        ).to(self.device)
        with self.torch.inference_mode():
            probabilities = self.torch.softmax(self.model(**inputs).logits, dim=-1)[0]
        label_id = int(probabilities.argmax().item())
        return self.label_map[label_id], float(probabilities[label_id].item())

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        if not evidence_items:
            return VerificationResult("NOT_ENOUGH_INFO", 1.0, [], "Không tìm thấy bằng chứng trong kho tài liệu hiện có.")
        scored = [(item, *self._predict_pair(claim, item.evidence.content)) for item in evidence_items]
        decisive = [row for row in scored if row[1] != "NOT_ENOUGH_INFO"]
        best_item, label, confidence = max(decisive or scored, key=lambda row: row[2])
        explanation = {
            "SUPPORTED": "PhoBERT đánh giá phát biểu được bằng chứng đã trích dẫn ủng hộ.",
            "REFUTED": "PhoBERT đánh giá phát biểu mâu thuẫn với bằng chứng đã trích dẫn.",
            "NOT_ENOUGH_INFO": "PhoBERT không tìm thấy bằng chứng đủ mạnh để kết luận ủng hộ hoặc bác bỏ.",
        }[label]
        return VerificationResult(label, round(confidence, 4), [best_item.evidence.passage_id], explanation)
