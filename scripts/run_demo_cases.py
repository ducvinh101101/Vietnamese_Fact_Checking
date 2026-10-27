"""W4-04 — chạy bộ claim minh họa qua hệ thống THẬT và ghi kết quả cho báo cáo/demo.

    py -3.13 scripts/run_demo_cases.py                 # chế độ local (đã đánh giá)
    py -3.13 scripts/run_demo_cases.py --with-web      # thêm ca thời sự qua Tavily (cần TAVILY_API_KEY)

Ghi outputs/demo/demo_cases.md (bảng đọc được) và outputs/demo/demo_cases.json (đầy đủ JSON
contract + chẩn đoán). Kết quả là quan sát định tính trên 5–6 ca chọn sẵn, không phải số đo chất lượng.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))

from src.demo_cases import DEMO_CASES  # noqa: E402
from src.system_builder import SystemOptions, build_system, load_config, load_dotenv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-web", action="store_true", help="Chạy cả ca thời sự ở chế độ local+web")
    parser.add_argument("--engine", choices=["phobert", "rule_based"], help="Ghi đè engine (rule_based để thử luồng)")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "demo")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    config = load_config(ROOT)

    systems = {}
    rows = []
    for case in DEMO_CASES:
        if case["mode"] == "hybrid" and not args.with_web:
            continue
        if case["mode"] not in systems:
            systems[case["mode"]] = build_system(SystemOptions(mode=case["mode"], engine=args.engine),
                                                 config=config, root=ROOT)
        system = systems[case["mode"]]
        response = system.check(case["claim"])
        verdict = response["verdict"]
        cited = response["citations"][0] if response["citations"] else None
        diagnostics = response["diagnostics"]
        match = verdict["label"] == case["expected"] if case["expected"] in {
            "SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"} else None
        rows.append({**case, "predicted": verdict["label"], "confidence": verdict["confidence"],
                     "match": match, "cited_url": cited["url"] if cited else None,
                     "cited_origin": cited.get("origin") if cited else None,
                     "minimal_pair_reason": diagnostics.get("minimal_pair_reason"),
                     "guard_reason": diagnostics.get("guard_reason"),
                     "engine": "rule_based (fallback)" if system.fallback_reason else (args.engine or config["verification"]["engine"]),
                     "response": response})
        mark = {True: "✓", False: "✗", None: "·"}[match]
        print(f"{mark} {case['id']} [{case['mode']}] kỳ vọng {case['expected']:<16} → {verdict['label']:<16}"
              f" ({verdict['confidence']:.2f})  {case['title']}")

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    (args.out / "demo_cases.json").write_text(
        json.dumps({"generated_at": stamp, "cases": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# Kết quả demo (W4-04) — {stamp}", "",
             "Quan sát định tính trên các ca chọn sẵn (src/demo_cases.py); không phải số đo chất lượng.", "",
             "| Ca | Chế độ | Claim | Kỳ vọng | Hệ thống | Điểm | Trích dẫn | Ghi chú |",
             "|---|---|---|---|---|---:|---|---|"]
    for row in rows:
        note = row["minimal_pair_reason"] or row["guard_reason"] or row["why"]
        cite = f"[{row['cited_origin']}]({row['cited_url']})" if row["cited_url"] else "—"
        lines.append(f"| {row['id']} | {row['mode']} | {row['claim']} | {row['expected']} | **{row['predicted']}** | "
                     f"{row['confidence']:.2f} | {cite} | {note} |")
    engines = sorted({row["engine"] for row in rows})
    lines += ["", f"Verifier: {', '.join(engines)}. Đúng kỳ vọng: "
              f"{sum(1 for r in rows if r['match'])}/{sum(1 for r in rows if r['match'] is not None)} ca có nhãn kỳ vọng."]
    (args.out / "demo_cases.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nĐã ghi {args.out / 'demo_cases.md'} và demo_cases.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
