"""Validate/score the independent evidence gold set; no model or network calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "tests/golden/model_comparison_v1"
LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
INPUT_FIELDS = ("id", "as_of", "claim", "evidence")
CATEGORIES = {
    "language_negation", "numbers_units", "time_scope", "entity_scope",
    "logic_quantifiers", "multi_evidence", "evidence_quality",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_jsonl(path):
    rows = []
    with Path(path).open(encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            require(isinstance(row, dict), f"{path}:{number}: expected an object")
            rows.append(row)
    return rows


def validate_dataset(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    expected_files = {"gold.jsonl", "inputs.jsonl", "PROTOCOL.md", "build_dataset.py"}
    require(set(manifest["sha256"]) == expected_files, "Unexpected manifest file list")
    for name, expected in manifest["sha256"].items():
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        require(actual == expected, f"Hash mismatch: {name}; do not silently regenerate gold after scoring")
    gold = read_jsonl(directory / "gold.jsonl")
    blind = read_jsonl(directory / "inputs.jsonl")
    require(len(gold) == len(blind) == manifest["case_count"] == 84, "Expected 84 cases")
    ids = [row["id"] for row in gold]
    require(len(set(ids)) == 84, "Duplicate case IDs")
    require(set(ids) == {f"vg{n:03d}" for n in range(1, 85)}, "Unexpected case IDs")
    require(len({row["claim"].strip().casefold() for row in gold}) == 84, "Duplicate claims")
    counts = Counter(row["gold_label"] for row in gold)
    require(counts == {label: 28 for label in LABELS}, "Labels must be balanced 28/28/28")
    require(counts == manifest["label_counts"], "Manifest label count mismatch")
    categories = Counter(row["category"] for row in gold)
    require(categories == {category: 12 for category in CATEGORIES}, "Expected seven categories of 12")
    require(categories == manifest["category_counts"], "Manifest category count mismatch")
    for category in CATEGORIES:
        require(Counter(row["gold_label"] for row in gold if row["category"] == category)
                == {label: 4 for label in LABELS}, f"Unbalanced category: {category}")
    for row, model_input in zip(gold, blind):
        cid = row["id"]
        require(set(model_input) == set(INPUT_FIELDS), f"{cid}: unexpected blind fields / possible gold leak")
        require(model_input == {key: row[key] for key in INPUT_FIELDS}, f"{cid}: input/gold mismatch")
        require(isinstance(row["claim"], str) and row["claim"].strip(), f"{cid}: empty claim")
        require(row["gold_reason"].strip(), f"{cid}: missing rationale")
        require(row["dataset_version"] == manifest["dataset_version"], f"{cid}: version mismatch")
        require(row["provenance"] == "synthetic_independently_authored", f"{cid}: missing provenance")
        require(row["as_of"] == manifest["as_of"], f"{cid}: reference date mismatch")
        as_of = date.fromisoformat(row["as_of"])
        passage_ids = set()
        for evidence in row["evidence"]:
            pid = evidence["passage_id"]
            require(pid not in passage_ids, f"{cid}: duplicate passage ID")
            passage_ids.add(pid)
            require(evidence["content"].strip(), f"{cid}/{pid}: empty passage")
            require(evidence["source"] == "Tư liệu giả lập", f"{cid}/{pid}: wrong provenance")
            require(evidence["url"].startswith("https://benchmark.invalid/"), f"{cid}/{pid}: non-synthetic URL")
            if evidence["published_at"] is not None:
                require(date.fromisoformat(evidence["published_at"]) <= as_of, f"{cid}/{pid}: future publication")
        groups = row["gold_evidence_sets"]
        if row["gold_label"] == "NOT_ENOUGH_INFO":
            require(groups == [], f"{cid}: NEI must have no gold citations")
        else:
            require(bool(groups), f"{cid}: decisive label needs evidence")
            for group in groups:
                require(bool(group) and len(group) == len(set(group)), f"{cid}: empty/duplicate gold citation")
                require(set(group) <= passage_ids, f"{cid}: unknown gold citation")
    return gold, manifest


def load_predictions(path, expected_ids):
    predictions = {}
    for row in read_jsonl(path):
        cid = row.get("id")
        require(isinstance(cid, str) and cid in expected_ids, f"{path}: unknown/missing ID {cid!r}")
        require(cid not in predictions, f"{path}: duplicate ID {cid}")
        require("label" in row, f"{path}/{cid}: missing label; use null + error for failed requests")
        label = row["label"]
        require(label is None or (isinstance(label, str) and label in LABELS),
                f"{path}/{cid}: invalid label; use null + error for failed requests")
        if label is None:
            require(isinstance(row.get("error"), str) and row["error"].strip(), f"{path}/{cid}: null label needs error")
        predictions[cid] = row
    missing = expected_ids - predictions.keys()
    require(not missing, f"{path}: missing {len(missing)} IDs: {', '.join(sorted(missing))}")
    return predictions


def citation_matches(row, prediction):
    cited = prediction.get("evidence_ids")
    if not isinstance(cited, list) or not all(isinstance(pid, str) for pid in cited):
        return False
    if len(cited) != len(set(cited)):
        return False
    if row["gold_label"] == "NOT_ENOUGH_INFO":
        return cited == []
    return any(set(cited) == set(group) for group in row["gold_evidence_sets"])


def score(gold, predictions):
    total = len(gold)
    confusion = {label: dict.fromkeys((*LABELS, "INVALID"), 0) for label in LABELS}
    category_stats = {}
    correct_ids, errors, citation_present, citation_joint_correct = [], [], 0, 0
    for row in gold:
        cid, truth = row["id"], row["gold_label"]
        prediction = predictions[cid]
        predicted = prediction["label"] or "INVALID"
        confusion[truth][predicted] += 1
        is_correct = predicted == truth
        bucket = category_stats.setdefault(row["category"], {"total": 0, "correct": 0})
        bucket["total"] += 1
        bucket["correct"] += int(is_correct)
        if is_correct:
            correct_ids.append(cid)
        else:
            errors.append({"id": cid, "gold_label": truth, "predicted_label": prediction["label"],
                           "error": prediction.get("error")})
        if "evidence_ids" in prediction:
            citation_present += 1
            citation_joint_correct += int(is_correct and citation_matches(row, prediction))
    per_label = {}
    for label in LABELS:
        tp = confusion[label][label]
        predicted_count = sum(confusion[truth][label] for truth in LABELS)
        support = sum(confusion[label].values())
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    for bucket in category_stats.values():
        bucket["accuracy"] = bucket["correct"] / bucket["total"]
    invalid = sum(confusion[label]["INVALID"] for label in LABELS)
    return {
        "total": total, "correct": len(correct_ids), "accuracy": len(correct_ids) / total,
        "macro_f1": sum(item["f1"] for item in per_label.values()) / len(LABELS),
        "valid_labels": total - invalid, "valid_label_rate": (total - invalid) / total,
        "per_label": per_label, "confusion_rows_gold_columns_predicted": confusion,
        "per_category": dict(sorted(category_stats.items())),
        "citations": {
            "predictions_with_evidence_ids": citation_present,
            "coverage": citation_present / total,
            "correct_label_and_exact_minimal_evidence": citation_joint_correct,
            "joint_accuracy_among_annotated": citation_joint_correct / citation_present if citation_present else None,
        },
        "correct_ids": correct_ids, "errors": errors,
    }


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    scoring = commands.add_parser("score")
    scoring.add_argument("predictions", type=Path, nargs="+", help="One or two prediction JSONL files")
    scoring.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        gold, manifest = validate_dataset(args.dataset)
        if args.command == "validate":
            print(json.dumps({"status": "VALID", "version": manifest["dataset_version"],
                              "cases": len(gold), "labels": manifest["label_counts"],
                              "categories": manifest["category_counts"], "hashes_verified": True},
                             ensure_ascii=False, indent=2))
            return 0
        require(1 <= len(args.predictions) <= 2, "Supply one or two prediction files")
        expected_ids = {row["id"] for row in gold}
        scores = []
        for path in args.predictions:
            predictions = load_predictions(path, expected_ids)
            scores.append({"prediction_file": str(path), "prediction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           **score(gold, predictions)})
        report = {"dataset_version": manifest["dataset_version"],
                  "gold_sha256": manifest["sha256"]["gold.jsonl"],
                  "inputs_sha256": manifest["sha256"]["inputs.jsonl"], "results": scores}
        if len(scores) == 2:
            a, b = (set(result["correct_ids"]) for result in scores)
            report["paired_comparison"] = {
                "both_correct": len(a & b), "both_wrong": len(expected_ids - (a | b)),
                "first_only_correct": sorted(a - b), "second_only_correct": sorted(b - a),
                "accuracy_second_minus_first": scores[1]["accuracy"] - scores[0]["accuracy"],
            }
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            protected = {path.resolve() for path in args.dataset.iterdir() if path.is_file()}
            protected.update(path.resolve() for path in args.predictions)
            require(args.output.resolve() not in protected, "Output must not overwrite dataset or prediction files")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
