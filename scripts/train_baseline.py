"""Huấn luyện E1: TF-IDF word+character n-gram với Linear SVM.

Đánh giá là oracle verification: đầu vào gồm claim và gold evidence.
Tập dev chỉ dùng để chọn C; tập test chỉ dùng cho báo cáo cuối.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed" / "vifactcheck_group_split"
MODEL_PATH = ROOT / "models" / "e1_tfidf_linear_svm.joblib"
METRICS_PATH = ROOT / "outputs" / "metrics" / "e1_tfidf_linear_svm.json"
PREDICTIONS_PATH = ROOT / "outputs" / "predictions" / "e1_test_predictions.csv"
CONFUSION_PATH = ROOT / "outputs" / "metrics" / "e1_confusion_matrix.csv"
LABEL_NAMES = ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]
CS = [0.25, 0.5, 1.0, 2.0]


def pair_text(frame: pd.DataFrame) -> pd.Series:
    return "[CLAIM] " + frame["Statement"].fillna("").astype(str) + " [EVIDENCE] " + frame["Evidence"].fillna("").astype(str)


def create_pipeline(c_value: float) -> Pipeline:
    features = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=120_000)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True, max_features=150_000)),
    ])
    return Pipeline([
        ("features", features),
        ("classifier", LinearSVC(C=c_value, class_weight="balanced", random_state=42)),
    ])


def metrics(y_true: pd.Series, y_pred: list[int]) -> dict[str, object]:
    report = classification_report(y_true, y_pred, labels=[0, 1, 2], target_names=LABEL_NAMES, output_dict=True, zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro")), 4),
        "per_label": {
            label: {
                "precision": round(float(report[label]["precision"]), 4),
                "recall": round(float(report[label]["recall"]), 4),
                "f1": round(float(report[label]["f1-score"]), 4),
                "support": int(report[label]["support"]),
            }
            for label in LABEL_NAMES
        },
    }


def main() -> None:
    train = pd.read_parquet(DATA_DIR / "train.parquet")
    dev = pd.read_parquet(DATA_DIR / "dev.parquet")
    test = pd.read_parquet(DATA_DIR / "test.parquet")
    x_train, y_train = pair_text(train), train["labels"]
    x_dev, y_dev = pair_text(dev), dev["labels"]

    dev_results: dict[str, dict[str, object]] = {}
    best_c = None
    best_score = -1.0
    for c_value in CS:
        model = create_pipeline(c_value)
        model.fit(x_train, y_train)
        current = metrics(y_dev, model.predict(x_dev))
        dev_results[str(c_value)] = current
        if current["macro_f1"] > best_score:
            best_score = current["macro_f1"]
            best_c = c_value

    assert best_c is not None
    selected_model = create_pipeline(best_c)
    selected_model.fit(x_train, y_train)
    test_predictions = selected_model.predict(pair_text(test))
    test_metrics = metrics(test["labels"], test_predictions)
    matrix = confusion_matrix(test["labels"], test_predictions, labels=[0, 1, 2])

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected_model, MODEL_PATH)
    pd.DataFrame(matrix, index=LABEL_NAMES, columns=LABEL_NAMES).to_csv(CONFUSION_PATH, encoding="utf-8")
    prediction_frame = test[["Statement", "Evidence", "Url", "labels"]].copy()
    prediction_frame["prediction"] = test_predictions
    prediction_frame.to_csv(PREDICTIONS_PATH, index=False, encoding="utf-8")

    result = {
        "experiment": "E1",
        "input": "[CLAIM] Statement [EVIDENCE] gold Evidence",
        "split": "grouped by normalized URL; seed=42; 70/15/15",
        "model": "TF-IDF word (1,2) + char_wb (3,5) + LinearSVC(class_weight=balanced)",
        "selection_metric": "dev macro_f1",
        "candidates": CS,
        "selected_c": best_c,
        "dev_results": dev_results,
        "test_metrics": test_metrics,
        "artifacts": {
            "model": str(MODEL_PATH.relative_to(ROOT)),
            "predictions": str(PREDICTIONS_PATH.relative_to(ROOT)),
            "confusion_matrix": str(CONFUSION_PATH.relative_to(ROOT)),
        },
    }
    METRICS_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
