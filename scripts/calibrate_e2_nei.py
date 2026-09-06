"""E6: chọn temperature và ngưỡng NEI PhoBERT chỉ bằng tập dev gold-evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.decision_policy import apply_decisive_threshold, softmax
from src.phobert_fact_checker import PhoBERTFactChecker


LABELS = ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    import torch

    logits_tensor = torch.tensor(logits, dtype=torch.float32)
    labels_tensor = torch.tensor(labels, dtype=torch.long)
    temperature = torch.nn.Parameter(torch.ones(1))
    optimizer = torch.optim.LBFGS([temperature], lr=0.1, max_iter=100)
    loss = torch.nn.CrossEntropyLoss()

    def closure():
        optimizer.zero_grad()
        value = loss(logits_tensor / temperature.clamp(min=0.05, max=20), labels_tensor)
        value.backward()
        return value

    optimizer.step(closure)
    return float(temperature.detach().clamp(min=0.05, max=20).item())


def probabilities(logits: np.ndarray, temperature: float) -> np.ndarray:
    return np.asarray([softmax(row, temperature) for row in logits], dtype=float)


def ece(values: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    confidence = values.max(axis=1)
    predicted = values.argmax(axis=1)
    result = 0.0
    for lower, upper in zip(np.linspace(0, 1, bins, endpoint=False), np.linspace(0, 1, bins + 1)[1:]):
        mask = (confidence >= lower) & ((confidence < upper) if upper < 1 else (confidence <= upper))
        if mask.any():
            result += mask.mean() * abs((predicted[mask] == labels[mask]).mean() - confidence[mask].mean())
    return float(result)


def calibration_metrics(values: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    one_hot = np.eye(len(LABELS))[labels]
    return {
        "macro_f1": float(f1_score(labels, values.argmax(axis=1), average="macro", zero_division=0)),
        "ece_10": ece(values, labels),
        "multiclass_brier": float(np.mean(np.sum((values - one_hot) ** 2, axis=1))),
    }


def choose_threshold(values: np.ndarray, labels: np.ndarray) -> tuple[float, np.ndarray, float]:
    best: tuple[float, np.ndarray, float] | None = None
    for threshold in np.linspace(0, 0.95, 96):
        predicted = np.asarray([LABELS.index(apply_decisive_threshold(row, float(threshold))[0]) for row in values])
        score = float(f1_score(labels, predicted, average="macro", zero_division=0))
        candidate = (float(threshold), predicted, score)
        if best is None or score > best[2] + 1e-12 or (score == best[2] and threshold < best[0]):
            best = candidate
    assert best is not None
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed/vifactcheck_group_split/dev.parquet")
    parser.add_argument("--model-path", type=Path, default=ROOT / "models/e2_phobert/best_model")
    parser.add_argument("--vncorenlp-dir", type=Path, default=ROOT / "models/vncorenlp")
    parser.add_argument("--predictions", type=Path, default=ROOT / "outputs/predictions/e6_e2_dev_calibration.csv")
    parser.add_argument("--metrics", type=Path, default=ROOT / "outputs/metrics/e6_e2_nei_calibration.json")
    args = parser.parse_args()

    frame = pd.read_parquet(args.data).reset_index(drop=True)
    required = {"index", "Statement", "Evidence", "Url", "labels"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Dev data thiếu cột: {sorted(missing)}")
    if frame[["Statement", "Evidence", "Url", "labels"]].isna().any().any():
        raise ValueError("Dev data có claim/evidence/URL/label trống")

    checker = PhoBERTFactChecker(args.model_path, args.vncorenlp_dir)
    print(f"E6: scoring {len(frame)} dev claim--gold-evidence pairs...", flush=True)
    scored_logits: list[list[float]] = []
    for row_number, row in enumerate(frame.itertuples(index=False), start=1):
        scored_logits.append(checker.predict_logits(str(row.Statement), str(row.Evidence)))
        if row_number % 100 == 0 or row_number == len(frame):
            print(f"E6: scored {row_number}/{len(frame)}", flush=True)
    logits = np.asarray(scored_logits, dtype=float)
    labels = frame["labels"].astype(int).to_numpy()
    groups = frame["Url"].astype(str).to_numpy()
    splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
    oof_probabilities = np.zeros_like(logits)
    folds: list[dict[str, object]] = []
    for fold, (fit_index, evaluate_index) in enumerate(splitter.split(logits, labels, groups)):
        temperature = fit_temperature(logits[fit_index], labels[fit_index])
        oof_probabilities[evaluate_index] = probabilities(logits[evaluate_index], temperature)
        folds.append({"fold": fold, "fit_records": int(len(fit_index)), "dev_records": int(len(evaluate_index)), "temperature": round(temperature, 6)})

    final_temperature = fit_temperature(logits, labels)
    raw_probabilities = probabilities(logits, 1.0)
    threshold, threshold_predictions, threshold_macro_f1 = choose_threshold(oof_probabilities, labels)
    report = classification_report(labels, threshold_predictions, labels=[0, 1, 2], target_names=LABELS, output_dict=True, zero_division=0)
    raw_predictions = raw_probabilities.argmax(axis=1)
    calibrated_predictions = oof_probabilities.argmax(axis=1)
    output = frame[["index", "Url", "labels"]].copy()
    output["raw_prediction"] = raw_predictions
    output["calibrated_prediction"] = calibrated_predictions
    output["nei_policy_prediction"] = threshold_predictions
    output["raw_confidence"] = raw_probabilities.max(axis=1).round(6)
    output["calibrated_confidence"] = oof_probabilities.max(axis=1).round(6)
    for label_index, label in enumerate(LABELS):
        output[f"raw_probability_{label}"] = raw_probabilities[:, label_index].round(6)
        output[f"calibrated_probability_{label}"] = oof_probabilities[:, label_index].round(6)
        output[f"raw_logit_{label}"] = logits[:, label_index].round(6)
    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.predictions, index=False)
    result = {
        "experiment": "E6",
        "task": "PhoBERT verifier calibration and NEI abstention; oracle gold-evidence only",
        "data": str(args.data.relative_to(ROOT)),
        "records": int(len(frame)),
        "protocol": "3-fold StratifiedGroupKFold by Url on dev; temperature fit on fold-train; threshold chosen on calibrated dev OOF; test untouched",
        "labels": LABELS,
        "calibration": {
            "raw": calibration_metrics(raw_probabilities, labels),
            "oof_temperature": calibration_metrics(oof_probabilities, labels),
            "folds": folds,
            "final_temperature_fit_on_all_dev": round(final_temperature, 6),
        },
        "nei_policy": {
            "decisive_min_confidence": round(threshold, 6),
            "oof_macro_f1": threshold_macro_f1,
            "confusion_matrix": confusion_matrix(labels, threshold_predictions, labels=[0, 1, 2]).tolist(),
            "per_label": {label: {key: float(value) for key, value in report[label].items()} for label in LABELS},
        },
        "artifacts": {"predictions": str(args.predictions.relative_to(ROOT))},
        "limitations": [
            "Calibration and threshold selection use dev, which was also used for E2 early stopping; they are selection results, not final generalization estimates.",
            "This is oracle gold-evidence calibration. It does not establish retrieval relevance gating or end-to-end quality.",
        ],
    }
    args.metrics.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
