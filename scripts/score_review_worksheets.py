"""Chấm ba worksheet đọc tay của W5-06 và W5-03a.

Script chỉ đọc file đã được người điền và tính thống kê; nó không gán nhãn,
không gọi model và không sửa dữ liệu gốc. Dòng chưa điền bị bỏ qua và được
báo riêng để không âm thầm tính thiếu.

Ba chế độ:

    py -3.13 scripts/score_review_worksheets.py --adjudication data/evaluation/train_pair_human_adjudication_v1_worksheet.csv
    py -3.13 scripts/score_review_worksheets.py --spotcheck   data/evaluation/train_pair_silver_spotcheck_v1_worksheet.csv --key data/evaluation/train_pair_silver_spotcheck_v1_key.csv
    py -3.13 scripts/score_review_worksheets.py --citation    data/evaluation/citation_faithfulness_audit_v1_worksheet.csv

Thêm --output PATH để ghi JSON; script từ chối ghi đè file đã tồn tại.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from math import sqrt
from pathlib import Path

import pandas as pd

LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
FAITHFUL_VALUES = ("CO", "KHONG", "KHONG_CHAC")


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Khoảng tin cậy Wilson 95%. Giả định các mẫu độc lập."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z**2 / total
    centre = p + z**2 / (2 * total)
    margin = z * sqrt(p * (1 - p) / total + z**2 / (4 * total**2))
    return ((centre - margin) / denominator, (centre + margin) / denominator)


def normalize(value: object) -> str:
    return str(value).strip().upper() if pd.notna(value) else ""


def cohen_kappa(a: list[str], b: list[str], labels: tuple[str, ...]) -> float:
    """Kappa cho hai lượt gán nhãn trên cùng các mục."""
    if len(a) != len(b) or not a:
        raise ValueError("Hai chuỗi nhãn phải cùng độ dài và khác rỗng")
    total = len(a)
    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / total
    count_a, count_b = Counter(a), Counter(b)
    expected = sum((count_a[label] / total) * (count_b[label] / total) for label in labels)
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def read_worksheet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Không thấy worksheet: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def score_adjudication(path: Path) -> dict:
    """53 cặp needs_human_review: thống kê nhãn người đã phân xử."""
    frame = read_worksheet(path)
    for column in ("pair_id", "reviewed_pair_label", "reviewer"):
        if column not in frame.columns:
            raise ValueError(f"Worksheet phân xử thiếu cột {column}")

    frame["label"] = frame.reviewed_pair_label.map(normalize)
    filled = frame[frame.label != ""]
    invalid = sorted(set(filled.label) - set(LABELS))
    if invalid:
        raise ValueError(f"Nhãn không hợp lệ: {invalid}. Chỉ nhận {list(LABELS)}")
    missing_reviewer = int((filled.reviewer.map(normalize) == "").sum())

    return {
        "worksheet": str(path),
        "total_rows": int(len(frame)),
        "reviewed": int(len(filled)),
        "pending": int(len(frame) - len(filled)),
        "rows_missing_reviewer_name": missing_reviewer,
        "label_counts": {label: int((filled.label == label).sum()) for label in LABELS},
        "note": "Nhãn người phân xử. Chỉ hợp lệ khi đủ tên người duyệt và lý do.",
    }


def score_spotcheck(path: Path, key_path: Path) -> dict:
    """50 cặp silver: đồng thuận giữa người và nhãn AI."""
    frame = read_worksheet(path)
    key = read_worksheet(key_path)
    if "ai_label_hidden" not in key.columns:
        raise ValueError("File key thiếu cột ai_label_hidden")

    merged = frame.merge(key, on="pair_id", how="inner", validate="one_to_one")
    if len(merged) != len(frame):
        raise ValueError("pair_id giữa worksheet và key không khớp một-một")

    merged["human"] = merged.reviewed_pair_label.map(normalize)
    merged["ai"] = merged.ai_label_hidden.map(normalize)
    filled = merged[merged.human != ""]
    invalid = sorted(set(filled.human) - set(LABELS))
    if invalid:
        raise ValueError(f"Nhãn không hợp lệ: {invalid}")
    if filled.empty:
        raise ValueError("Chưa có dòng nào được điền")

    agree = int((filled.human == filled.ai).sum())
    per_label = {}
    for label in LABELS:
        subset = filled[filled.ai == label]
        per_label[label] = {
            "ai_proposed": int(len(subset)),
            "human_agreed": int((subset.human == label).sum()),
            "agreement_rate": round(float((subset.human == label).mean()), 4) if len(subset) else None,
        }
    low, high = wilson_interval(agree, len(filled))
    confusion = (
        filled.groupby(["ai", "human"]).size().reset_index(name="n").to_dict("records")
    )
    return {
        "worksheet": str(path),
        "key": str(key_path),
        "reviewed": int(len(filled)),
        "pending": int(len(merged) - len(filled)),
        "overall_agreement": round(agree / len(filled), 4),
        "overall_agreement_wilson_95": [round(low, 4), round(high, 4)],
        "cohen_kappa": round(cohen_kappa(list(filled.human), list(filled.ai), LABELS), 4),
        "per_ai_label": per_label,
        "ai_vs_human": confusion,
        "note": (
            "Đồng thuận cao không chứng minh nhãn AI đúng; nó chỉ nói người và AI đọc "
            "giống nhau trên mẫu này. Mẫu được phân tầng nên tỷ lệ tổng không đại diện "
            "cho phân bố thật của 487 cặp."
        ),
    }


def score_citation(path: Path, key_path: Path | None) -> dict:
    """50 citation: đoạn được trích có thực sự đủ để kết luận không."""
    frame = read_worksheet(path)
    for column in ("audit_id", "du_doan_cua_he_thong", "doan_co_du_de_ket_luan"):
        if column not in frame.columns:
            raise ValueError(f"Worksheet citation thiếu cột {column}")

    frame["verdict"] = frame.doan_co_du_de_ket_luan.map(normalize)
    filled = frame[frame.verdict != ""]
    invalid = sorted(set(filled.verdict) - set(FAITHFUL_VALUES))
    if invalid:
        raise ValueError(f"Giá trị không hợp lệ: {invalid}. Chỉ nhận {list(FAITHFUL_VALUES)}")
    if filled.empty:
        raise ValueError("Chưa có dòng nào được điền")

    faithful = int((filled.verdict == "CO").sum())
    low, high = wilson_interval(faithful, len(filled))

    per_prediction = {}
    for label in ("SUPPORTED", "REFUTED"):
        subset = filled[filled.du_doan_cua_he_thong.map(normalize) == label]
        if len(subset):
            per_prediction[label] = {
                "reviewed": int(len(subset)),
                "faithful": int((subset.verdict == "CO").sum()),
                "rate": round(float((subset.verdict == "CO").mean()), 4),
            }

    result = {
        "worksheet": str(path),
        "reviewed": int(len(filled)),
        "pending": int(len(frame) - len(filled)),
        "faithful": faithful,
        "faithfulness_rate": round(faithful / len(filled), 4),
        "faithfulness_wilson_95": [round(low, 4), round(high, 4)],
        "breakdown": {value: int((filled.verdict == value).sum()) for value in FAITHFUL_VALUES},
        "per_prediction": per_prediction,
        "note": (
            "Đây là phép đo passage-level đầu tiên của dự án. Nó KHÁC citation URL-match: "
            "URL đúng không đồng nghĩa đoạn đủ để entail hay refute claim. Mẫu được phân "
            "tầng có chủ ý theo nhãn và theo việc URL có khớp annotation hay không."
        ),
    }

    if key_path is not None:
        key = read_worksheet(key_path)
        merged = filled.merge(key, on="audit_id", how="inner", validate="one_to_one")
        if "nhan_dung_theo_doan_nay" in merged.columns:
            human = merged.nhan_dung_theo_doan_nay.map(normalize)
            has_label = merged[human.isin(LABELS)]
            if len(has_label):
                human_label = has_label.nhan_dung_theo_doan_nay.map(normalize)
                result["verdict_vs_human_reading"] = {
                    "reviewed": int(len(has_label)),
                    "system_matches_human": int(
                        (has_label.du_doan_cua_he_thong.map(normalize) == human_label).sum()
                    ),
                }
        result["url_match_vs_faithfulness"] = [
            {
                "citation_url_matches_gold": bool(flag),
                "reviewed": int(len(group)),
                "faithful": int((group.verdict == "CO").sum()),
            }
            for flag, group in merged.groupby("citation_url_matches_gold")
        ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Chấm worksheet đọc tay W5-06 và W5-03a")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--adjudication", type=Path, help="Worksheet 53 cặp phân xử")
    mode.add_argument("--spotcheck", type=Path, help="Worksheet 50 cặp silver")
    mode.add_argument("--citation", type=Path, help="Worksheet 50 citation")
    parser.add_argument("--key", type=Path, help="File key đi kèm (spotcheck bắt buộc)")
    parser.add_argument("--output", type=Path, help="Ghi kết quả JSON; không ghi đè file cũ")
    args = parser.parse_args()

    if args.adjudication:
        report = score_adjudication(args.adjudication)
    elif args.spotcheck:
        if args.key is None:
            raise SystemExit("--spotcheck cần --key")
        report = score_spotcheck(args.spotcheck, args.key)
    else:
        report = score_citation(args.citation, args.key)

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        if args.output.exists():
            raise SystemExit(f"Từ chối ghi đè: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"\nĐã ghi {args.output}")


if __name__ == "__main__":
    main()
