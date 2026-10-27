"""Sinh hard negative RT-V3 (scripts/build_hard_negative_finetune_v3.py) và bộ ca demo W4-04."""

from __future__ import annotations

import random

import pandas as pd
import pytest

from scripts.build_hard_negative_finetune_v3 import (
    build, is_single_flip, perturb_direction, perturb_negation, perturb_number,
)
from src.demo_cases import DEMO_CASES
from src.schemas import Evidence, RetrievedEvidence, VerificationResult
from src.system_builder import SystemOptions, build_system

CLAIM = "Doanh thu của tập đoàn đã tăng lên 12% so với năm trước nhờ thị trường nội địa phục hồi"


def test_each_perturbation_is_exactly_one_flip_of_the_right_kind():
    rng = random.Random(0)
    number = perturb_number(CLAIM, CLAIM, rng)
    direction = perturb_direction(CLAIM, CLAIM, rng)
    negation = perturb_negation(CLAIM, CLAIM, rng)
    assert number and "12%" not in number and is_single_flip(CLAIM, number, "number")
    assert direction and "giảm" in direction and is_single_flip(CLAIM, direction, "direction")
    assert negation and is_single_flip(CLAIM, negation, "negation")


def test_perturbations_skip_compounds_and_already_negated_claims():
    rng = random.Random(0)
    assert perturb_direction("Bộ chỉ đạo tăng cường kiểm tra an toàn thực phẩm dịp Tết", "tăng cường kiểm tra", rng) is None
    assert perturb_negation("Dự án chưa được phê duyệt trong năm nay theo kế hoạch", "", rng) is None
    assert perturb_negation("Người dân có thể đăng ký trực tuyến từ tuần sau", "", rng) is None
    assert perturb_number("Không có số nào trong câu này cả", "", rng) is None
    assert not is_single_flip(CLAIM, CLAIM, "number")


def _frame(rows):
    return pd.DataFrame(rows, columns=["Statement", "Evidence", "Url", "labels"])


def test_build_keeps_base_rows_adds_weighted_synthetic_and_refuses_heldout_urls():
    train = _frame([
        (CLAIM, CLAIM + ".", "https://a.vn/1", 0),
        ("Giá vàng trong nước đã tăng 500 nghìn đồng mỗi lượng sáng nay tại Hà Nội", 
         "Giá vàng trong nước đã tăng 500 nghìn đồng mỗi lượng sáng nay tại Hà Nội.", "https://a.vn/2", 0),
        ("Đội tuyển nữ Việt Nam thắng Myanmar 2-1 ở bán kết giải Đông Nam Á",
         "Thời tiết miền Bắc chuyển lạnh từ đêm nay, nhiệt độ thấp nhất 12 độ.", "https://a.vn/3", 2),
    ])
    base = train.assign(label_origin="original_gold_train", sample_weight=1.0)
    combined, synthetic = build(train, base, held_urls={"https://dev.vn/x"}, per_kind=1, nei_count=1, seed=1)
    assert len(combined) == len(base) + len(synthetic) and len(synthetic) >= 2
    assert set(synthetic["sample_weight"]) == {0.5}
    assert set(synthetic.loc[synthetic.label_origin.str.startswith("synthetic_refuted"), "labels"]) == {1}
    with pytest.raises(ValueError):
        build(train, base, held_urls={"https://a.vn/1"}, per_kind=1, nei_count=1, seed=1)


class AlwaysNEI:
    def verify(self, claim, items):
        return VerificationResult("NOT_ENOUGH_INFO", 0.5, [], "fixed")


class OneSource:
    def __init__(self, text): self.text = text
    def search(self, claim, top_k=3):
        return [RetrievedEvidence(Evidence("d", "p1", self.text, url="https://vnexpress.net/x.html"), 1.0)]


@pytest.mark.parametrize("case_id, expected", [("D1", "SUPPORTED"), ("D2", "REFUTED"), ("D3", "REFUTED")])
def test_demo_minimal_pair_cases_hold_regardless_of_model(case_id, expected):
    """D1–D3 dựa vào luật cặp-tối-thiểu nên đúng kỳ vọng kể cả khi mô hình trả NEI."""
    case = next(c for c in DEMO_CASES if c["id"] == case_id)
    source = DEMO_CASES[0]["claim"]          # câu gốc trong kho (vifactcheck_01030_p001)
    system = build_system(SystemOptions(mode="local", engine="rule_based"), verifier=AlwaysNEI())
    system.pipeline.retriever = OneSource(source)
    response = system.check(case["claim"])
    assert response["verdict"]["label"] == expected == case["expected"]
    assert response["diagnostics"]["minimal_pair_reason"]


def test_demo_cases_are_well_formed():
    ids = [case["id"] for case in DEMO_CASES]
    assert len(ids) == len(set(ids)) and all(case["mode"] in {"local", "hybrid"} for case in DEMO_CASES)
