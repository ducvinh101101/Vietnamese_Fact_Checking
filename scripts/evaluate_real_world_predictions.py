"""Score a locked, human-reviewed real-world benchmark, including coverage.

Gold CSV fields: claim_id, claim, gold_label, topic_group, source_url,
observed_at, reviewer_1, reviewer_2, review_status.
Prediction CSV fields: claim_id, predicted_label, citation_faithful.
Citation faithfulness must be independently reviewed: true/false/unknown.
Missing/abstained/error predictions count as failures in all-claim accuracy.
"""
import argparse
import hashlib
import json
from pathlib import Path
from math import sqrt

import pandas as pd
from sklearn.metrics import f1_score, classification_report

LABELS = ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


def wilson(correct, total):
    if not total:
        return [0.0, 1.0]
    z = 1.959963984540054
    p = correct / total
    den = 1 + z*z/total
    center = (p + z*z/(2*total)) / den
    margin = z * sqrt(p*(1-p)/total + z*z/(4*total*total)) / den
    return [center-margin, center+margin]


def evaluate(gold, predictions):
    required = {"claim_id", "claim", "gold_label", "topic_group", "source_url", "observed_at", "reviewer_1", "reviewer_2", "review_status"}
    if required - set(gold):
        raise ValueError(f"Missing gold fields: {sorted(required-set(gold))}")
    if gold.empty or gold.claim_id.duplicated().any() or predictions.claim_id.duplicated().any():
        raise ValueError("Require nonempty gold with unique claim IDs and unique predictions")
    if gold[list(required)].isna().any().any() or gold[list(required)].astype(str).apply(lambda c: c.str.strip().eq("")).any().any():
        raise ValueError("Gold review fields must be populated")
    if not gold.gold_label.isin(LABELS).all() or not gold.review_status.eq("approved").all():
        raise ValueError("Gold labels must be approved by reviewers")
    if gold.reviewer_1.eq(gold.reviewer_2).any():
        raise ValueError("Require two distinct reviewers")
    if set(predictions.claim_id) - set(gold.claim_id):
        raise ValueError("Prediction IDs absent from gold")
    merged = gold.merge(predictions, on="claim_id", how="left", validate="one_to_one")
    pred = merged.predicted_label.fillna("ERROR")
    if not pred.isin(LABELS + ["ERROR", "ABSTAIN"]).all():
        raise ValueError("Invalid prediction label")
    correct = pred.eq(merged.gold_label)
    accepted = pred.isin(LABELS)
    decisive = pred.isin(LABELS[:2])
    faith = merged.citation_faithful.fillna("unknown").astype(str).str.lower()
    if not faith.isin(["true", "false", "unknown"]).all():
        raise ValueError("citation_faithful requires true/false/unknown")
    ci = wilson(int(correct.sum()), len(gold))
    return {"claims": len(gold), "accuracy_all_claims": float(correct.mean()),
            "accuracy_95pct_wilson": ci, "ci_note": "Binomial interval; does not account for topic clustering or sampling bias.",
            "macro_f1": float(f1_score(merged.gold_label, pred, labels=LABELS, average="macro", zero_division=0)),
            "classification_report": classification_report(merged.gold_label, pred, labels=LABELS, output_dict=True, zero_division=0),
            "coverage": float(accepted.mean()),
            "accuracy_answered_only": float(correct[accepted].mean()) if accepted.any() else None,
            "decisive_citation_review_coverage": float(faith[decisive].ne("unknown").mean()) if decisive.any() else None,
            "correct_and_faithful_decisive_fraction": float((correct & faith.eq("true"))[decisive].mean()) if decisive.any() else None,
            "label_counts": gold.gold_label.value_counts().to_dict(),
            "topic_groups": int(gold.topic_group.nunique()),
            "accuracy_target_80_point_estimate_met": bool(correct.mean() >= 0.8),
            "accuracy_target_80_lower_bound_met": bool(ci[0] >= 0.8)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--expected-gold-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = hashlib.sha256(args.gold.read_bytes()).hexdigest()
    if digest != args.expected_gold_sha256:
        raise ValueError("Gold benchmark differs from precommitted hash")
    report = evaluate(pd.read_csv(args.gold), pd.read_csv(args.predictions))
    report["gold_sha256"] = digest
    report["predictions_sha256"] = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
