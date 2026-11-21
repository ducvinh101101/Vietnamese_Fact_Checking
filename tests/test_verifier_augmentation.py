import importlib.util
from pathlib import Path
import random
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("aug", ROOT / "scripts" / "build_verifier_augmented_data.py")
aug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aug)

EVIDENCE = ("Sáng 21.11, Quốc hội thông qua Nghị quyết, hiệu lực thi hành từ 1/3/2027, thí điểm trong 2 năm. "
            "Mức phí 700.000 đồng, quãng đường 430,5 km, học phí từ 3-4 triệu một tháng.")


def _dmy(text: str) -> tuple[int, int, str]:
    day, month, year = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", text).groups()
    return int(day), int(month), year


def test_date_variant_keeps_value_or_shifts_day():
    claim = "Nghị quyết có hiệu lực từ 1/3/2027."
    for seed in range(5):
        same = aug.date_variant(claim, EVIDENCE, random.Random(seed), False)
        assert same != claim and _dmy(same) == (1, 3, "2027")
        shifted = aug.date_variant(claim, EVIDENCE, random.Random(seed), True)
        day, month, year = _dmy(shifted)
        assert (month, year) == (3, "2027") and abs(day - 1) >= 2


def test_number_range_is_not_a_date():
    assert aug.date_variant("Học phí từ 3-4 triệu một tháng.", EVIDENCE, random.Random(0), False) is None


def test_count_round_and_approximate_variants():
    rng = random.Random(0)
    assert aug.count_variant("Thí điểm trong 2 năm.", EVIDENCE, rng, False) == "Thí điểm trong hai năm."
    assert aug.round_variant("Mức phí 700.000 đồng.", EVIDENCE, rng, False) == "Mức phí 700 nghìn đồng."
    assert aug.approximate_variant("Quãng đường 430,5 km.", EVIDENCE, rng, False) == "Quãng đường hơn 430 km."
    far = aug.approximate_variant("Quãng đường 430,5 km.", EVIDENCE, rng, True)
    assert far and "430" not in far


def test_augment_labels():
    frame = pd.DataFrame([
        {"Statement": "Quãng đường 430,5 km.", "Evidence": EVIDENCE, "Url": "u", "labels": aug.SUPPORTED,
         "label_origin": "original_gold", "sample_weight": 1.0, "kind": "gold_window"},
        {"Statement": "Thí điểm trong 2 năm.", "Evidence": EVIDENCE, "Url": "u", "labels": 2,
         "label_origin": "original_gold", "sample_weight": 1.0, "kind": "gold_window"},
    ])
    rows, _ = aug.augment(frame, seed=1)
    kinds = dict(zip(rows.kind, rows.labels))
    assert any(k.startswith("contrast_") and v == aug.REFUTED for k, v in kinds.items())
    assert rows[rows.Statement == "Thí điểm trong hai năm."].labels.tolist() == [2]   # giữ nhãn NEI
    assert set(rows.sample_weight) == {1.0}
