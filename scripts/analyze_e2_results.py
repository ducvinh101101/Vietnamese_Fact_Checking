"""Nhập kết quả Kaggle E2, kiểm tra và so sánh với baseline E1."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score


ROOT = Path(__file__).resolve().parents[1]
KAGGLE_DIR = ROOT / "kaggle"
METRICS_DIR = ROOT / "outputs" / "metrics"
PREDICTIONS_DIR = ROOT / "outputs" / "predictions"
LABEL_NAMES = ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


def main() -> None:
    source_metrics = KAGGLE_DIR / "e2_phobert_metrics.json"
    source_predictions = KAGGLE_DIR / "e2_phobert_test_predictions.csv"
    e1_path = METRICS_DIR / "e1_tfidf_linear_svm.json"
    metrics = json.loads(source_metrics.read_text(encoding="utf-8"))
    predictions = pd.read_csv(source_predictions)
    required = {"Statement", "Evidence", "Url", "labels", "prediction"}
    if missing := required - set(predictions.columns):
        raise ValueError(f"Thiếu cột trong predictions: {sorted(missing)}")
    if len(predictions) != 1076 or predictions[["labels", "prediction"]].isna().any().any():
        raise ValueError("Predictions E2 không đúng số mẫu hoặc có nhãn rỗng")
    if set(predictions["labels"].unique()) - {0, 1, 2} or set(predictions["prediction"].unique()) - {0, 1, 2}:
        raise ValueError("Có nhãn ngoài tập 0, 1, 2")

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_metrics, METRICS_DIR / source_metrics.name)
    shutil.copy2(source_predictions, PREDICTIONS_DIR / source_predictions.name)
    matrix = confusion_matrix(predictions["labels"], predictions["prediction"], labels=[0, 1, 2])
    pd.DataFrame(matrix, index=LABEL_NAMES, columns=LABEL_NAMES).to_csv(METRICS_DIR / "e2_phobert_confusion_matrix.csv", encoding="utf-8")

    e1 = json.loads(e1_path.read_text(encoding="utf-8"))
    e1_metrics = e1["test_metrics"]
    e2_macro_f1 = float(metrics["test_metrics"]["test_macro_f1"])
    comparison = {
        "protocol": "grouped by normalized URL; seed=42; 70/15/15; claim + gold evidence",
        "E1": {"model": e1["model"], "test_macro_f1": e1_metrics["macro_f1"], "test_accuracy": e1_metrics["accuracy"]},
        "E2": {"model": metrics["model"], "test_macro_f1": e2_macro_f1, "test_accuracy": float(metrics["test_metrics"]["test_accuracy"])},
        "delta": {
            "macro_f1_points": round((e2_macro_f1 - float(e1_metrics["macro_f1"])) * 100, 2),
            "accuracy_points": round((float(metrics["test_metrics"]["test_accuracy"]) - float(e1_metrics["accuracy"])) * 100, 2),
        },
        "E2_recomputed_macro_f1": round(float(f1_score(predictions["labels"], predictions["prediction"], average="macro")), 6),
        "E2_confusion_matrix": matrix.tolist(),
    }
    (METRICS_DIR / "e1_e2_comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
