"""Held-out set sampling, inter-annotator agreement (Cohen's Kappa), and bootstrap CI tools.

NOTE: Real held-out evaluation datasets MUST be collected from articles strictly OUTSIDE
the ViFactCheck training corpus to ensure true out-of-distribution evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data/evidence/vifactcheck_passages.jsonl"
VALID_LABELS = ["SUPPORTED", "REFUTED", "NEI"]


def cmd_sample(args: argparse.Namespace) -> None:
    corpus_path = Path(args.corpus)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not corpus_path.exists():
        print(f"Error: Corpus file not found: {corpus_path}", file=sys.stderr)
        sys.exit(1)

    passages = []
    with corpus_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                passages.append(json.loads(line))

    rng = random.Random(args.seed)
    sampled = rng.sample(passages, min(args.n, len(passages)))

    rows = []
    for idx, p in enumerate(sampled, start=1):
        rows.append({
            "id": f"H{idx:03d}",
            "passage_id": p.get("passage_id", ""),
            "url": p.get("url", ""),
            "content": p.get("content", ""),
            "claim": "",
            "annotator_a": "",
            "annotator_b": "",
        })

    fieldnames = ["id", "passage_id", "url", "content", "claim", "annotator_a", "annotator_b"]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Sampled {len(rows)} passages into '{out_path}'. (Seed: {args.seed})")


def cmd_kappa(args: argparse.Namespace) -> None:
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(csv_path).fillna("")
    if "annotator_a" not in df.columns or "annotator_b" not in df.columns:
        print("Error: CSV must contain 'annotator_a' and 'annotator_b' columns.", file=sys.stderr)
        sys.exit(1)

    valid_mask = (df["annotator_a"].isin(VALID_LABELS)) & (df["annotator_b"].isin(VALID_LABELS))
    annotated = df[valid_mask]

    if len(annotated) < 30:
        print(f"Thông báo: Chỉ có {len(annotated)} dòng được cả 2 annotator gán đủ nhãn hợp lệ ({VALID_LABELS}). Cần tối thiểu 30 dòng để tính Cohen's kappa có ý nghĩa thống kê.")
        sys.exit(0)

    y_a = annotated["annotator_a"].tolist()
    y_b = annotated["annotator_b"].tolist()

    kappa = cohen_kappa_score(y_a, y_b, labels=VALID_LABELS)
    cm = confusion_matrix(y_a, y_b, labels=VALID_LABELS)

    print(f"Annotated pairs count: {len(annotated)}")
    print(f"Cohen's Kappa: {kappa:.4f}")
    print("\nConfusion Matrix (Rows: Annotator A, Cols: Annotator B):")
    cm_df = pd.DataFrame(cm, index=VALID_LABELS, columns=VALID_LABELS)
    print(cm_df)


def cmd_bootstrap(args: argparse.Namespace) -> None:
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(csv_path).fillna("")
    if "y_true" not in df.columns or "y_pred" not in df.columns:
        print("Error: CSV must contain 'y_true' and 'y_pred' columns.", file=sys.stderr)
        sys.exit(1)

    valid_mask = (df["y_true"].isin(VALID_LABELS)) & (df["y_pred"].isin(VALID_LABELS))
    filtered = df[valid_mask]
    n = len(filtered)
    if n == 0:
        print("Error: No valid rows with y_true and y_pred found.", file=sys.stderr)
        sys.exit(1)

    y_true = np.array(filtered["y_true"].tolist())
    y_pred = np.array(filtered["y_pred"].tolist())

    base_f1 = f1_score(y_true, y_pred, labels=VALID_LABELS, average="macro")

    rng = np.random.RandomState(42)
    boot_f1s = []
    n_iterations = args.n_bootstrap

    for _ in range(n_iterations):
        indices = rng.randint(0, n, size=n)
        sample_true = y_true[indices]
        sample_pred = y_pred[indices]
        boot_f1s.append(f1_score(sample_true, sample_pred, labels=VALID_LABELS, average="macro", zero_division=0))

    ci_lower = np.percentile(boot_f1s, 2.5)
    ci_upper = np.percentile(boot_f1s, 97.5)

    print(f"Evaluation samples count: {n}")
    print(f"Base Macro-F1: {base_f1 * 100:.2f}%")
    print(f"95% Bootstrap Confidence Interval ({n_iterations} rounds): [{ci_lower * 100:.2f}%, {ci_upper * 100:.2f}%]")


def cmd_citation_sheet(args: argparse.Namespace) -> None:
    """Create a manual passage-level citation audit sheet from prediction JSONL."""
    predictions_path = Path(args.predictions)
    output_path = Path(args.out)
    if not predictions_path.is_file():
        print(f"Error: Predictions file not found: {predictions_path}", file=sys.stderr)
        sys.exit(1)

    rows = []
    with predictions_path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            item = json.loads(line)
            citations = item.get("citations") or item.get("evidence") or []
            if not citations:
                continue
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                rows.append({
                    "id": f"C{len(rows) + 1:03d}",
                    "claim": item.get("claim", ""),
                    "predicted_label": item.get("predicted_label", item.get("label", "")),
                    "passage_id": citation.get("passage_id", ""),
                    "url": citation.get("url", ""),
                    "content": citation.get("content", ""),
                    "supports_verdict": "",
                    "reviewer_note": "",
                })
                if len(rows) >= args.n:
                    break
            if len(rows) >= args.n:
                break
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "claim", "predicted_label", "passage_id", "url", "content", "supports_verdict", "reviewer_note"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Created citation audit sheet with {len(rows)} rows: '{output_path}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Held-out annotation & evaluation tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: sample
    sample_parser = subparsers.add_parser("sample", help="Sample passages for annotation.")
    sample_parser.add_argument("--corpus", type=str, default=str(DEFAULT_CORPUS))
    sample_parser.add_argument("--n", type=int, default=200)
    sample_parser.add_argument("--seed", type=int, default=42)
    sample_parser.add_argument("--out", type=str, default="outputs/annotation_sheet.csv")

    # Subcommand: kappa
    kappa_parser = subparsers.add_parser("kappa", help="Compute Cohen's kappa.")
    kappa_parser.add_argument("--csv", type=str, required=True)

    # Subcommand: bootstrap
    boot_parser = subparsers.add_parser("bootstrap", help="Compute bootstrap CI for Macro-F1.")
    boot_parser.add_argument("--csv", type=str, required=True)
    boot_parser.add_argument("--n_bootstrap", type=int, default=2000)

    citation_parser = subparsers.add_parser("citation-sheet", help="Create a passage-level citation review worksheet.")
    citation_parser.add_argument("--predictions", type=str, required=True)
    citation_parser.add_argument("--n", type=int, default=100)
    citation_parser.add_argument("--out", type=str, default="outputs/citation_audit_sheet.csv")

    args = parser.parse_args()
    if args.command == "sample":
        cmd_sample(args)
    elif args.command == "kappa":
        cmd_kappa(args)
    elif args.command == "bootstrap":
        cmd_bootstrap(args)
    elif args.command == "citation-sheet":
        cmd_citation_sheet(args)


if __name__ == "__main__":
    main()
