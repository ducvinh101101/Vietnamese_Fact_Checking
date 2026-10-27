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
