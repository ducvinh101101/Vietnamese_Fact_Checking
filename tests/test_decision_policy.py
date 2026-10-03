import pytest

from src.decision_policy import DecisionPolicy, apply_decisive_threshold, softmax


def test_nei_is_not_discarded_when_it_has_the_highest_probability():
    label, confidence = apply_decisive_threshold([0.34, 0.01, 0.99], minimum=0.5)

    assert label == "NOT_ENOUGH_INFO"
    assert confidence == 0.99


def test_low_confidence_decisive_label_abstains_to_nei():
    label, confidence = apply_decisive_threshold([0.42, 0.31, 0.27], minimum=0.5)

    assert label == "NOT_ENOUGH_INFO"
    assert confidence == pytest.approx(0.58)


def test_temperature_policy_returns_normalized_probabilities():
    values = DecisionPolicy(temperature=2.0, decisive_min_confidence=0.4).probabilities([3.0, 1.0, -2.0])

    assert sum(values) == pytest.approx(1.0)
    assert values[0] > values[1] > values[2]


@pytest.mark.parametrize("temperature", [0, -1])
def test_invalid_temperature_is_rejected(temperature):
    with pytest.raises(ValueError, match="temperature"):
        softmax([1, 2, 3], temperature)
