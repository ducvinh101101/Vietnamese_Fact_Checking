"""Đánh giá chẩn đoán trên challenge set có nhãn theo cấu trúc (xem scripts/challenge_set.py).

Chạy đúng pipeline production (configs/config.yaml: BM25 + PhoBERT, giống app.py và
script đánh giá), rồi báo cáo:

  * Độ chính xác theo TỪNG LOẠI hiện tượng (đổi số, đổi chiều, phủ định, ghép chi tiết bịa...)
  * Retrieval hit@k: có lấy được câu nguồn trong top-k không -> tách lỗi RETRIEVAL vs VERIFIER
  * Ma trận nhầm lẫn + P/R/F1 từng nhãn + Macro-F1 (thô và sau guard)
  * Tác động của GuardedVerifier: chặn được bao nhiêu SUPPORTED/REFUTED sai, hạ nhầm bao nhiêu đúng
  * Danh sách lỗi cụ thể để sửa

    py -3.13 scripts/run_challenge_eval.py                       # PhoBERT theo config
    py -3.13 scripts/run_challenge_eval.py --per-category 20     # chạy nhanh
    py -3.13 scripts/run_challenge_eval.py --engine rule_based   # so sánh engine demo

Engine được ghi trung thực vào báo cáo. Nếu yêu cầu PhoBERT mà không nạp được thì DỪNG,
không âm thầm chạy rule_based (trừ khi --allow-rule-based).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))

from scripts.challenge_set import (  # noqa: E402
    LABELS, build_challenge_set, load_items, load_passages, normalize, save_items,
)
from src.minimal_pair import refine as minimal_pair_refine  # noqa: E402
from src.pipeline import FactCheckingPipeline  # noqa: E402
from src.schemas import VerificationResult  # noqa: E402
from src.verdict_guard import guard_reason  # noqa: E402

SHORT = {"SUPPORTED": "SUP", "REFUTED": "REF", "NOT_ENOUGH_INFO": "NEI"}
CATEGORY_HELP = {
    "SUP_VERBATIM": "Câu nguyên văn trong kho -> phải SUPPORTED. Sai = verifier/retrieval yếu cả ở ca dễ nhất.",
    "SUP_FORMAT": "Chỉ khác khoảng trắng/dấu câu cuối -> phải giống SUP_VERBATIM. Thấp hơn = nhạy định dạng.",
    "REF_NUMBER": "Đổi một con số -> phải REFUTED. SUPPORTED = verifier mù số liệu (false positive nguy hiểm).",
    "REF_DIRECTION": "Đổi tăng<->giảm -> phải REFUTED. SUPPORTED = verifier không hiểu chiều biến động.",
    "REF_NEGATION": "Đổi 'đã'->'chưa' -> phải REFUTED. SUPPORTED = verifier bỏ qua phủ định.",
    "NEI_PARTIAL": "Câu thật + chi tiết bịa -> phải NEI. SUPPORTED = 'ủng hộ một phần' bị coi là ủng hộ toàn phần.",
    "NEI_FICTIONAL": "Sự kiện bịa -> phải NEI. SUPPORTED/REFUTED = suy diễn từ bài không liên quan.",
}


def build_pipeline(engine: str, allow_rule_based: bool, evidence_view: str = "passage") -> tuple[FactCheckingPipeline, str, dict]:
    config = yaml.safe_load((ROOT / "configs/config.yaml").read_text(encoding="utf-8"))
    v = config["verification"]
    common = dict(
        evidence_path=str(ROOT / config["paths"]["evidence_path"]),
        top_k=int(config["retrieval"]["top_k"]),
        support_threshold=float(v.get("support_threshold", 0.45)),
        refute_markers=v.get("refute_markers"),
    )
    if engine == "rule_based":
        return FactCheckingPipeline(engine="rule_based", **common), "rule_based", config
    try:
        pipeline = FactCheckingPipeline(
            engine="phobert",
            model_path=str(ROOT / v["model_path"]),
            vncorenlp_dir=str(ROOT / v["vncorenlp_dir"]),
            max_length=int(v.get("max_length", 256)),
            temperature=float(v.get("temperature", 1.0)),
            decisive_min_confidence=float(v.get("decisive_min_confidence", 0.0)),
            retrieval_rank_bias=float(v.get("retrieval_rank_bias", 0.0)),
            aggregation_model_path=str(ROOT / v["aggregation_model_path"]) if v.get("aggregation_model_path") else None,
            evidence_view=evidence_view,
            **common,
        )
        return pipeline, "phobert", config
    except Exception as exc:
        if not allow_rule_based:
            raise SystemExit(f"[challenge] Không nạp được PhoBERT: {exc}\n"
                             "Dừng để tránh báo cáo nhầm engine. Dùng --allow-rule-based nếu chấp nhận.")
        print(f"[challenge] PhoBERT lỗi ({exc}) -> chạy rule_based (được cho phép).", file=sys.stderr)
        return FactCheckingPipeline(engine="rule_based", **common), "rule_based (fallback)", config


def source_retrieved(item, retrieved) -> bool | None:
    if not item.source_sentence:
        return None
    needle = normalize(item.source_sentence).rstrip(".!?…").casefold()
    return any(needle in normalize(r.evidence.content).casefold() for r in retrieved)


def prf(gold: list[str], pred: list[str]) -> dict:
    out = {}
    for label in LABELS:
        tp = sum(g == label and p == label for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    out["macro_f1"] = sum(out[l]["f1"] for l in LABELS) / len(LABELS)
    out["accuracy"] = sum(g == p for g, p in zip(gold, pred)) / max(1, len(gold))
    return out


def confusion(gold, pred) -> dict:
    return {g: {p: sum(1 for a, b in zip(gold, pred) if a == g and b == p) for p in LABELS} for g in LABELS}


def run(items, pipeline) -> list[dict]:
    rows = []
    for n, item in enumerate(items, 1):
        t0 = time.perf_counter()
        try:
            result, retrieved = pipeline.run(item.claim)
            error = None
        except Exception as exc:  # một claim lỗi không được làm hỏng cả lượt đánh giá
            result, retrieved, error = None, [], f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - t0
        pred = result.label if result else "ERROR"
        reason = guard_reason(item.claim, result, retrieved) if result else None
        guarded = "NOT_ENOUGH_INFO" if reason else pred
        final, mp_reason = pred, None
        if result:
            after_guard = (VerificationResult("NOT_ENOUGH_INFO", 0.0, [], "[guard]") if reason else result)
            refined, mp_reason = minimal_pair_refine(item.claim, after_guard, retrieved)
            final = refined.label
        cited = [r.evidence for r in retrieved if result and r.evidence.passage_id in result.evidence_ids]
        rows.append({
            **asdict(item),
            "pred": pred, "pred_guarded": guarded, "guard_reason": reason,
            "pred_final": final, "minimal_pair": mp_reason,
            "confidence": round(result.confidence, 4) if result else None,
            "source_retrieved": source_retrieved(item, retrieved),
            "retrieved_ids": [r.evidence.passage_id for r in retrieved],
            "cited_id": cited[0].passage_id if cited else None,
            "cited_text": cited[0].content[:300] if cited else None,
            "seconds": round(elapsed, 3), "error": error,
        })
        if n % 25 == 0:
            print(f"[challenge] {n}/{len(items)} claim...", file=sys.stderr)
    return rows


def summarize(rows: list[dict], engine: str) -> dict:
    valid = [r for r in rows if r["pred"] != "ERROR"]
    gold = [r["gold"] for r in valid]
    raw, grd = [r["pred"] for r in valid], [r["pred_guarded"] for r in valid]
    fin = [r["pred_final"] for r in valid]
    per_cat = {}
    for cat in dict.fromkeys(r["category"] for r in rows):
        cr = [r for r in valid if r["category"] == cat]
        hits = [r for r in cr if r["source_retrieved"]]
        miss = [r for r in cr if r["source_retrieved"] is False]
        acc = lambda rs, key="pred": (sum(r[key] == r["gold"] for r in rs) / len(rs)) if rs else None
        per_cat[cat] = {
            "n": len(cr), "accuracy": acc(cr), "accuracy_guarded": acc(cr, "pred_guarded"),
            "accuracy_final": acc(cr, "pred_final"),
            "false_supported_final": (sum(r["pred_final"] == "SUPPORTED" for r in cr) / len(cr))
            if cr and cr[0]["gold"] != "SUPPORTED" else None,
            "pred_distribution": dict(Counter(SHORT[r["pred"]] for r in cr)),
            "retrieval_hit_rate": (len(hits) / len(cr)) if cr and cr[0]["source_retrieved"] is not None else None,
            "accuracy_when_source_retrieved": acc(hits), "accuracy_when_source_missed": acc(miss),
            "false_supported_rate": (sum(r["pred"] == "SUPPORTED" for r in cr) / len(cr))
            if cr and cr[0]["gold"] != "SUPPORTED" else None,
        }
    decisive_wrong_blocked = sum(1 for r in valid if r["pred"] in ("SUPPORTED", "REFUTED")
                                 and r["pred"] != r["gold"] and r["pred_guarded"] == "NOT_ENOUGH_INFO")
    decisive_right_lost = sum(1 for r in valid if r["pred"] in ("SUPPORTED", "REFUTED")
                              and r["pred"] == r["gold"] and r["pred_guarded"] == "NOT_ENOUGH_INFO")
    secs = sorted(r["seconds"] for r in valid)
    return {
        "engine": engine, "n_claims": len(rows), "n_errors": len(rows) - len(valid),
        "overall_raw": prf(gold, raw), "overall_guarded": prf(gold, grd), "overall_final": prf(gold, fin),
        "confusion_raw": confusion(gold, raw), "confusion_guarded": confusion(gold, grd),
        "confusion_final": confusion(gold, fin),
        "per_category": per_cat,
        "guard_effect": {"wrong_decisive_blocked": decisive_wrong_blocked,
                         "correct_decisive_lost": decisive_right_lost},
        "latency_seconds": {"p50": secs[len(secs) // 2] if secs else None,
                            "p95": secs[min(len(secs) - 1, int(0.95 * len(secs)))] if secs else None},
    }


def pct(x):
    return "—" if x is None else f"{100 * x:.1f}%"


def write_report(summary: dict, rows: list[dict], path: Path, max_examples: int = 8) -> None:
    o, g, fz = summary["overall_raw"], summary["overall_guarded"], summary["overall_final"]
    lines = [
        "# Báo cáo đánh giá challenge set", "",
        f"- Engine: **{summary['engine']}** · Số claim: {summary['n_claims']} · Lỗi chạy: {summary['n_errors']}",
        f"- Độ trễ: p50 {summary['latency_seconds']['p50']}s · p95 {summary['latency_seconds']['p95']}s",
        "- Lưu ý: claim lấy từ chính kho (in-distribution), REF_* là biến đổi tổng hợp, NEI theo giả định kho đóng.",
        "  Kết quả là CHẨN ĐOÁN điểm yếu, không thay cho đánh giá trên test split có nhãn người.", "",
        "## Tổng quan", "",
        "| | Accuracy | Macro-F1 | F1 SUP | F1 REF | F1 NEI |", "|---|---|---|---|---|---|",
        f"| Pipeline (thô) | {pct(o['accuracy'])} | {pct(o['macro_f1'])} | {pct(o['SUPPORTED']['f1'])} | "
        f"{pct(o['REFUTED']['f1'])} | {pct(o['NOT_ENOUGH_INFO']['f1'])} |",
        f"| + GuardedVerifier | {pct(g['accuracy'])} | {pct(g['macro_f1'])} | {pct(g['SUPPORTED']['f1'])} | "
        f"{pct(g['REFUTED']['f1'])} | {pct(g['NOT_ENOUGH_INFO']['f1'])} |",
        f"| + Guard + MinimalPair | {pct(fz['accuracy'])} | {pct(fz['macro_f1'])} | {pct(fz['SUPPORTED']['f1'])} | "
        f"{pct(fz['REFUTED']['f1'])} | {pct(fz['NOT_ENOUGH_INFO']['f1'])} |",
        "",
        f"Evidence view: **{summary.get('evidence_view', 'passage')}**. Cột 'final' = guard + minimal_pair (guard hạ nhầm nhiều trên dev thật, xem mục 6.8).",
        f"Guard chặn **{summary['guard_effect']['wrong_decisive_blocked']}** verdict sai, "
        f"nhưng hạ nhầm **{summary['guard_effect']['correct_decisive_lost']}** verdict đúng.", "",
        "## Ma trận nhầm lẫn (thô) — hàng: nhãn đúng, cột: dự đoán", "",
        "| | SUP | REF | NEI |", "|---|---|---|---|",
    ]
    for gl in LABELS:
        c = summary["confusion_raw"][gl]
        lines.append(f"| **{SHORT[gl]}** | {c['SUPPORTED']} | {c['REFUTED']} | {c['NOT_ENOUGH_INFO']} |")
    lines += ["", "## Theo từng loại hiện tượng", "",
              "| Loại | n | Acc | Acc+guard | Acc+safety | SUP sai (safety) | Hit@k nguồn | Acc khi lấy được nguồn | Acc khi trượt nguồn | SUP sai | Phân bố dự đoán |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for cat, m in summary["per_category"].items():
        lines.append(
            f"| {cat} | {m['n']} | {pct(m['accuracy'])} | {pct(m['accuracy_guarded'])} | {pct(m['accuracy_final'])} | {pct(m['false_supported_final'])} | "
            f"{pct(m['retrieval_hit_rate'])} | {pct(m['accuracy_when_source_retrieved'])} | "
            f"{pct(m['accuracy_when_source_missed'])} | {pct(m['false_supported_rate'])} | {m['pred_distribution']} |")
    lines += ["", "## Cách đọc & ví dụ lỗi", ""]
    for cat, m in summary["per_category"].items():
        lines += [f"### {cat}", "", CATEGORY_HELP.get(cat, ""), ""]
        wrong = [r for r in rows if r["category"] == cat and r["pred"] != r["gold"]]
        if not wrong:
            lines += ["Không có lỗi.", ""]
            continue
        lines.append(f"{len(wrong)} lỗi. Ví dụ:")
        lines.append("")
        for r in wrong[:max_examples]:
            src = {True: "có", False: "KHÔNG", None: "—"}[r["source_retrieved"]]
            lines.append(f"- `{r['id']}` vàng **{SHORT[r['gold']]}** → dự đoán **{SHORT.get(r['pred'], r['pred'])}** "
                         f"(conf {r['confidence']}, lấy được nguồn: {src}){' — ' + r['note'] if r['note'] else ''}")
            lines.append(f"  - Claim: {r['claim'].strip()[:220]}")
            if r["cited_text"]:
                lines.append(f"  - Trích dẫn: {r['cited_text'][:220]}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:  # noqa: C901
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-category", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--set", type=Path, help="Dùng lại challenge set đã lưu (jsonl) thay vì sinh mới")
    parser.add_argument("--engine", choices=["phobert", "rule_based"],
                        default=os.environ.get("FC_ENGINE", "phobert"))
    parser.add_argument("--allow-rule-based", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "challenge_eval")
    parser.add_argument("--evidence-view", choices=["passage", "focus_first", "focus_only", "ensemble"], default="passage",
                        help="Cách dựng chuỗi evidence đưa vào PhoBERT (xem src/evidence_focus.py)")
    parser.add_argument("--limit", type=int, help="Chỉ chạy N claim đầu (debug)")
    args = parser.parse_args()

    if args.set:
        items = load_items(args.set)
    else:
        config = yaml.safe_load((ROOT / "configs/config.yaml").read_text(encoding="utf-8"))
        items = build_challenge_set(load_passages(ROOT / config["paths"]["evidence_path"]),
                                    per_category=args.per_category, seed=args.seed)
    if args.limit:
        items = items[: args.limit]

    pipeline, engine, _ = build_pipeline(args.engine, args.allow_rule_based, args.evidence_view)
    run_dir = args.out / f"{engine.split()[0]}_{args.evidence_view}_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=True)
    save_items(items, run_dir / "challenge_set.jsonl")
    print(f"[challenge] Engine: {engine} · {len(items)} claim -> {run_dir}", file=sys.stderr)

    rows = run(items, pipeline)
    summary = summarize(rows, engine)
    summary["evidence_view"] = args.evidence_view
    with open(run_dir / "results.jsonl", "w", encoding="utf-8") as handle:
        for r in rows:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(summary, rows, run_dir / "report.md")

    o = summary["overall_raw"]
    print(f"\nEngine {engine} | Accuracy {pct(o['accuracy'])} | Macro-F1 {pct(o['macro_f1'])} "
          f"| +guard Macro-F1 {pct(summary['overall_guarded']['macro_f1'])} "
          f"| +safety Macro-F1 {pct(summary['overall_final']['macro_f1'])} (view={args.evidence_view})")
    for cat, m in summary["per_category"].items():
        print(f"  {cat:<14} acc {pct(m['accuracy']):>6}  hit@k {pct(m['retrieval_hit_rate']):>6}  "
              f"SUP-sai {pct(m['false_supported_rate']):>6}  safety acc {pct(m['accuracy_final']):>6} "
              f"SUP-sai {pct(m['false_supported_final']):>6}  {m['pred_distribution']}")
    print(f"\nBáo cáo: {run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
