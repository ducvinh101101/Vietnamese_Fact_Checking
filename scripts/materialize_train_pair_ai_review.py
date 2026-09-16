"""Attach the individually authored review ledger to a hash-locked source CSV."""
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "1e5f0f229d3edda5aa601ca63f5746e4bc1a4093c978bc56cdc4ae4db9697942"
LABELS = {"S": "SUPPORTED", "R": "REFUTED", "N": "NOT_ENOUGH_INFO"}


def materialize(source, ledger):
    if len(source) != 540 or sorted(ledger.row.tolist()) != list(range(len(source))):
        raise ValueError("Review ledger must cover all 540 rows exactly once")
    if not ledger.decision.isin([*LABELS, "U"]).all() or ledger.note.str.strip().eq("").any():
        raise ValueError("Every decision needs a valid code and individual rationale")
    if not source.review_status.eq("pending").all():
        raise ValueError("Do not replace existing reviews")
    ledger = ledger.sort_values("row").reset_index(drop=True)
    result = source.copy().reset_index(drop=True)
    result["reviewed_pair_label"] = ledger.decision.map(LABELS).fillna("")
    result["reviewer"] = "Codex AI / single-pass semantic review / 2026-09-07"
    result["review_notes"] = ledger.note
    result["review_status"] = ledger.decision.map(lambda d: "needs_human_review" if d == "U" else "ai_reviewed")
    result["review_method"] = "claim_and_single_passage_only; no external fact lookup; no gold-label copying"
    return result


def main():
    directory = ROOT / "data/evaluation"
    source = directory / "train_retrieved_pair_review.csv"
    ledger_path = directory / "train_pair_ai_review_v1.tsv"
    output = directory / "train_retrieved_pair_ai_review_v1.csv"
    queue = directory / "train_pair_human_adjudication_v1.csv"
    report_path = ROOT / "outputs/metrics/train_pair_ai_review_v1.json"
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source changed; ledger row indices are no longer safe")
    if any(p.exists() for p in (output, queue, report_path)):
        raise FileExistsError("Versioned review outputs already exist")
    result = materialize(pd.read_csv(source, keep_default_na=False), pd.read_csv(ledger_path, sep="\t", keep_default_na=False))
    result.to_csv(output, index=False, encoding="utf-8-sig")
    result[result.review_status == "needs_human_review"].to_csv(queue, index=False, encoding="utf-8-sig")
    report = {"source_sha256": SOURCE_SHA256, "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
              "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "reviewed_pairs": len(result),
              "claims": int(result.claim.nunique()), "status_counts": result.review_status.value_counts().to_dict(),
              "ai_label_counts": result.loc[result.review_status == "ai_reviewed", "reviewed_pair_label"].value_counts().to_dict(),
              "human_gold": False, "training_use": "Optional silver augmentation, exclude unresolved rows; evaluate before promotion",
              "limitations": "Single AI reviewer; no human agreement score. Full claim must be supported by one passage; absent information is not refutation."}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
