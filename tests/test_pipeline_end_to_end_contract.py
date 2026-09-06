import pytest

from src.pipeline import FactCheckingPipeline
from src.schemas import Evidence, RetrievedEvidence, VerificationResult


class FixedRetriever:
    def __init__(self, items):
        self.items = items

    def search(self, claim, top_k=3):
        return self.items[:top_k]


class OverflowRetriever(FixedRetriever):
    def search(self, claim, top_k=3):
        return self.items


class FixedVerifier:
    def __init__(self, result):
        self.result = result

    def verify(self, claim, evidence_items):
        return self.result


def item(score=1.0):
    return RetrievedEvidence(Evidence("doc", "passage", "Bằng chứng", url="https://example.test"), score)


@pytest.mark.parametrize("label", ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"])
def test_pipeline_preserves_each_valid_verdict_and_citation(label):
    evidence = item()
    pipeline = FactCheckingPipeline(
        top_k=1,
        retriever=FixedRetriever([evidence]),
        checker=FixedVerifier(VerificationResult(label, 0.7, ["passage"], "Kết luận")),
    )
    result, retrieved = pipeline.run("  Claim hợp lệ. ")
    assert result.label == label
    assert result.evidence_ids == ["passage"]
    assert retrieved == [evidence]


def test_pipeline_rejects_invalid_contract_outputs():
    evidence = item()
    pipeline = FactCheckingPipeline(
        top_k=1,
        retriever=FixedRetriever([evidence]),
        checker=FixedVerifier(VerificationResult("SUPPORTED", 0.7, ["không-thuộc-retrieval"], "Sai citation")),
    )
    with pytest.raises(RuntimeError, match="không thuộc evidence"):
        pipeline.run("Claim")

    pipeline = FactCheckingPipeline(
        top_k=1,
        retriever=OverflowRetriever([item(0.1), item(0.9)]),
        checker=FixedVerifier(VerificationResult("SUPPORTED", 0.7, [], "Không chạy đến verifier")),
    )
    with pytest.raises(RuntimeError, match="nhiều evidence hơn top_k"):
        pipeline.run("Claim")

    pipeline = FactCheckingPipeline(
        top_k=2,
        retriever=FixedRetriever([item(0.1), item(0.9)]),
        checker=FixedVerifier(VerificationResult("SUPPORTED", 0.7, [], "Không chạy đến verifier")),
    )
    with pytest.raises(RuntimeError, match="score giảm dần"):
        pipeline.run("Claim")


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (VerificationResult("UNKNOWN", 0.7, [], "Nhãn sai"), "nhãn không hợp lệ"),
        (VerificationResult("SUPPORTED", 1.1, [], "Confidence sai"), "confidence ngoài"),
    ],
)
def test_pipeline_rejects_invalid_verifier_values(result, message):
    pipeline = FactCheckingPipeline(
        top_k=1,
        retriever=FixedRetriever([item()]),
        checker=FixedVerifier(result),
    )
    with pytest.raises(RuntimeError, match=message):
        pipeline.run("Claim")


def test_pipeline_rejects_nonpositive_top_k():
    with pytest.raises(ValueError, match="top_k"):
        FactCheckingPipeline(top_k=0, retriever=FixedRetriever([]), checker=FixedVerifier(VerificationResult("NOT_ENOUGH_INFO", 1.0, [], "")))
