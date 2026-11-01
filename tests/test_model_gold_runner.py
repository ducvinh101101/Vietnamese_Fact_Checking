"""No-network checks for blind Gemini/PhoBERT comparison tooling."""

import json
from urllib.error import HTTPError
from unittest.mock import patch

import pytest

from scripts.run_model_gold import DEFAULT_INPUTS, load_inputs, protocol_prompt
from src.gemini_gold import GeminiGoldClient, GeminiOutputError


def input_case():
    return {"id": "demo", "as_of": "2026-10-01", "claim": "Phòng A có 3 ghế.",
            "evidence": [{"passage_id": "e1", "content": "Phòng A có 3 ghế."}]}


def response(prediction, finish="STOP"):
    return {"candidates": [{"finishReason": finish,
                            "content": {"parts": [{"text": json.dumps(prediction)}]}}]}


def prediction():
    return {"id": "demo", "label": "SUPPORTED", "evidence_ids": ["e1"], "explanation": "Số ghế khớp."}


def test_request_keeps_secret_in_header_and_has_no_external_tools():
    client = GeminiGoldClient("test-model", api_key="fake-unit-test-key")
    request = client.make_request(input_case(), "fixed protocol")
    payload = json.loads(request.data)
    assert "fake-unit-test-key" not in request.full_url
    assert "fake-unit-test-key" not in request.data.decode()
    assert dict((k.lower(), v) for k, v in request.header_items())["x-goog-api-key"] == "fake-unit-test-key"
    assert "tools" not in payload
    assert payload["systemInstruction"]["parts"][0]["text"] == "fixed protocol"
    assert json.loads(payload["contents"][0]["parts"][0]["text"]) == input_case()
    assert payload["generationConfig"]["responseJsonSchema"]["properties"]["label"]["enum"] == [
        "SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


def test_refuses_gold_label_leak_to_api():
    client = GeminiGoldClient("test-model", api_key="fake")
    with pytest.raises(ValueError, match="blind"):
        client.make_request({**input_case(), "gold_label": "SUPPORTED"}, "prompt")


def test_model_id_cannot_redirect_request_or_put_secret_in_url():
    with pytest.raises(ValueError, match="model ID"):
        GeminiGoldClient("https://other.example/model", api_key="fake")


def test_frozen_blind_inputs_and_prompt_are_usable():
    rows = load_inputs(DEFAULT_INPUTS)
    assert len(rows) == 84 and len({row["id"] for row in rows}) == 84
    assert "SUPPORTED" in protocol_prompt()
    assert all(set(row) == {"id", "as_of", "claim", "evidence"} for row in rows)


def test_parser_accepts_valid_output_and_ignores_thought_parts():
    raw = response(prediction())
    raw["candidates"][0]["content"]["parts"].insert(0, {"text": "private thought", "thought": True})
    assert GeminiGoldClient.parse_response(raw, "demo") == prediction()


@pytest.mark.parametrize("bad", [
    {**prediction(), "id": "wrong-case"},
    {**prediction(), "label": "TRUE"},
    {**prediction(), "evidence_ids": "e1"},
    {**prediction(), "evidence_ids": [4]},
    {**prediction(), "explanation": None},
])
def test_bad_output_is_error_instead_of_nei(bad):
    raw = response(bad)
    with pytest.raises(GeminiOutputError) as error:
        GeminiGoldClient.parse_response(raw, "demo")
    assert error.value.raw == raw


@pytest.mark.parametrize("raw", [{}, {"candidates": []}, response(prediction(), "MAX_TOKENS")])
def test_blocked_empty_or_truncated_output_is_not_a_valid_label(raw):
    with pytest.raises(GeminiOutputError):
        GeminiGoldClient.parse_response(raw, "demo")


def test_wrong_citation_does_not_replace_correct_label_with_nei():
    result = {**prediction(), "evidence_ids": ["invented"]}
    assert GeminiGoldClient.parse_response(response(result), "demo")["label"] == "SUPPORTED"


def test_http_error_does_not_echo_key_or_provider_body():
    client = GeminiGoldClient("test-model", api_key="fake-sensitive-key")
    error = HTTPError("https://example.invalid/?key=fake-sensitive-key", 429, "quota", {}, None)
    with patch("src.gemini_gold.urlopen", side_effect=error):
        with pytest.raises(RuntimeError) as caught:
            client.predict(input_case(), "prompt")
    assert "429" in str(caught.value)
    assert "fake-sensitive-key" not in str(caught.value)


def test_http_error_reports_provider_message_without_key():
    import io
    client = GeminiGoldClient("gemma-4-31b-it", api_key="fake-unit-test-key")
    body = json.dumps({"error": {"status": "INVALID_ARGUMENT",
                                 "message": "JSON mode is not enabled for fake-unit-test-key"}}).encode()
    error = HTTPError("https://x", 400, "Bad Request", {}, io.BytesIO(body))
    with patch("src.gemini_gold.urlopen", side_effect=error):
        with pytest.raises(RuntimeError) as info:
            client.predict(input_case(), "fixed protocol")
    message = str(info.value)
    assert "HTTP 400" in message and "INVALID_ARGUMENT" in message
    assert "fake-unit-test-key" not in message


def test_frozen_dataset_validates_with_crlf_line_endings(tmp_path):
    import shutil
    from scripts.evaluate_model_gold import validate_dataset
    copy = tmp_path / "ds"
    shutil.copytree(DEFAULT_INPUTS.parent, copy)
    for name in ("gold.jsonl", "inputs.jsonl", "PROTOCOL.md", "build_dataset.py"):
        path = copy / name
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    validate_dataset(copy)  # Windows checkout / write_text CRLF must not look like a changed gold set


@pytest.mark.parametrize("mode,has_mime,has_schema", [("schema", True, True), ("mime", True, False),
                                                     ("prompt", False, False)])
def test_json_modes_shape_generation_config(mode, has_mime, has_schema):
    client = GeminiGoldClient("gemma-4-31b-it", api_key="fake-unit-test-key", json_mode=mode)
    config = json.loads(client.make_request(input_case(), "p").data)["generationConfig"]
    assert ("responseMimeType" in config) is has_mime
    assert ("responseJsonSchema" in config) is has_schema


def test_parser_accepts_fenced_json_and_skips_thought_parts():
    text = "```json\n" + json.dumps(prediction()) + "\n```"
    raw = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"text": "thinking about it", "thought": True}, {"text": text}]}}]}
    assert GeminiGoldClient.parse_response(raw, "demo")["label"] == "SUPPORTED"


