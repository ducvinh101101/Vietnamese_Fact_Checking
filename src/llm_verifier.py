"""Verifier dựa trên LLM (Gemma 4 / Gemini API) cho kiểm chứng thông tin tiếng Việt.

Tương thích với protocol Verifier (src.contracts.Verifier), cho phép người dùng
chuyển đổi linh hoạt giữa PhoBERT (cục bộ CPU) và LLM Gemma 4 trên giao diện Web.
"""

from __future__ import annotations

import os
from typing import Any
from src.schemas import RetrievedEvidence, VerificationResult
from src.gemini_gold import GeminiGoldClient

DEFAULT_PROMPT = """Bạn xác minh claim tiếng Việt dựa trên các đoạn bằng chứng (evidence) được cung cấp.
Chỉ dùng các đoạn evidence được cung cấp. Không tìm kiếm, không dùng kiến thức ngoài.

Trả SUPPORTED nếu toàn bộ claim được xác nhận bởi bằng chứng.
Trả REFUTED nếu có bằng chứng chắc chắn phủ định hoặc mâu thuẫn với claim.
Trả NOT_ENOUGH_INFO nếu chưa đủ thông tin để xác nhận hay phản bác.
Cho phép tính toán số học, đổi đơn vị và kết hợp nhiều đoạn bằng chứng.

Trả đúng một object JSON duy nhất có các trường:
id: sao chép id đầu vào;
label: SUPPORTED, REFUTED hoặc NOT_ENOUGH_INFO;
evidence_ids: danh sách passage_id tối thiểu đủ để chứng minh kết luận, hoặc [] khi NOT_ENOUGH_INFO;
explanation: lý do ngắn gọn bằng tiếng Việt.
"""


class LLMVerifier:
    def __init__(
        self,
        model: str = "gemma-4-26b-a4b-it",
        api_key: str | None = None,
        timeout: float = 40.0,
    ):
        self.model = os.environ.get("GEMINI_MODEL") or model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.timeout = timeout

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        if not evidence_items:
            return VerificationResult(
                label="NOT_ENOUGH_INFO",
                confidence=0.0,
                evidence_ids=[],
                explanation="Không có đoạn bằng chứng nào được cung cấp để đối chiếu.",
            )

        evidence_list = []
        for item in evidence_items:
            ev = item.evidence
            evidence_list.append({
                "passage_id": ev.passage_id,
                "content": ev.content,
                "source": getattr(ev, "source", "Không rõ nguồn"),
                "url": getattr(ev, "url", ""),
                "published_at": getattr(ev, "published_at", None),
            })

        record = {
            "id": "query_claim",
            "as_of": "2026-10-01",
            "claim": claim,
            "evidence": evidence_list,
        }

        try:
            client = GeminiGoldClient(
                model=self.model,
                api_key=self.api_key,
                timeout=self.timeout,
                json_mode="prompt",
            )
            pred, _ = client.predict(record, DEFAULT_PROMPT)
            label = pred.get("label", "NOT_ENOUGH_INFO")
            if label not in ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"):
                label = "NOT_ENOUGH_INFO"

            valid_pids = {ev["passage_id"] for ev in evidence_list}
            cited_ids = [pid for pid in pred.get("evidence_ids", []) if pid in valid_pids]
            if not cited_ids and label != "NOT_ENOUGH_INFO" and evidence_list:
                cited_ids = [evidence_list[0]["passage_id"]]

            confidence = 0.95 if label == "SUPPORTED" else (0.92 if label == "REFUTED" else 0.50)
            explanation = pred.get("explanation", "").strip() or f"Phán quyết từ mô hình {self.model}."
            explanation = f"[{self.model.upper()}] {explanation}"

            return VerificationResult(
                label=label,
                confidence=confidence,
                evidence_ids=cited_ids,
                explanation=explanation,
            )
        except Exception as exc:
            err_msg = str(exc)
            return VerificationResult(
                label="NOT_ENOUGH_INFO",
                confidence=0.0,
                evidence_ids=[],
                explanation=f"[{self.model.upper()} - Lỗi kết nối API]: {err_msg}. Vui lòng thử lại hoặc chọn mô hình PhoBERT Cục bộ.",
            )
