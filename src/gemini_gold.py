"""Small REST client for fixed-evidence Gemini evaluation (no search/tools).

Reference: https://ai.google.dev/api/generate-content
This module is deliberately independent of the project's retrieval/model logic.
"""

from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string", "enum": list(LABELS)},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
    },
    "required": ["id", "label", "evidence_ids", "explanation"],
    "additionalProperties": False,
}


JSON_MODES = ("schema", "mime", "prompt")


def extract_json_text(text: str) -> str:
    """Return the JSON object in a model reply.

    Pure JSON is returned as-is. Some open models (e.g. Gemma via the Gemini API)
    may wrap it in a ```json fence or add a sentence around it when the API's JSON
    mode is unavailable; take the outermost {...} span in that case.
    """
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("Gemini output contains no JSON object")
    return stripped[start:end + 1]


class GeminiOutputError(ValueError):
    def __init__(self, message, raw):
        super().__init__(message)
        self.raw = raw


class GeminiGoldClient:
    def __init__(self, model: str, api_key: str | None = None, timeout: float = 90,
                 max_output_tokens: int = 4096, temperature: float | None = None,
                 json_mode: str = "schema"):
        model = model.removeprefix("models/")
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", model):
            raise ValueError("GEMINI_MODEL must be a model ID, not a URL")
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key.strip():
            raise ValueError("Missing GEMINI_API_KEY: set it in the project .env or environment")
        if timeout <= 0 or max_output_tokens < 1:
            raise ValueError("timeout and max_output_tokens must be positive")
        self.model, self.timeout = model, timeout
        self.max_output_tokens, self.temperature = max_output_tokens, temperature
        if json_mode not in JSON_MODES:
            raise ValueError(f"json_mode must be one of {JSON_MODES}")
        # schema: responseJsonSchema (default, Gemini models); mime: JSON MIME type only;
        # prompt: no API JSON mode, the frozen prompt alone asks for JSON (for models
        # whose endpoint rejects JSON mode). Recorded in run metadata by the runner.
        self.json_mode = json_mode

    def make_request(self, record: dict, prompt: str) -> Request:
        # Explicit allowlist prevents a gold label/rationale field leaking to the API.
        if set(record) != {"id", "as_of", "claim", "evidence"}:
            raise ValueError("Only blind input fields may be sent to Gemini")
        config = {"maxOutputTokens": self.max_output_tokens, "candidateCount": 1}
        if self.json_mode in ("schema", "mime"):
            config["responseMimeType"] = "application/json"
        if self.json_mode == "schema":
            config["responseJsonSchema"] = OUTPUT_SCHEMA
        if self.temperature is not None:
            config["temperature"] = self.temperature
        body = {
            "systemInstruction": {"parts": [{"text": prompt}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(record, ensure_ascii=False)}]}],
            "generationConfig": config,
        }
        return Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key}, method="POST",
        )

    def predict(self, record: dict, prompt: str) -> tuple[dict, dict]:
        request = self.make_request(record, prompt)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = json.load(response)
        except HTTPError as error:
            # Do not echo URLs, request headers or credentials; only the provider's short
            # error status/message (it never contains the key) so 400/404/429 are diagnosable.
            detail = self._safe_error_detail(error)
            raise RuntimeError(f"Gemini HTTP {error.code}{detail}; check API key, model access and quota") from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError("Gemini network/timeout error; no automatic retry was made") from None
        return self.parse_response(raw, record["id"]), raw

    def _safe_error_detail(self, error) -> str:
        try:
            body = json.loads(error.read().decode("utf-8", "replace"))["error"]
            text = f"{body.get('status', '')}: {body.get('message', '')}".strip(": ")
        except Exception:
            return ""
        text = text.replace(self.api_key, "[REDACTED]")[:300]
        return f" ({text})" if text else ""

    @staticmethod
    def parse_response(raw: dict, expected_id: str) -> dict:
        try:
            candidate = raw["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError("Gemini did not finish normally (blocked or token limit)")
            parts = candidate["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
            prediction = json.loads(extract_json_text(text))
            if not isinstance(prediction, dict) or prediction.get("id") != expected_id:
                raise ValueError("Gemini output has a missing/mismatched case ID")
            if prediction.get("label") not in LABELS:
                raise ValueError("Gemini output has an invalid label")
            citations = prediction.get("evidence_ids")
            if not isinstance(citations, list) or not all(isinstance(pid, str) for pid in citations):
                raise ValueError("Gemini output has malformed evidence_ids")
            if not isinstance(prediction.get("explanation"), str):
                raise ValueError("Gemini output has no explanation")
            # Incorrect citations remain visible and are scored separately from labels.
            return {key: prediction[key] for key in ("id", "label", "evidence_ids", "explanation")}
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise GeminiOutputError(str(error), raw) from None
