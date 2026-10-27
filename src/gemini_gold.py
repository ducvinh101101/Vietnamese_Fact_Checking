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


class GeminiOutputError(ValueError):
    def __init__(self, message, raw):
        super().__init__(message)
        self.raw = raw


class GeminiGoldClient:
    def __init__(self, model: str, api_key: str | None = None, timeout: float = 90,
                 max_output_tokens: int = 4096, temperature: float | None = None):
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

    def make_request(self, record: dict, prompt: str) -> Request:
        # Explicit allowlist prevents a gold label/rationale field leaking to the API.
        if set(record) != {"id", "as_of", "claim", "evidence"}:
            raise ValueError("Only blind input fields may be sent to Gemini")
        config = {
            "responseMimeType": "application/json", "responseJsonSchema": OUTPUT_SCHEMA,
            "maxOutputTokens": self.max_output_tokens, "candidateCount": 1,
        }
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
            # Do not echo provider responses, URLs, request headers or credentials.
            raise RuntimeError(f"Gemini HTTP {error.code}; check API key, model access and quota") from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError("Gemini network/timeout error; no automatic retry was made") from None
        return self.parse_response(raw, record["id"]), raw

    @staticmethod
    def parse_response(raw: dict, expected_id: str) -> dict:
        try:
            candidate = raw["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError("Gemini did not finish normally (blocked or token limit)")
            parts = candidate["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
            prediction = json.loads(text)
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
