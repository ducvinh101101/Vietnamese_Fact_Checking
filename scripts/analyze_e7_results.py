"""Compare E7 long-context results with the frozen E2 reference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, default=ROOT / "kaggle/e7_phobert_metrics.json")
    parser.add_argument("--predictions", type=Path, default=ROOT / "kaggle/e7_phobert_test_predictions.csv")
    args = parser.parse_args()
    e2 = pd.read_csv(ROOT / "outputs/predictions/e2_phobert_test_predictions.csv")
    e7 = pd.read_csv(args.predictions)
    if len(e2) != len(e7) or not e2[["Statement", "Evidence", "Url", "labels"]].equals(
        e7[["Statement", "Evidence", "Url", "labels"]]
    ):
        raise ValueError("Test rows E7 không khớp E2; không thể so sánh trực tiếp.")
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    e2_macro = f1_score(e2["labels"], e2["prediction"], average="macro")
    e7_macro = f1_score(e7["labels"], e7["prediction"], average="macro")
    e2_accuracy = accuracy_score(e2["labels"], e2["prediction"])
    e7_accuracy = accuracy_score(e7["labels"], e7["prediction"])
    report = {
        "e2": {"macro_f1": e2_macro, "accuracy": e2_accuracy, "refuted_to_supported": int(((e2.labels == 1) & (e2.prediction == 0)).sum())},
        "e7": {"macro_f1": e7_macro, "accuracy": e7_accuracy, "refuted_to_supported": int(((e7.labels == 1) & (e7.prediction == 0)).sum())},
        "delta": {"macro_f1": e7_macro - e2_macro, "accuracy": e7_accuracy - e2_accuracy},
        "e7_training": metrics.get("training", {}),
        "decision": "replace_e2" if e7_macro > e2_macro else "keep_e2",
    }
    output = ROOT / "outputs/metrics/e2_e7_comparison.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
