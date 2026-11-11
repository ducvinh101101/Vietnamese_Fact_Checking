import io
import json
from urllib.error import HTTPError

from src.schemas import Evidence, RetrievedEvidence
from src.system_builder import build_verifier


CLAIM = "Một mét bằng 100 xăng-ti-mét."
EVIDENCE = [RetrievedEvidence(Evidence("demo", "demo-p1", CLAIM), 1.0)]


def test_deepseek_engine_sends_fixed_evidence_and_returns_citation(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    def complete(request, *, timeout):
        body = json.loads(request.data)
        record = json.loads(body["messages"][1]["content"])
        assert request.full_url == "https://api.deepseek.com/chat/completions"
        assert request.get_header("Authorization") == "Bearer deepseek-test-key"
        assert body["model"] == "deepseek-flash"
        assert body["response_format"] == {"type": "json_object"}
        assert record["claim"] == CLAIM and record["evidence"][0]["passage_id"] == "demo-p1"
        prediction = {"id": record["id"], "label": "SUPPORTED", "evidence_ids": ["demo-p1"],
                      "explanation": "Bằng chứng xác nhận đơn vị đo."}
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(prediction)}}]}
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr("src.deepseek_client.urlopen", complete)
    verifier, fallback = build_verifier({"verification": {"engine": "deepseek"}})
    result = verifier.verify(CLAIM, EVIDENCE)
    assert fallback is None
    assert result.status == "ok" and result.label == "SUPPORTED"
    assert result.evidence_ids == ["demo-p1"]


def test_deepseek_bad_key_is_a_provider_error_and_does_not_leak_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    def deny(request, *, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"deepseek-test-key"))

    monkeypatch.setattr("src.deepseek_client.urlopen", deny)
    verifier, _ = build_verifier({"verification": {"engine": "deepseek"}})
    result = verifier.verify(CLAIM, EVIDENCE)
    assert result.status == "error" and result.error_code == "provider_error"
    assert "HTTP 401" in result.explanation and "deepseek-test-key" not in result.explanation
    assert result.evidence_ids == []
