"""Select AGG-V1 calibration/threshold on cached dev OOF; never open test.

These are development selection scores, not an independent quality estimate.
The base verifier and its temperature have previously used this dev set.
"""
import json
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score, log_loss

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.learned_evidence_policy import aggregation_features
from src.decision_policy import LABELS


def apply_guard(probs, pairs, scores, threshold):
    predicted = probs.argmax(1)
    agreed = np.array([any(s > 0 and int(p.argmax()) == label for p, s in zip(row, sc))
                       for row, sc, label in zip(pairs, scores, predicted)])
    rejected = (predicted != 2) & ((probs.max(1) < threshold) | ~agreed)
    out = predicted.copy()
    out[rejected] = 2
    return out, rejected


def main():
    cache = ROOT / "outputs/predictions/e11_dev_rank_aware_candidates.csv"
    model_path = ROOT / "models/aggregation/dev_logistic_v1.json"
    model_data = json.loads(model_path.read_text())
    if hashlib.sha256(cache.read_bytes()).hexdigest() != model_data["training_cache_sha256"]:
        raise ValueError("Training cache does not match deployed model")
    frame = pd.read_csv(cache)
    pairs = np.array([json.loads(s) for s in frame.candidate_probabilities])
    scores = np.array([[hit["score"] for hit in json.loads(s)] for s in frame.retrieved])
    x = np.array([aggregation_features(p.tolist(), s.tolist()) for p, s in zip(pairs, scores)])
    y = np.array([LABELS.index(s) for s in frame.gold_label])
    logits = np.zeros((len(y), 3))
    fold_ids = np.zeros(len(y), dtype=int)
    for fold, (train, valid) in enumerate(StratifiedGroupKFold(5, shuffle=True, random_state=42).split(x, y, frame.gold_url)):
        assert not set(frame.gold_url.iloc[train]) & set(frame.gold_url.iloc[valid])
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000, random_state=42))
        m.fit(x[train], y[train])
        logits[valid] = m.decision_function(x[valid])
        fold_ids[valid] = fold

    def probabilities(t):
        values = logits / t
        values -= values.max(axis=1, keepdims=True)
        values = np.exp(values)
        return values / values.sum(axis=1, keepdims=True)

    temperatures = [0.7, 0.85, 1.0, 1.15, 1.3, 1.5, 1.8, 2.0]
    temperature = min(temperatures, key=lambda t: log_loss(y, probabilities(t)))
    calibrated = probabilities(temperature)
    grid = []
    for threshold in [0.0, 0.4, 0.5, 0.6, 0.7, 0.8]:
        pred, rejected = apply_guard(calibrated, pairs, scores, threshold)
        grid.append(dict(threshold=threshold, accuracy=float(accuracy_score(y, pred)),
                         macro_f1=float(f1_score(y, pred, average="macro")), guard_rejections=int(rejected.sum())))
    selected = max(grid, key=lambda r: (r["macro_f1"], -r["threshold"]))
    pred, rejected = apply_guard(calibrated, pairs, scores, selected["threshold"])
    report = dict(protocol="URL-group OOF base scores; temperature and threshold selected on those dev scores; NOT an independent estimate",
                  cache_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),
                  baseline_accuracy=float(accuracy_score(y, logits.argmax(1))),
                  baseline_macro_f1=float(f1_score(y, logits.argmax(1), average="macro")),
                  raw_oof_log_loss=float(log_loss(y, probabilities(1))),
                  selected_oof_log_loss=float(log_loss(y, calibrated)),
                  temperature=temperature, grid=grid, selected=selected,
                  note="Pair agreement is a consistency check, not human proof of entailment. Zero-score filtering may route runtime to the existing pair policy when fewer than three passages remain.")
    model_data["temperature"] = temperature
    model_data["decisive_min_confidence"] = selected["threshold"]
    model_data["status"] = "dev-calibrated with citation agreement guard; real-world calibration and accuracy unmeasured"
    model_path.write_text(json.dumps(model_data, indent=2) + "\n")
    report["deployed_model_sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    (ROOT / "outputs/metrics/aggregation_guard_dev.json").write_text(json.dumps(report, indent=2) + "\n")
    pd.DataFrame(dict(source_row_id=frame.source_row_id, fold=fold_ids, gold=frame.gold_label,
                      prediction=[LABELS[i] for i in pred], guard_rejected=rejected)).to_csv(ROOT / "outputs/predictions/aggregation_guard_dev.csv", index=False)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
