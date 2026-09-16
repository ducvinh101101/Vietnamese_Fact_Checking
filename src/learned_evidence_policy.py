"""Small, inspectable three-label aggregator fitted on development data."""
from __future__ import annotations

import json
from math import isfinite, log
from pathlib import Path

from src.decision_policy import LABELS, softmax
from src.retrieval_aware_policy import AggregatedDecision


def aggregation_features(probabilities, scores):
    if len(probabilities) != 3 or len(scores) != 3:
        raise ValueError("Learned aggregator requires exactly three ranked passages")
    flat = [float(p) for row in probabilities for p in row]
    if len(flat) != 9 or any(not isfinite(p) or not 0 <= p <= 1 for p in flat):
        raise ValueError("Invalid candidate probabilities")
    if any(len(row) != 3 or abs(sum(row) - 1) > 1e-5 for row in probabilities):
        raise ValueError("Candidate probabilities must sum to one")
    if any(not isfinite(float(s)) or s < 0 for s in scores):
        raise ValueError("Invalid retrieval scores")
    return flat + [log(max(p, 1e-6)) for p in flat] + [s / max(scores[0], 1e-6) for s in scores]


class LearnedEvidencePolicy:
    def __init__(self, path):
        self.model = json.loads(Path(path).read_text(encoding="utf-8"))
        if self.model["labels"] != list(LABELS) or self.model["feature_version"] != 1:
            raise ValueError("Incompatible learned aggregator")

    def predict_probabilities(self, probabilities, scores):
        features = aggregation_features(probabilities, scores)
        standardized = [(x - m) / s for x, m, s in zip(features, self.model["mean"], self.model["scale"], strict=True)]
        logits = [sum(w * x for w, x in zip(weights, standardized, strict=True)) + bias
                  for weights, bias in zip(self.model["coef"], self.model["intercept"], strict=True)]
        return softmax(logits, self.model.get("temperature", 1.0))

    def decide(self, probabilities, scores):
        probs = self.predict_probabilities(probabilities, scores)
        label = max(range(3), key=probs.__getitem__)
        if label == 2:
            return AggregatedDecision(LABELS[2], probs[2], -1)
        if probs[label] < self.model.get("decisive_min_confidence", 0.0):
            return AggregatedDecision(LABELS[2], probs[2], -1, "low_confidence")
        eligible = [i for i in range(3) if scores[i] > 0 and max(range(3), key=probabilities[i].__getitem__) == label]
        if not eligible:
            return AggregatedDecision(LABELS[2], probs[2], -1, "no_agreeing_passage")
        # Pair agreement is necessary, but not proof of citation faithfulness.
        index = max(eligible, key=lambda i: probabilities[i][label] / (i + 1))
        return AggregatedDecision(LABELS[label], probs[label], index)
