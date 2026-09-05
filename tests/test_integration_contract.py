from src.contracts import Retriever, Verifier
from src.pipeline import FactCheckingPipeline
from src.schemas import Evidence, RetrievedEvidence, VerificationResult


class StubRetriever:
    def __init__(self, items: list[RetrievedEvidence]) -> None:
        self.items = items
        self.calls: list[tuple[str, int]] = []

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        self.calls.append((claim, top_k))
        return self.items[:top_k]


class StubVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[RetrievedEvidence]]] = []

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        self.calls.append((claim, evidence_items))
        return VerificationResult("SUPPORTED", 0.9, [evidence_items[0].evidence.passage_id], "Stub verdict")


def test_pipeline_accepts_any_retriever_and_verifier_implementing_the_contract():
    item = RetrievedEvidence(Evidence("doc-1", "passage-1", "Bằng chứng."), 1.5)
    retriever = StubRetriever([item])
    verifier = StubVerifier()
    assert isinstance(retriever, Retriever)
    assert isinstance(verifier, Verifier)

    pipeline = FactCheckingPipeline(top_k=1, retriever=retriever, checker=verifier)
    result, retrieved = pipeline.run("  Claim cần kiểm chứng.  ")

    assert retriever.calls == [("Claim cần kiểm chứng.", 1)]
    assert verifier.calls == [("Claim cần kiểm chứng.", [item])]
    assert retrieved == [item]
    assert result.evidence_ids == ["passage-1"]


def test_pipeline_requires_evidence_path_without_a_retriever():
    try:
        FactCheckingPipeline()
    except ValueError as error:
        assert "evidence_path" in str(error)
    else:
        raise AssertionError("Pipeline phải yêu cầu evidence_path nếu không có retriever")
