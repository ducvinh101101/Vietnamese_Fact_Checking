"""A/B trên DEV có nhãn người: cách dựng evidence (evidence_view) x lớp an toàn.

Mục đích: quyết định có đổi `evidence_view` / bật `guard` / `minimal_pair` hay không dựa trên dữ
liệu ViFactCheck có nhãn người, KHÔNG chỉ dựa trên challenge set tổng hợp (challenge set
thiên vị cho focus_only vì claim là câu đơn lấy từ kho).

* Chạy trên dev split. Từ chối test split trừ khi có --allow-test (test split đã khóa
  để chạy MỘT lần cho báo cáo; không dùng nó để chọn cấu hình).
* Mỗi claim: truy xuất 1 lần/view, PhoBERT 1 lần/view; các tầng hậu kiểm tính sau (không
  gọi lại mô hình): raw | mp (cặp-tối-thiểu) | g60/g40/g25+mp (guard với độ phủ chủ đề
  60%/40%/25% rồi cặp-tối-thiểu). 'ensemble' = trung bình xác suất 3 view (1 lần gọi mô hình).
* Với mỗi cấu hình guard: in số verdict ĐÚNG bị hạ nhầm và số verdict sai được chặn.
* Báo cáo accuracy, Macro-F1, F1 từng nhãn, ma trận nhầm lẫn, và khoảng tin cậy
  bootstrap CỦA CHÊNH LỆCH Macro-F1 so với cấu hình gốc (passage, raw), ghép cặp theo claim.

    py -3.13 scripts/ab_dev_end_to_end.py
    py -3.13 scripts/ab_dev_end_to_end.py --limit 200          # chạy thử
    py -3.13 scripts/ab_dev_end_to_end.py --views passage focus_only
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))

from src.evidence_focus import VIEWS  # noqa: E402
from src.minimal_pair import refine  # noqa: E402
from src.pipeline import FactCheckingPipeline  # noqa: E402
from src.schemas import VerificationResult  # noqa: E402
from src.verdict_guard import guard_reason  # noqa: E402

LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
ID_TO_LABEL = {0: "SUPPORTED", 1: "REFUTED", 2: "NOT_ENOUGH_INFO"}
GUARD_COVERAGES = {"g60+mp": 0.6, "g40+mp": 0.4, "g25+mp": 0.25}
STAGES = ("raw", "mp", *GUARD_COVERAGES)
DEFAULT_SPLIT = ROOT / "data/processed/vifactcheck_group_split/dev.parquet"


def macro_f1(gold: list[str], pred: list[str]) -> float:
    scores = []
    for label in LABELS:
        tp = sum(g == label and p == label for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        denominator = 2 * tp + fp + fn
        scores.append(2 * tp / denominator if denominator else 0.0)
    return sum(scores) / len(scores)


def per_label_f1(gold, pred) -> dict[str, float]:
    out = {}
    for label in LABELS:
        tp = sum(g == label and p == label for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        out[label] = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    return out


def confusion(gold, pred) -> list[list[int]]:
    return [[sum(g == a and p == b for g, p in zip(gold, pred)) for b in LABELS] for a in LABELS]


def paired_bootstrap(gold, base, other, rounds: int = 1000, seed: int = 42) -> tuple[float, float, float]:
    """Chênh lệch Macro-F1 (other - base) và khoảng 95%, resample theo claim."""
    rng = random.Random(seed)
    n = len(gold)
    diffs = []
    for _ in range(rounds):
        idx = [rng.randrange(n) for _ in range(n)]
        g = [gold[i] for i in idx]
        diffs.append(macro_f1(g, [other[i] for i in idx]) - macro_f1(g, [base[i] for i in idx]))
    diffs.sort()
    point = macro_f1(gold, other) - macro_f1(gold, base)
    return point, diffs[int(0.025 * rounds)], diffs[int(0.975 * rounds) - 1]


def build_pipeline(config: dict, engine: str) -> FactCheckingPipeline:
    v = config["verification"]
    common = dict(
        evidence_path=str(ROOT / config["paths"]["evidence_path"]),
        top_k=int(config["retrieval"]["top_k"]),
        support_threshold=float(v.get("support_threshold", 0.45)),
        refute_markers=v.get("refute_markers"),
    )
    if engine == "rule_based":
        return FactCheckingPipeline(engine="rule_based", **common)
    return FactCheckingPipeline(
        engine="phobert", model_path=str(ROOT / v["model_path"]), vncorenlp_dir=str(ROOT / v["vncorenlp_dir"]),
        max_length=int(v.get("max_length", 256)), temperature=float(v.get("temperature", 1.0)),
        decisive_min_confidence=float(v.get("decisive_min_confidence", 0.0)),
        retrieval_rank_bias=float(v.get("retrieval_rank_bias", 0.0)),
        aggregation_model_path=str(ROOT / v["aggregation_model_path"]) if v.get("aggregation_model_path") else None,
        **common,
    )


def apply_stages(claim: str, result: VerificationResult, retrieved) -> dict[str, str]:
    out = {"raw": result.label, "mp": refine(claim, result, retrieved)[0].label}
    for stage, coverage in GUARD_COVERAGES.items():
        reason = guard_reason(claim, result, retrieved, 0.0, coverage)
        guarded = VerificationResult("NOT_ENOUGH_INFO", 0.0, [], "[guard]") if reason else result
        out[stage] = refine(claim, guarded, retrieved)[0].label
    return out


def load_split(path: Path):
    if path.suffix == ".csv":
        import csv
        with path.open(encoding="utf-8", newline="") as handle:
            return [(r["Statement"], int(r["labels"])) for r in csv.DictReader(handle)]
    import pandas as pd
    frame = pd.read_parquet(path)
    missing = {"Statement", "labels"} - set(frame.columns)
    if missing:
        raise ValueError(f"Split thiếu cột: {sorted(missing)}")
    return [(str(s), int(l)) for s, l in zip(frame["Statement"], frame["labels"])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--allow-test", action="store_true", help="KHÔNG dùng để chọn cấu hình")
    parser.add_argument("--views", nargs="+", choices=VIEWS, default=["passage", "ensemble"])
    parser.add_argument("--engine", choices=["phobert", "rule_based"], default="phobert")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "ab_dev")
    args = parser.parse_args()

    split_path = args.split if args.split.is_absolute() else ROOT / args.split
    if "test" in split_path.name.casefold() and not args.allow_test:
        raise SystemExit("Từ chối chạy trên test split (đã khóa để chạy một lần). Dùng dev.parquet, "
                         "hoặc --allow-test nếu chỉ để kiểm tra, không để chọn cấu hình.")
    rows = load_split(split_path)
    if args.limit:
        rows = rows[: args.limit]
    config = yaml.safe_load((ROOT / "configs/config.yaml").read_text(encoding="utf-8"))
    pipeline = build_pipeline(config, args.engine)
    checker = pipeline.checker
    if args.engine != "phobert":
        print("[ab] CẢNH BÁO: engine rule_based không có evidence_view; kết quả các view sẽ giống nhau.", file=sys.stderr)

    gold = [ID_TO_LABEL[label] for _, label in rows]
    preds: dict[tuple[str, str], list[str]] = {(v, s): [] for v in args.views for s in STAGES}
    started = time.perf_counter()
    for view in args.views:
        if hasattr(checker, "evidence_view"):
            checker.evidence_view = view
        for number, (claim, _) in enumerate(rows, 1):
            result, retrieved = pipeline.run(claim)
            for stage, label in apply_stages(claim, result, retrieved).items():
                preds[(view, stage)].append(label)
            if number % 100 == 0:
                print(f"[ab] view={view} {number}/{len(rows)}", file=sys.stderr, flush=True)

    base_key = ("passage", "raw") if ("passage", "raw") in preds else next(iter(preds))
    summary = {"split": str(split_path.relative_to(ROOT)) if split_path.is_relative_to(ROOT) else str(split_path),
               "n": len(rows), "engine": args.engine, "baseline": "/".join(base_key), "configs": {}}
    print(f"\nDev n={len(rows)} · baseline = {base_key[0]}/{base_key[1]}")
    print(f"{'view':<12}{'stage':<10}{'Acc':>7}{'MacroF1':>9}{'F1 SUP':>8}{'F1 REF':>8}{'F1 NEI':>8}   Δ MacroF1 vs gốc [95% CI]")
    for (view, stage), pred in preds.items():
        f1s = per_label_f1(gold, pred)
        acc = sum(g == p for g, p in zip(gold, pred)) / len(gold)
        point, lo, hi = paired_bootstrap(gold, preds[base_key], pred)
        significant = "  *" if (lo > 0 or hi < 0) else ""
        print(f"{view:<12}{stage:<10}{100 * acc:6.1f}%{100 * macro_f1(gold, pred):8.1f}%"
              f"{100 * f1s['SUPPORTED']:7.1f}%{100 * f1s['REFUTED']:7.1f}%{100 * f1s['NOT_ENOUGH_INFO']:7.1f}%"
              f"   {100 * point:+5.1f} [{100 * lo:+5.1f}, {100 * hi:+5.1f}]{significant}")
        summary["configs"][f"{view}/{stage}"] = {
            "accuracy": acc, "macro_f1": macro_f1(gold, pred), "f1": f1s,
            "confusion_rows_gold_cols_pred": confusion(gold, pred),
            "delta_macro_f1_vs_baseline": {"point": point, "ci95": [lo, hi]},
        }
    print("(* = khoảng tin cậy 95% không chứa 0)")
    print("\nTác động guard so với raw cùng view: [đúng bị hạ nhầm] / [verdict sai được chặn, gold=NEI]")
    for view in args.views:
        for stage in GUARD_COVERAGES:
            raw, new = preds[(view, "raw")], preds[(view, stage)]
            lost = sum(1 for g, r, n in zip(gold, raw, new) if r == g != "NOT_ENOUGH_INFO" and n == "NOT_ENOUGH_INFO")
            saved = sum(1 for g, r, n in zip(gold, raw, new) if g == "NOT_ENOUGH_INFO" and r != g and n == g)
            print(f"  {view:<12}{stage:<9} hạ nhầm {lost:4d} · chặn đúng {saved:4d}")

    run_dir = args.out / f"{args.engine}_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary["wall_seconds"] = round(time.perf_counter() - started, 1)
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(run_dir / "predictions.jsonl", "w", encoding="utf-8") as handle:
        for i, (claim, _) in enumerate(rows):
            handle.write(json.dumps({"claim": claim, "gold": gold[i],
                                     **{f"{v}/{s}": preds[(v, s)][i] for v in args.views for s in STAGES}},
                                    ensure_ascii=False) + "\n")
    print(f"\nKết quả: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
