import json

import pytest

from src.pipeline import FactCheckingPipeline
from src.schemas import Evidence, RetrievedEvidence, VerificationResult


class FixedRetriever:
    def __init__(self, items):
        self.items = items

    def search(self, claim, top_k=3):
        return self.items[:top_k]


class FixedVerifier:
    def __init__(self, result):
        self.result = result

    def verify(self, claim, evidence_items):
        return self.result


def evidence(passage_id="p1", score=2.5, url="https://example.org/article"):
    item = Evidence("doc-1", passage_id, "Nội dung evidence", source="Nguồn kiểm thử", url=url, title="Tiêu đề")
    return RetrievedEvidence(item, score)


def pipeline(result, items):
    return FactCheckingPipeline(top_k=3, retriever=FixedRetriever(items), checker=FixedVerifier(result))


def test_json_output_keeps_citation_id_url_and_json_safety():
    response = pipeline(
        VerificationResult("SUPPORTED", 0.8, ["p1"], "Có evidence"),
        [evidence()],
    ).run_json("Claim")
    assert response["verdict"]["label"] == "SUPPORTED"
    assert response["citations"] == [response["retrieval"]["evidence"][0]]
    assert response["citations"][0]["passage_id"] == "p1"
    assert response["citations"][0]["url"] == "https://example.org/article"
    json.dumps(response, ensure_ascii=False, allow_nan=False)


def test_json_output_for_no_evidence_is_nei_without_citation():
    response = pipeline(
        VerificationResult("NOT_ENOUGH_INFO", 0.0, [], "Không có evidence"),
        [],
    ).run_json("Claim ngoài kho")
    assert response["verdict"]["label"] == "NOT_ENOUGH_INFO"
    assert response["retrieval"]["retrieved_count"] == 0
    assert response["retrieval"]["positive_score_count"] == 0
    assert response["citations"] == []


@pytest.mark.parametrize(
    ("result", "items", "message"),
    [
        (VerificationResult("SUPPORTED", 0.8, ["p1"], ""), [evidence(url="not-a-url")], "URL HTTP"),
        (VerificationResult("SUPPORTED", 0.8, ["p1"], ""), [evidence(score=0)], "không dương"),
        (VerificationResult("NOT_ENOUGH_INFO", 0.8, ["p1"], ""), [evidence()], "NOT_ENOUGH_INFO"),
        (VerificationResult("SUPPORTED", 0.8, ["p1", "p1"], ""), [evidence()], "trùng lặp"),
    ],
)
def test_json_output_rejects_invalid_citation_contract(result, items, message):
    with pytest.raises(RuntimeError, match=message):
        pipeline(result, items).run_json("Claim")
