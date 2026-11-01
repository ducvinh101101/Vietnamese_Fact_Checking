"""Paired statistics for two prediction files on the frozen 84-case gold set.

    python scripts/analyze_model_comparison.py A.jsonl B.jsonl --names PhoBERT Gemma4 --out report.json

Prints accuracy / Macro-F1 / per-label F1 / per-category accuracy / latency for each,
plus an exact McNemar test on discordant cases and a paired bootstrap 95% CI of
Delta Macro-F1 (B - A). Reads gold only here, after predictions exist.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_model_gold import DEFAULT_DATASET, LABELS, load_predictions, validate_dataset  # noqa: E402


def macro_f1(pairs):
    f1s = []
    for label in LABELS:
        tp = sum(1 for g, p in pairs if g == label and p == label)
        fp = sum(1 for g, p in pairs if g != label and p == label)
        fn = sum(1 for g, p in pairs if g == label and p != label)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s), dict(zip(LABELS, f1s))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def summarize(name, gold, preds):
    ids = [row["id"] for row in gold]
    truth = {row["id"]: row["gold_label"] for row in gold}
    cats = {row["id"]: row["category"] for row in gold}
    pairs = [(truth[i], preds[i].get("label")) for i in ids]
    mf1, per_label = macro_f1(pairs)
    correct = {i for i in ids if preds[i].get("label") == truth[i]}
    by_cat = {}
    for cat in sorted(set(cats.values())):
        members = [i for i in ids if cats[i] == cat]
        by_cat[cat] = sum(i in correct for i in members) / len(members)
    latencies = [float(preds[i].get("latency_seconds", 0)) for i in ids]
    predicted = {label: sum(1 for _, p in pairs if p == label) for label in LABELS}
    predicted["ERROR"] = sum(1 for _, p in pairs if p not in LABELS)
    confusion = {g: {p: sum(1 for gg, pp in pairs if gg == g and (pp == p or (p == "ERROR" and pp not in LABELS)))
                     for p in (*LABELS, "ERROR")} for g in LABELS}
    return {"name": name, "accuracy": len(correct) / len(ids), "macro_f1": mf1, "per_label_f1": per_label,
            "per_category_accuracy": by_cat, "predicted_counts": predicted, "confusion": confusion,
            "latency_median_s": statistics.median(latencies),
            "latency_p95_s": sorted(latencies)[int(0.95 * (len(latencies) - 1))],
            "errors": predicted["ERROR"], "retries": sum(int(preds[i].get("retries") or 0) for i in ids),
            "_correct": correct, "_pairs": pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--names", nargs=2, default=["A", "B"])
    parser.add_argument("--rounds", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    gold, _ = validate_dataset(DEFAULT_DATASET)
    expected = {row["id"] for row in gold}
    first = summarize(args.names[0], gold, load_predictions(args.a, expected))
    second = summarize(args.names[1], gold, load_predictions(args.b, expected))
    only_a = sorted(first["_correct"] - second["_correct"])
    only_b = sorted(second["_correct"] - first["_correct"])
    rng = random.Random(args.seed)
    n = len(gold)
    deltas = []
    for _ in range(args.rounds):
        sample = [rng.randrange(n) for _ in range(n)]
        deltas.append(macro_f1([second["_pairs"][i] for i in sample])[0] - macro_f1([first["_pairs"][i] for i in sample])[0])
    deltas.sort()
    paired = {"only_first_correct": only_a, "only_second_correct": only_b,
              "mcnemar_exact_p": mcnemar_exact(len(only_a), len(only_b)),
              "delta_macro_f1": second["macro_f1"] - first["macro_f1"],
              "delta_macro_f1_ci95": [deltas[int(0.025 * args.rounds)], deltas[int(0.975 * args.rounds) - 1]],
              "bootstrap_rounds": args.rounds, "seed": args.seed}
    report = {"first": {k: v for k, v in first.items() if not k.startswith("_")},
              "second": {k: v for k, v in second.items() if not k.startswith("_")}, "paired": paired}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
