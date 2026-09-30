"""W4-06: fit và lưu model content-risk E9 để dùng ở runtime.

E9 (train_content_baseline.py) chỉ chạy nested CV để **đánh giá**; nó không lưu
một model triển khai được. Script này fit đúng pipeline E9 trên toàn bộ VFND rồi
lưu lại kèm metadata cần thiết cho cảnh báo ngoài phân bố (out-of-distribution).

    py -3.13 scripts/fit_content_risk_model.py

Model được lưu KHÔNG phải verifier và KHÔNG sinh bằng chứng. Điểm nó cho là
"độ giống các bài bị gán FAKE trong tập huấn luyện", không phải xác suất một bài
là tin giả ngoài đời. Xem docs/W4_06_CONTENT_RISK_INTEGRATION.md.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "processed" / "vfnd_content" / "articles.parquet"
DEFAULT_OUT = ROOT / "models" / "e9_content_risk"
CS = (0.25, 0.5, 1.0, 2.0)
SEED = 42
# Ngưỡng dải rủi ro chọn thủ công, cố ý thô. Không có ý nghĩa xác suất tuyệt đối;
# chỉ để hiển thị "thấp / trung bình / cao" thay cho một con số giả chính xác.
BAND_EDGES = (0.34, 0.67)


def content_text(frame: pd.DataFrame) -> pd.Series:
    return "[TITLE] " + frame["title"].fillna("").astype(str) + " [BODY] " + frame["body"].fillna("").astype(str)


def make_base_pipeline(c_value: float) -> Pipeline:
    """Giữ nguyên đặc trưng và tham số của E9 để model triển khai khớp đánh giá."""
    return Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, max_features=80_000)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True, max_features=100_000)),
        ])),
        ("classifier", LinearSVC(C=c_value, class_weight="balanced", random_state=SEED)),
    ])


def select_c(frame: pd.DataFrame) -> float:
    splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED)
    text, labels, groups = content_text(frame), frame["label"], frame["source_domain"]
    scores = {c: [] for c in CS}
    for train_index, validation_index in splitter.split(text, labels, groups):
        for c_value in CS:
            model = make_base_pipeline(c_value)
            model.fit(text.iloc[train_index], labels.iloc[train_index])
            prediction = model.predict(text.iloc[validation_index])
            scores[c_value].append(f1_score(labels.iloc[validation_index], prediction, average="macro", zero_division=0))
    return max(CS, key=lambda c_value: (sum(scores[c_value]) / len(scores[c_value]), -c_value))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    frame = pd.read_parquet(args.data).reset_index(drop=True)
    required = {"article_id", "title", "body", "url", "source_domain", "label"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"VFND content data thiếu cột: {sorted(missing)}")
    if frame["label"].nunique() != 2:
        raise ValueError("Content-risk yêu cầu đủ hai nhãn REAL và FAKE")

    # C chọn trên toàn bộ dữ liệu bằng cùng thủ tục group-CV như E9.
    c_value = select_c(frame)
    text, labels = content_text(frame), frame["label"]
    model = CalibratedClassifierCV(make_base_pipeline(c_value), method="sigmoid", cv=3)
    model.fit(text, labels)

    args.out.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.out / "model.joblib")

    metadata = {
        "experiment": "E9 content-risk, fitted on full VFND for deployment",
        "task": "binary content-risk; NOT claim verification, NOT evidence",
        "risk_score_meaning": (
            "P(class=FAKE) theo văn phong/nguồn của tập huấn luyện; không phải xác suất "
            "một bài là tin giả ngoài đời."
        ),
        "input": "[TITLE] title [BODY] body",
        "selected_c": c_value,
        "seed": SEED,
        "positive_label_index": 1,
        "band_edges": list(BAND_EDGES),
        "band_names": ["thấp", "trung bình", "cao"],
        "n_training_records": int(len(frame)),
        "training_source_domains": sorted(frame["source_domain"].dropna().astype(str).unique().tolist()),
        "domain_confounding_warning": (
            "Mỗi source_domain trong VFND chỉ có một nhãn. Điểm trên một nguồn ngoài danh "
            "sách training gần như vô nghĩa; runtime phải gắn cờ out-of-distribution."
        ),
        "fitted_on": date.today().isoformat(),
    }
    (args.out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã lưu model content-risk vào {args.out} (C={c_value}, {len(frame)} bài).")


if __name__ == "__main__":
    main()