def test_runner_retries_transient_http_errors_only(tmp_path, monkeypatch):
    import sys
    from scripts import run_model_gold
    calls = {"n": 0}

    def flaky(self, record, prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Gemini HTTP 500 (INTERNAL: x); check API key, model access and quota")
        return {"id": record["id"], "label": "SUPPORTED", "evidence_ids": [], "explanation": "ok"}, {}

    monkeypatch.setattr("src.gemini_gold.GeminiGoldClient.predict", flaky)
    monkeypatch.setattr(run_model_gold.time, "sleep", lambda s: None)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-unit-test-key")
    out = tmp_path / "p.jsonl"
    monkeypatch.setattr(sys, "argv", ["x", "--backend", "gemini", "--model", "m", "--limit", "1",
                                      "--max-retries", "2", "--output", str(out)])
    assert run_model_gold.main() == 0
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["label"] == "SUPPORTED" and row["retries"] == 1
    meta = json.loads((tmp_path / "p.run.json").read_text(encoding="utf-8"))
    assert meta["retries_used"] == 1 and meta["automatic_retries"] == 2


def test_resume_reuses_successes_and_recalls_only_failures(tmp_path, monkeypatch):
    import sys
    from scripts import run_model_gold
    from scripts.run_model_gold import protocol_prompt
    import hashlib
    records = load_inputs(DEFAULT_INPUTS)[:2]
    prev = tmp_path / "prev.jsonl"
    prev.write_text(json.dumps({"id": records[0]["id"], "label": "REFUTED", "evidence_ids": [], "explanation": "x"}) + "\n"
                    + json.dumps({"id": records[1]["id"], "label": None, "evidence_ids": [], "error": "HTTP 500"}) + "\n",
                    encoding="utf-8")
    (tmp_path / "prev.run.json").write_text(json.dumps(
        {"model": "m", "prompt_sha256": hashlib.sha256(protocol_prompt().encode()).hexdigest()}), encoding="utf-8")
    called = []

    def fake(self, record, prompt):
        called.append(record["id"])
        return {"id": record["id"], "label": "SUPPORTED", "evidence_ids": [], "explanation": "ok"}, {}

    monkeypatch.setattr("src.gemini_gold.GeminiGoldClient.predict", fake)
    monkeypatch.setattr(run_model_gold.time, "sleep", lambda s: None)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-unit-test-key")
    out = tmp_path / "new.jsonl"
    monkeypatch.setattr(sys, "argv", ["x", "--backend", "gemini", "--model", "m", "--limit", "2",
                                      "--resume-from", str(prev), "--output", str(out)])
    assert run_model_gold.main() == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert called == [records[1]["id"]]
    assert [r["label"] for r in rows] == ["REFUTED", "SUPPORTED"] and rows[0]["reused_from_previous_run"]
