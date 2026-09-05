"""E9: nested source-domain CV cho baseline content-risk VFND article-only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "processed" / "vfnd_content" / "articles.parquet"
CS = (0.25, 0.5, 1.0, 2.0)
SEED = 42


def content_text(frame: pd.DataFrame) -> pd.Series:
    return "[TITLE] " + frame["title"].fillna("").astype(str) + " [BODY] " + frame["body"].fillna("").astype(str)


def make_base_pipeline(c_value: float) -> Pipeline:
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
    scores: dict[float, list[float]] = {c: [] for c in CS}
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
    parser.add_argument("--metrics", type=Path, default=ROOT / "outputs" / "metrics" / "e9_vfnd_content_baseline.json")
    parser.add_argument("--predictions", type=Path, default=ROOT / "outputs" / "predictions" / "e9_vfnd_content_oof_predictions.csv")
    args = parser.parse_args()

    frame = pd.read_parquet(args.data).reset_index(drop=True)
    required = {"article_id", "title", "body", "url", "source_domain", "label"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"VFND content data thiếu cột: {sorted(missing)}")
    if frame["label"].nunique() != 2:
        raise ValueError("E9 yêu cầu đủ hai nhãn REAL và FAKE")

    text, labels, groups = content_text(frame), frame["label"], frame["source_domain"]
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    oof_label = pd.Series(index=frame.index, dtype="int64")
    oof_score = pd.Series(index=frame.index, dtype="float64")
    selected_cs: list[float] = []
    folds: list[dict[str, object]] = []
    for fold, (train_index, test_index) in enumerate(outer.split(text, labels, groups)):
        train = frame.iloc[train_index].reset_index(drop=True)
        c_value = select_c(train)
        selected_cs.append(c_value)
        calibrated = CalibratedClassifierCV(make_base_pipeline(c_value), method="sigmoid", cv=3)
        calibrated.fit(text.iloc[train_index], labels.iloc[train_index])
        probabilities = calibrated.predict_proba(text.iloc[test_index])[:, 1]
        prediction = (probabilities >= 0.5).astype(int)
        oof_label.iloc[test_index] = prediction
        oof_score.iloc[test_index] = probabilities
        folds.append({
            "fold": fold,
            "selected_c": c_value,
            "train_records": int(len(train_index)),
            "test_records": int(len(test_index)),
            "test_domains": int(groups.iloc[test_index].nunique()),
            "test_label_distribution": {str(key): int(value) for key, value in labels.iloc[test_index].value_counts().sort_index().items()},
        })

    report = classification_report(labels, oof_label, labels=[0, 1], target_names=["REAL", "FAKE"], output_dict=True, zero_division=0)
    metrics = {
        "experiment": "E9",
        "task": "binary content-risk classification; not claim verification and not evidence",
        "dataset": "VFND article-only, revision v1.1.1",
        "input": "[TITLE] title [BODY] body",
        "protocol": "nested StratifiedGroupKFold by source_domain; 5 outer folds, 3 inner folds, seed=42",
        "domain_confounding_note": "Each VFND source_domain has one label in this release; source-held-out OOF evaluation is intentionally strict.",
        "model": "TF-IDF word (1,2) + char_wb (3,5) + calibrated LinearSVC(class_weight=balanced)",
        "metrics": {
            "macro_f1": round(float(f1_score(labels, oof_label, average="macro", zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(labels, oof_score)), 4),
            "per_label": {
                label: {key: round(float(value), 4) if isinstance(value, float) else int(value) for key, value in report[label].items()}
                for label in ("REAL", "FAKE")
            },
            "confusion_matrix": confusion_matrix(labels, oof_label, labels=[0, 1]).tolist(),
        },
        "folds": folds,
        "selected_c_per_outer_fold": selected_cs,
        "artifacts": {"predictions": str(args.predictions.relative_to(ROOT))},
    }
    output = frame[["article_id", "url", "source_domain", "label"]].copy()
    output["prediction"] = oof_label.astype(int)
    output["fake_risk_score"] = oof_score.round(6)
    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.predictions, index=False, encoding="utf-8")
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
