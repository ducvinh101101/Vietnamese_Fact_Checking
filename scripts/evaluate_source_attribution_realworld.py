"""Chạy pipeline kiểm tra nguồn ĐẦY ĐỦ (kho cục bộ + web) trên tập claim thực tế do nhóm gán nhãn.

File CSV theo mẫu ``data/evaluation/source_attribution_realworld_template.csv``:

* ``group``: ``recent_real`` (tin thật sau 2023, có URL nguồn) | ``paraphrase`` (diễn đạt
  lại tin thật) | ``fabricated`` (bịa hoàn toàn) | ``perturbed`` (tin thật bị sửa số/tên/ngày);
* ``expected_label``: ``SOURCE_FOUND`` | ``SOURCE_CONFLICT`` | ``NO_SOURCE``;
* ``source_url``: URL nguồn đúng (để đo citation có trỏ đúng bài không), có thể để trống.

Cần ``TAVILY_API_KEY``; mỗi claim tốn tối đa ``requests_per_claim`` request.

    python scripts/evaluate_source_attribution_realworld.py data/evaluation/source_attribution_realworld_v1.csv
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.env_loader import load_dotenv
from src.source_attribution import SOURCE_LABELS
from src.source_attribution_factory import build_pipeline, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--no-web", action="store_true", help="chỉ kho cục bộ (để so sánh)")
    parser.add_argument("--no-verifier", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    frame = pd.read_csv(args.csv)
    missing = {"claim_id", "group", "claim", "expected_label"} - set(frame.columns)
    if missing:
        raise SystemExit(f"Thiếu cột: {sorted(missing)}")
    if not frame.expected_label.isin(SOURCE_LABELS).all():
        raise SystemExit(f"expected_label phải thuộc {SOURCE_LABELS}")
    load_dotenv()
    if not args.no_web and not os.environ.get(load_config()["web_retrieval"]["provider"]["api_key_env"]):
        raise SystemExit("Chưa đặt TAVILY_API_KEY; dùng --no-web nếu chỉ muốn đo kho cục bộ.")

    pipeline = build_pipeline(use_web=not args.no_web, use_verifier=not args.no_verifier)
    rows = []
    for record in frame.itertuples():
        output = pipeline.run_json(str(record.claim))
        cited = [c["url"] for c in output["citations"]]
        source_url = str(getattr(record, "source_url", "") or "")
        rows.append({
            "claim_id": record.claim_id, "group": record.group, "expected": record.expected_label,
            "predicted": output["verdict"]["label"], "confidence": output["verdict"]["confidence"],
            "cited_urls": cited, "cites_expected_url": bool(source_url) and source_url in cited,
            "independent_sources": output["verdict"]["independent_sources"],
        })
        print(f"{record.claim_id}: {record.expected_label} → {output['verdict']['label']}", flush=True)

    by_group: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_group[row["group"]]["n"] += 1
        by_group[row["group"]]["correct"] += row["expected"] == row["predicted"]
    labels = list(SOURCE_LABELS)
    per_label = {}
    for label in labels:
        tp = sum(r["expected"] == label and r["predicted"] == label for r in rows)
        fp = sum(r["expected"] != label and r["predicted"] == label for r in rows)
        fn = sum(r["expected"] == label and r["predicted"] != label for r in rows)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        per_label[label] = {"precision": round(p, 4), "recall": round(r, 4),
                            "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}
    with_url = [r for r in rows if r["expected"] == "SOURCE_FOUND" and r["predicted"] == "SOURCE_FOUND"]
    report = {
        "n": len(rows), "web": not args.no_web, "verifier": not args.no_verifier,
        "accuracy": round(sum(r["expected"] == r["predicted"] for r in rows) / max(1, len(rows)), 4),
        "macro_f1": round(sum(v["f1"] for v in per_label.values()) / len(labels), 4),
        "per_label": per_label,
        "per_group_accuracy": {g: round(c["correct"] / c["n"], 4) for g, c in by_group.items()},
        "citation_hits_expected_url": round(sum(r["cites_expected_url"] for r in with_url) / max(1, len(with_url)), 4),
    }
    output = args.output or ROOT / f"outputs/metrics/source_attribution_realworld_{'web' if not args.no_web else 'local'}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"report": report, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
