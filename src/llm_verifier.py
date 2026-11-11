"""Verifier dựa trên LLM cho kiểm chứng thông tin tiếng Việt.

Tương thích với protocol Verifier (src.contracts.Verifier), cho phép người dùng
chuyển đổi giữa PhoBERT, Gemma 4 và DeepSeek trên giao diện Web.
"""

from __future__ import annotations

import os
from datetime import date
from src.deepseek_client import DEFAULT_DEEPSEEK_MODEL, DeepSeekClient, DeepSeekOutputError
from src.schemas import RetrievedEvidence, VerificationResult
from src.gemini_gold import GeminiGoldClient, GeminiOutputError

DEFAULT_MODEL = 'gemma-4-26b-a4b-it'

DEFAULT_PROMPT = """Bạn xác minh claim tiếng Việt dựa trên các đoạn bằng chứng (evidence) được cung cấp.
Chỉ dùng các đoạn evidence được cung cấp. Không tìm kiếm, không dùng kiến thức ngoài.

Trả SUPPORTED nếu toàn bộ claim được xác nhận bởi bằng chứng.
Trả REFUTED nếu có bằng chứng chắc chắn phủ định hoặc mâu thuẫn với claim.
Trả NOT_ENOUGH_INFO nếu chưa đủ thông tin để xác nhận hay phản bác.
Cho phép tính toán số học, đổi đơn vị và kết hợp nhiều đoạn bằng chứng.
Ưu tiên trích đoạn nêu trực tiếp đầy đủ các ý trong claim; nếu có đoạn trùng nguyên văn toàn bộ claim,
hãy dùng đoạn đó thay cho các đoạn chỉ liên quan chung đến chủ đề.

Trả đúng một object JSON duy nhất có các trường:
id: sao chép id đầu vào;
label: SUPPORTED, REFUTED hoặc NOT_ENOUGH_INFO;
evidence_ids: danh sách passage_id tối thiểu đủ để chứng minh kết luận, hoặc [] khi NOT_ENOUGH_INFO;
explanation: lý do ngắn gọn bằng tiếng Việt.
"""


class LLMVerifier:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 90.0,
        as_of: date | None = None,
        *,
        provider: str = "gemini",
    ):
        self.provider = provider
        if provider == "deepseek":
            self.model = (model if model is not None else os.environ.get("DEEPSEEK_MODEL", "")).strip() or DEFAULT_DEEPSEEK_MODEL
            self.api_key = (api_key or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
        else:
            self.model = (model if model is not None else os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL).strip().removeprefix('models/')
            self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.timeout = timeout
        self.as_of = as_of

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
            "as_of": (self.as_of or date.today()).isoformat(),
            "claim": claim,
            "evidence": evidence_list,
        }

        try:
            if self.provider == "deepseek":
                client = DeepSeekClient(self.model, self.api_key, self.timeout)
            else:
                client = GeminiGoldClient(
                    model=self.model,
                    api_key=self.api_key,
                    timeout=self.timeout,
                    json_mode="prompt",
                )
            pred, _ = client.predict(record, DEFAULT_PROMPT)
            label = pred.get("label")
            if label not in ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"):
                raise GeminiOutputError('LLM trả nhãn không hợp lệ', pred)

            valid_pids = {ev["passage_id"] for ev in evidence_list}
            cited_ids = [pid for pid in pred.get("evidence_ids", []) if pid in valid_pids]
            cited_ids = list(dict.fromkeys(cited_ids))
            if label != 'NOT_ENOUGH_INFO' and (not cited_ids or len(cited_ids) != len(set(pred['evidence_ids']))):
                raise GeminiOutputError('LLM trả kết luận nhưng citation thiếu hoặc không thuộc bằng chứng được cung cấp', pred)
            if label == 'NOT_ENOUGH_INFO':
                cited_ids = []

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
            err_msg = str(exc).replace(self.api_key, '[REDACTED]') if self.api_key else str(exc)
            code = 'invalid_output' if isinstance(exc, (GeminiOutputError, DeepSeekOutputError)) else (
                'configuration_error' if isinstance(exc, ValueError) else 'provider_error')
            return VerificationResult(
                label="NOT_ENOUGH_INFO",
                confidence=0.0,
                evidence_ids=[],
                explanation=f"[{self.model} - Lỗi xác minh]: {err_msg}. Yêu cầu kiểm chứng chưa hoàn tất.",
                status='error', error_code=code,
            )
