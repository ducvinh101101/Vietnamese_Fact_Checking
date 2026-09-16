"""Diagnose the 80% target on cached DEV scores, without another test run."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.decision_policy import LABELS
from src.retrieval_aware_policy import decide_rank_aware
from src.learned_evidence_policy import aggregation_features, LearnedEvidencePolicy


def metrics(y, pred):
    return {"accuracy": float(accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, labels=range(3), average="macro")),
            "per_label": classification_report(y, pred, labels=range(3), target_names=LABELS, output_dict=True, zero_division=0)}


def main():
    path = ROOT / "outputs/predictions/e11_dev_rank_aware_candidates.csv"
    frame = pd.read_csv(path)
    p = np.array([json.loads(value) for value in frame.candidate_probabilities])
    y = np.array([LABELS.index(label) for label in frame.gold_label])
    old = np.array([LABELS.index(label) for label in frame.selected_prediction])
    candidates = p.argmax(axis=2)
    selectable = (candidates == y[:, None]).any(axis=1)
    # Fixed feature design, no claim text, annotated evidence, URL or label input.
    scores = np.array([[r["score"] for r in json.loads(value)] for value in frame.retrieved])
    x = np.array([aggregation_features(probs.tolist(), s.tolist()) for probs, s in zip(p, scores)])
    pred = np.full(len(y), -1)
    folds = np.full(len(y), -1)
    fold_records = []
    for fold, (train, valid) in enumerate(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42).split(x, y, frame.gold_url)):
        assert not set(frame.gold_url.iloc[train]) & set(frame.gold_url.iloc[valid])
        model = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000, random_state=42))
        model.fit(x[train], y[train])
        pred[valid] = model.predict(x[valid])
        folds[valid] = fold
        fold_records.append({"fold": fold, "train": len(train), "validation": len(valid),
                             "baseline": metrics(y[valid], old[valid]), "candidate": metrics(y[valid], pred[valid])})
    same_rank = []
    for probs in p:
        d = decide_rank_aware(probs.tolist(), 1.0, 0.6)
        same_rank.append(d.evidence_index == 0)
    report = {
        "scope": "DEV diagnostic only; not a new independent test and not a production claim",
        "cache_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "queries": len(y), "unique_urls": frame.gold_url.nunique(),
        "baseline": metrics(y, old),
        "argmax_candidate_selection_ceiling": float(selectable.mean()),
        "ceiling_note": "Gold label used ONLY to diagnose whether any top-3 pair argmax is correct. Not deployable accuracy; not a ceiling for retraining or label-changing policies.",
        "gold_label_absent_from_all_pair_argmax": int((~selectable).sum()),
        "rank_1_citation_fraction": float(np.mean(same_rank)),
        "learned_aggregation_group_oof": metrics(y, pred),
        "candidate_protocol": "Fixed C=0.1 logistic regression; 5-fold URL-disjoint OOF on cached dev. E2 and temperature previously used dev, so this is a development estimate only.",
        "folds": fold_records,
        "target": {"accuracy": 0.8, "achieved_on_independent_real_world_set": False},
    }
    out = ROOT / "outputs/metrics/accuracy_gap_dev_audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    frame["audit_fold"] = folds
    frame["learned_oof_prediction"] = [LABELS[i] for i in pred]
    frame.to_csv(ROOT / "outputs/predictions/accuracy_gap_dev_oof.csv", index=False)
    # Export the fixed candidate fitted on all dev; OOF above remains the reported score.
    model.fit(x, y)
    scaler, classifier = model.steps[0][1], model.steps[1][1]
    assert classifier.classes_.tolist() == [0, 1, 2]
    model_path = ROOT / "models/aggregation/dev_logistic_v1.json"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(json.dumps({
        "feature_version": 1, "labels": list(LABELS), "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(), "coef": classifier.coef_.tolist(),
        "intercept": classifier.intercept_.tolist(), "training_cache_sha256": report["cache_sha256"],
        "status": "dev-selected candidate; external real-world accuracy unmeasured; confidence uncalibrated"
    }, indent=2) + "\n", encoding="utf-8")
    runtime = LearnedEvidencePolicy(model_path)
    actual = np.array([runtime.predict_probabilities(probs.tolist(), s.tolist()) for probs, s in zip(p, scores)])
    assert np.allclose(actual, model.predict_proba(x)), "Export differs from sklearn model"
    print(json.dumps({k: report[k] for k in ("queries", "argmax_candidate_selection_ceiling", "gold_label_absent_from_all_pair_argmax", "rank_1_citation_fraction")}))
    print("baseline", report["baseline"]["accuracy"], report["baseline"]["macro_f1"])
    print("group_oof", report["learned_aggregation_group_oof"]["accuracy"], report["learned_aggregation_group_oof"]["macro_f1"])


if __name__ == "__main__":
    main()
