"""So sánh cấu hình cuối với các baseline trên CÙNG test split (ghép cặp theo claim).

Không chạy lại mô hình: chỉ đọc các file dự đoán đã có trong outputs/predictions/.
In và ghi outputs/metrics/final_vs_baselines_test.json gồm:
* Macro-F1/accuracy từng cấu hình,
* chênh lệch Macro-F1 (final - baseline) + khoảng tin cậy 95% bootstrap ghép cặp,
* số claim được sửa đúng / bị làm sai so với từng baseline,
* tỷ lệ citation trùng URL gold CHỈ tính trên verdict quyết đoán (SUPPORTED/REFUTED).
  Lý do: verdict NEI không có citation theo thiết kế, nên tỷ lệ tính trên toàn bộ claim
  phạt cấu hình trả NEI nhiều hơn chứ không phản ánh chất lượng trích dẫn.

Lưu ý phương pháp: test split đã được dùng cho W4-02/E11/reranked trước đó, nên đây là
so sánh tương đối giữa các cấu hình, KHÔNG phải ước lượng độc lập chất lượng thực tế.

    py -3.13 scripts/compare_final_vs_baselines.py
    # So hai lượt bất kỳ trên CÙNG split (vd RT-V3 vs RT-V2 trên dev):
    py -3.13 scripts/compare_final_vs_baselines.py --base outputs/predictions/rt_v2_final_e2e_dev.csv --new outputs/predictions/rt_v3_hardneg_e2e_dev.csv --out outputs/metrics/rt_v3_vs_rt_v2_dev.json
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRED = ROOT / "outputs" / "predictions"
LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
RUNS = {
    "w4_02_bm25_e2": "w4_02_local_end_to_end_test.csv",
    "e11_rank_aware": "e11_rank_aware_local_end_to_end_test.csv",
    "w4_05_reranked": "reranked_e2e_test.csv",
    "final_rtv2_ensemble_mp": "final_local_end_to_end_test.csv",
}
FINAL = "final_rtv2_ensemble_mp"


def macro_f1(gold: list[str], pred: list[str]) -> float:
    scores = []
    for label in LABELS:
        tp = sum(g == label == p for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        scores.append(2 * tp / (2 * tp + fp + fn) if (tp + fp + fn) else 0.0)
    return sum(scores) / len(scores)


def load(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["source_row_id"]: row for row in csv.DictReader(handle)}


def main(rounds: int = 2000, seed: int = 42) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", type=Path, help="CSV dự đoán của cấu hình gốc")
    parser.add_argument("--new", type=Path, help="CSV dự đoán của cấu hình mới")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "metrics" / "final_vs_baselines_test.json")
    args = parser.parse_args()
    final = FINAL
    if args.base or args.new:
        if not (args.base and args.new):
            raise SystemExit("Cần cả --base và --new")
        final = "new"
        runs = {"base": load(args.base), "new": load(args.new)}
    else:
        missing = [name for name, file in RUNS.items() if not (PRED / file).exists()]
        if FINAL in missing:
            raise SystemExit("Thiếu dự đoán cấu hình cuối: chạy evaluate_local_end_to_end.py --use-final-config trước.")
        runs = {name: load(PRED / file) for name, file in RUNS.items() if name not in missing}
    ids = sorted(set.intersection(*(set(rows) for rows in runs.values())), key=lambda x: int(x) if x.isdigit() else x)
    gold = [runs[final][i]["gold_label"] for i in ids]
    for name, rows in runs.items():
        if [rows[i]["gold_label"] for i in ids] != gold:
            raise SystemExit(f"Nhãn gold của {name} không khớp — không cùng split.")
    preds = {name: [rows[i]["predicted_label"] for i in ids] for name, rows in runs.items()}

    rng = random.Random(seed)
    n = len(ids)
    samples = [[rng.randrange(n) for _ in range(n)] for _ in range(rounds)]
    report: dict[str, object] = {"n_claims": n, "bootstrap_rounds": rounds, "seed": seed,
                                 "note": "Test split đã xem nhiều lần; so sánh tương đối, không phải ước lượng độc lập.",
                                 "configs": {}, "final_vs": {}}
    for name, rows in runs.items():
        decisive = [rows[i] for i in ids if rows[i]["predicted_label"] != "NOT_ENOUGH_INFO"]
        cited = sum(r["citation_url_matches_gold"] == "True" for r in decisive)
        report["configs"][name] = {
            "macro_f1": round(macro_f1(gold, preds[name]), 6),
            "accuracy": round(sum(g == p for g, p in zip(gold, preds[name])) / n, 6),
            "decisive_predictions": len(decisive),
            "citation_url_matches_gold_among_decisive": round(cited / len(decisive), 6) if decisive else None,
        }
    for name in runs:
        if name == final:
            continue
        diffs = []
        for ix in samples:
            g = [gold[i] for i in ix]
            diffs.append(macro_f1(g, [preds[final][i] for i in ix]) - macro_f1(g, [preds[name][i] for i in ix]))
        diffs.sort()
        report["final_vs"][name] = {
            "delta_macro_f1": round(macro_f1(gold, preds[final]) - macro_f1(gold, preds[name]), 6),
            "ci95": [round(diffs[int(0.025 * rounds)], 6), round(diffs[int(0.975 * rounds) - 1], 6)],
            "fixed": sum(preds[final][j] == gold[j] != preds[name][j] for j in range(n)),
            "broken": sum(preds[name][j] == gold[j] != preds[final][j] for j in range(n)),
        }
    print(f"Test n={n}")
    for name, item in report["configs"].items():
        print(f"  {name:<24} Macro-F1 {100 * item['macro_f1']:5.1f}%  Acc {100 * item['accuracy']:5.1f}%  "
              f"citation đúng URL (verdict quyết đoán) {100 * (item['citation_url_matches_gold_among_decisive'] or 0):5.1f}%")
    for name, item in report["final_vs"].items():
        lo, hi = item["ci95"]
        print(f"  final - {name:<18} {100 * item['delta_macro_f1']:+5.1f} [{100 * lo:+5.1f}, {100 * hi:+5.1f}]"
              f"  sửa đúng {item['fixed']}, làm sai {item['broken']}")
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Ghi {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
