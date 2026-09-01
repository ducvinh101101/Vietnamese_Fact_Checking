"""Evaluate the current verifier on Vinh's manually labelled smoke-test set."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import FactCheckingPipeline



LABELS = ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=ROOT / "data/evaluation/vinh_manual_claims_v1.csv")
    parser.add_argument("--evidence", type=Path, default=ROOT / "data/evidence/sample_evidence.jsonl")
    args = parser.parse_args()

    pipeline = FactCheckingPipeline(
        evidence_path=str(args.evidence),
        engine="phobert",
        model_path=str(ROOT / "models/e2_phobert/best_model"),
        vncorenlp_dir=str(ROOT / "models/vncorenlp"),
    )
    cases = pd.read_csv(args.cases).fillna("")
    predictions, evidence_ids = [], []
    for claim in cases["claim"]:
        result, _ = pipeline.run(claim)
        predictions.append(result.label)
        evidence_ids.append(",".join(result.evidence_ids))
    cases["prediction"] = predictions
    cases["retrieved_evidence_ids"] = evidence_ids
    cases["is_correct"] = cases["prediction"] == cases["expected_label"]

    output_dir = ROOT / "outputs/manual_evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    cases.to_csv(output_dir / "vinh_manual_claims_v1_results.csv", index=False, encoding="utf-8")
    matrix = confusion_matrix(cases["expected_label"], predictions, labels=LABELS)
    pd.DataFrame(matrix, index=LABELS, columns=LABELS).to_csv(
        output_dir / "vinh_manual_claims_v1_confusion_matrix.csv", encoding="utf-8")
    report = classification_report(cases["expected_label"], predictions, labels=LABELS, zero_division=0)
    (output_dir / "vinh_manual_claims_v1_report.txt").write_text(
        f"Accuracy: {cases['is_correct'].mean():.2%}\n\n{report}", encoding="utf-8")
    print(f"Accuracy: {cases['is_correct'].mean():.2%}")
    print(f"Saved results to: {output_dir}")


if __name__ == "__main__":
    main()
