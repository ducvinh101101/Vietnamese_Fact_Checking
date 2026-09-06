"""Aggregate three-way verifier probabilities across ranked evidence.

Parameters are selected only on a development end-to-end run.  Rank weighting
is deliberately modest and transparent: it cannot invent evidence relevance,
but reduces the chance that a lower-ranked distractor with an overconfident
verdict overrides the first retrieved passage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.decision_policy import DECISIVE_LABELS, LABELS


@dataclass(frozen=True)
class AggregatedDecision:
    label: str
    confidence: float
    evidence_index: int


def decide_rank_aware(
    probabilities_by_evidence: Sequence[Sequence[float]],
    rank_bias: float = 0.0,
    decisive_min_confidence: float = 0.0,
) -> AggregatedDecision:
    """Choose a cited verdict from ranked candidate evidence.

    ``rank_bias=0`` matches the old max-confidence behavior.  A positive bias
    multiplies candidate confidence by ``1 / rank**rank_bias`` for selection;
    reported confidence remains the unweighted calibrated probability.
    """
    if not probabilities_by_evidence:
        raise ValueError("Cần ít nhất một evidence để tổng hợp")
    if rank_bias < 0:
        raise ValueError("rank_bias không được âm")
    if not 0 <= decisive_min_confidence <= 1:
        raise ValueError("decisive_min_confidence phải trong khoảng 0–1")

    candidates: list[tuple[float, float, str, int]] = []
    for evidence_index, probabilities in enumerate(probabilities_by_evidence):
        if len(probabilities) != len(LABELS):
            raise ValueError("Mỗi evidence phải có đúng ba xác suất")
        if any(value < 0 or value > 1 for value in probabilities):
            raise ValueError("Xác suất evidence phải thuộc [0, 1]")
        rank_weight = 1 / ((evidence_index + 1) ** rank_bias)
        for label_index, label in enumerate(LABELS):
            confidence = float(probabilities[label_index])
            candidates.append((confidence * rank_weight, confidence, label, evidence_index))

    _, confidence, label, evidence_index = max(candidates, key=lambda item: item[0])
    if label in DECISIVE_LABELS and confidence < decisive_min_confidence:
        nei_index = LABELS.index("NOT_ENOUGH_INFO")
        nei_candidates = [
            (float(probabilities[nei_index]) / ((index + 1) ** rank_bias), float(probabilities[nei_index]), index)
            for index, probabilities in enumerate(probabilities_by_evidence)
        ]
        _, confidence, evidence_index = max(nei_candidates, key=lambda item: item[0])
        label = "NOT_ENOUGH_INFO"
    return AggregatedDecision(label, confidence, evidence_index)

