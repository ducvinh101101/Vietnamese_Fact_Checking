"""Chọn verdict từ xác suất PhoBERT theo chính sách abstention minh bạch."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Sequence


LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
DECISIVE_LABELS = frozenset(("SUPPORTED", "REFUTED"))


def softmax(logits: Sequence[float], temperature: float = 1.0) -> list[float]:
    if len(logits) != len(LABELS):
        raise ValueError("PhoBERT phải trả đúng ba logits")
    if temperature <= 0:
        raise ValueError("temperature phải lớn hơn 0")
    scaled = [float(value) / temperature for value in logits]
    maximum = max(scaled)
    unnormalized = [exp(value - maximum) for value in scaled]
    total = sum(unnormalized)
    return [value / total for value in unnormalized]


def apply_decisive_threshold(probabilities: Sequence[float], minimum: float) -> tuple[str, float]:
    """Trả NEI nếu dự đoán quyết đoán không vượt ngưỡng dev đã chọn.

    Confidence trong nhánh abstain là độ tin cậy *không đủ cho verdict quyết
    đoán*, không phải xác suất đã hiệu chỉnh hoàn hảo của nhãn NEI.
    """
    if not 0 <= minimum <= 1:
        raise ValueError("minimum phải trong khoảng 0–1")
    if len(probabilities) != len(LABELS):
        raise ValueError("PhoBERT phải trả đúng ba xác suất")
    index = max(range(len(probabilities)), key=probabilities.__getitem__)
    label = LABELS[index]
    confidence = float(probabilities[index])
    if label in DECISIVE_LABELS and confidence < minimum:
        decisive_confidence = max(probabilities[0], probabilities[1])
        return "NOT_ENOUGH_INFO", float(1 - decisive_confidence)
    return label, confidence


@dataclass(frozen=True)
class DecisionPolicy:
    """Temperature scaling và ngưỡng NEI do E6 chọn trên dev."""

    temperature: float = 1.0
    decisive_min_confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.temperature <= 0:
            raise ValueError("temperature phải lớn hơn 0")
        if not 0 <= self.decisive_min_confidence <= 1:
            raise ValueError("decisive_min_confidence phải trong khoảng 0–1")

    def probabilities(self, logits: Sequence[float]) -> list[float]:
        return softmax(logits, self.temperature)

    def decide(self, logits: Sequence[float]) -> tuple[str, float]:
        return apply_decisive_threshold(self.probabilities(logits), self.decisive_min_confidence)
