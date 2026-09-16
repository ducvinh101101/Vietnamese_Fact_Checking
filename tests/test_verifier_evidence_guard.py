from types import SimpleNamespace
import pytest
from src.phobert_fact_checker import PhoBERTFactChecker
from src.schemas import Evidence, RetrievedEvidence
from src.retrieval_aware_policy import AggregatedDecision
from src.decision_policy import DecisionPolicy


def hit(score, name="p"):
    return RetrievedEvidence(Evidence("d", name, "Nội dung passage"), score)


def checker(probabilities):
    verifier = object.__new__(PhoBERTFactChecker)
    verifier.aggregation_policy = None
    verifier.decision_policy = DecisionPolicy(1, 0)
    verifier.retrieval_rank_bias = 0
    verifier.predict_probabilities_batch = lambda claim, evidence: probabilities
    return verifier


def test_zero_score_hits_skip_inference_and_have_no_citation():
    verifier = object.__new__(PhoBERTFactChecker)
    result = verifier.verify("không trùng corpus", [hit(0)])
    assert result.label == "NOT_ENOUGH_INFO"
    assert result.confidence == 0
    assert result.evidence_ids == []


def test_zero_score_distractor_cannot_be_cited():
    verifier = checker([[0.8, 0.1, 0.1]])
    def infer(claim, evidence):
        assert len(evidence) == 1
        return [[0.8, 0.1, 0.1]]
    verifier.predict_probabilities_batch = infer
    result = verifier.verify("claim", [hit(10, "valid"), hit(0, "noise")])
    assert result.evidence_ids == ["valid"]


def test_guard_abstention_does_not_index_or_cite_a_passage():
    verifier = checker([[0.8, 0.1, 0.1]]*3)
    verifier.aggregation_policy = SimpleNamespace(decide=lambda *args: AggregatedDecision("NOT_ENOUGH_INFO", 0.1, -1, "no_agreeing_passage"))
    result = verifier.verify("claim", [hit(3), hit(2), hit(1)])
    assert result.evidence_ids == []
    assert "passage" in result.explanation


def test_nonfinite_score_is_rejected():
    with pytest.raises(ValueError, match="hữu hạn"):
        checker([]).verify("claim", [hit(float("nan"))])
