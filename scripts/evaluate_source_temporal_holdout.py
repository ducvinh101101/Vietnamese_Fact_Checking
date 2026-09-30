"""W5-03b: external validity — chia đánh giá theo NGUỒN và THỜI GIAN.

Hậu xử lý một file predictions đã có (đầu ra của evaluate_local_end_to_end.py
hoặc evaluate_reranked_end_to_end.py). Không chạy lại model. Trả Macro-F1 và F1
từng nhãn cho mỗi nhóm nguồn (domain của gold_url) và, nếu có cột ngày, cho mỗi
mốc thời gian. Mục đích: xem model có tổng quát sang nguồn/thời điểm mà nó gặp ít
hay không, thay vì chỉ một số tổng gộp.

    py -3.13 scripts/evaluate_source_temporal_holdout.py --predictions outputs/predictions/reranked_e2e_test.csv --metrics outputs/metrics/w5_03b_source_temporal.json

Cột bắt buộc trong CSV: gold_label, predicted_label, gold_url.
Cột thời gian (tùy chọn): published_at hoặc observed_at (ISO date).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
from sklearn.metrics import f1_score

LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
MIN_GROUP = 15  # nhóm nhỏ hơn ngưỡng này gộp vào "small_sources_pooled"


def domain_of(url: str) -> str:
    try:
        host = (urlsplit(str(url)).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


def group_metrics(frame: pd.DataFrame) -> dict:
    y_true = frame["gold_label"].tolist()
    y_pred = frame["predicted_label"].tolist()
    per = f1_score(y_true, y_pred, labels=LABELS, average=None, zero_division=0)
    return {
        "n": int(len(frame)),
        "accuracy": round(float((frame["gold_label"] == frame["predicted_label"]).mean()), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)), 4),
        "f1_per_label": {label: round(float(value), 4) for label, value in zip(LABELS, per)},
        "gold_label_counts": {label: int((frame["gold_label"] == label).sum()) for label in LABELS},
    }


def by_source(frame: pd.DataFrame, min_group: int = MIN_GROUP) -> dict:
    frame = frame.assign(_domain=frame["gold_url"].map(domain_of))
    sizes = frame["_domain"].value_counts()
    big = sizes[sizes >= min_group].index
    result = {domain: group_metrics(frame[frame._domain == domain]) for domain in big}
    small = frame[~frame._domain.isin(big)]
    if len(small):
        result["small_sources_pooled"] = group_metrics(small) | {"n_domains": int(small._domain.nunique())}
    return result


def by_time(frame: pd.DataFrame, date_column: str, bins: int = 3) -> dict:
    dates = pd.to_datetime(frame[date_column], errors="coerce", utc=True)
    valid = frame[dates.notna()].assign(_date=dates[dates.notna()])
    if valid.empty:
        return {"note": f"Cột {date_column} không có ngày hợp lệ"}
    valid = valid.sort_values("_date")
    try:
        valid["_bucket"] = pd.qcut(valid["_date"].astype("int64"), q=bins, duplicates="drop")
    except ValueError:
        return {"note": "Không đủ đa dạng ngày để chia mốc thời gian"}
    out = {}
    for bucket, group in valid.groupby("_bucket", observed=True):
        span = f"{group._date.min().date()} → {group._date.max().date()}"
        out[span] = group_metrics(group.drop(columns=["_date", "_bucket"]))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, help="Ghi JSON; không có thì in stdout")
    parser.add_argument("--min-group", type=int, default=MIN_GROUP)
    args = parser.parse_args()

    frame = pd.read_csv(args.predictions)
    required = {"gold_label", "predicted_label", "gold_url"}
    missing = required.difference(frame.columns)
    if missing:
        raise SystemExit(f"Predictions thiếu cột: {sorted(missing)}")
    bad = set(frame["gold_label"]).union(frame["predicted_label"]) - set(LABELS)
    if bad:
        raise SystemExit(f"Nhãn ngoài tập cho phép: {sorted(bad)}")

    report = {
        "analysis": "W5-03b source/temporal held-out external validity",
        "source": str(args.predictions),
        "overall": group_metrics(frame),
        "by_source": by_source(frame, args.min_group),
        "note": (
            "Source-held-out: mỗi nhóm là các claim có gold_url cùng domain. Chênh lệch "
            "Macro-F1 giữa domain lớn cho biết model phụ thuộc nguồn tới đâu. Domain nhỏ "
            f"(<{args.min_group} claim) được gộp. Đây vẫn là dữ liệu ViFactCheck, không phải "
            "held-out thời sự thật ngoài đời."
        ),
    }
    date_column = next((c for c in ("published_at", "observed_at", "date") if c in frame.columns), None)
    report["by_time"] = by_time(frame, date_column) if date_column else {
        "note": "Không có cột thời gian trong predictions; bỏ qua phần temporal."
    }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text[:1500])
    if args.metrics:
        args.metrics.parent.mkdir(parents=True, exist_ok=True)
        args.metrics.write_text(text + "\n", encoding="utf-8")
        print(f"\nĐã ghi {args.metrics}")


if __name__ == "__main__":
    main()
