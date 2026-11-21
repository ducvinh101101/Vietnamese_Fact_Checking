"""Đánh giá bài toán KIỂM TRA NGUỒN trên ViFactCheck (dev mặc định).

Tạo 5 nhóm kiểm thử từ dữ liệu sẵn có, mỗi nhóm có nhãn kỳ vọng:

=====================  ==============================================  ===============
Nhóm                   Cách tạo                                        Kỳ vọng
=====================  ==============================================  ===============
A in_corpus            claim SUPPORTED, kho đầy đủ                     SOURCE_FOUND
B refuted              claim REFUTED, kho đầy đủ                       SOURCE_CONFLICT
C leave_gold_out       claim SUPPORTED, BỎ bài gốc (URL) khỏi kho       NO_SOURCE*
D nei                  claim NEI (bài gốc không đủ thông tin)          NO_SOURCE
E perturbed            claim SUPPORTED bị đổi con số                   không FOUND
=====================  ==============================================  ===============

(*) Bài khác trong kho có thể đưa cùng tin; tỷ lệ FOUND ở nhóm C là CẬN TRÊN
của tỷ lệ báo nhầm "có nguồn".

Ngoài ra đo retrieval mức đoạn: Hit@k = có cửa sổ/passage chứa câu Evidence
gold (độ phủ âm tiết ≥ 0.8) trong top-k, so sánh BM25 baseline cũ (passage
700 ký tự, top-k) với retriever mới (multi-query + cửa sổ câu + rerank).

Ví dụ:
    python scripts/evaluate_source_attribution.py --limit 300 --sweep
    python scripts/evaluate_source_attribution.py --verifier --limit 300
    python scripts/evaluate_source_attribution.py --legacy-baseline --verifier --limit 300
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
from itertools import product
import json
from pathlib import Path
import random
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.io_utils import load_evidence_jsonl
from src.retriever import BM25Retriever
from src.schemas import RetrievedEvidence
from src.source_attribution import (
    AttributionThresholds, LEGACY_TO_SOURCE, SourceAttributionPipeline, check_facets,
)
from src.source_attribution_factory import build_local_retriever, build_scorer, build_verifier, load_config
from src.source_reranker import LexicalSourceScorer, rerank
from src.vi_text import content_syllables


EXPECTED = {"A_in_corpus": "SOURCE_FOUND", "B_refuted": "SOURCE_CONFLICT", "C_leave_gold_out": "NO_SOURCE",
            "D_nei": "NO_SOURCE", "E_perturbed": "NOT_FOUND"}
GROUPS = list(EXPECTED)


class ExcludingRetriever:
    """Bỏ mọi passage thuộc các URL bị loại (giả lập "nguồn không có trong kho")."""

    def __init__(self, base, excluded_urls: set[str]) -> None:
        self.base, self.excluded_urls = base, excluded_urls

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        results = self.base.search(claim, top_k + 80)
        return [item for item in results if item.evidence.url not in self.excluded_urls][:top_k]


def coverage(gold: str, passage: str) -> float:
    gold_terms = set(content_syllables(gold))
    return len(gold_terms & set(content_syllables(passage))) / max(1, len(gold_terms))


def perturb_number(claim: str, rng: random.Random) -> str | None:
    """Đổi một con số trong claim (giữ định dạng) – claim trở thành "không có nguồn"."""
    matches = [m for m in re.finditer(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w])", claim)
               if not (len(m.group(0)) == 4 and m.group(0).startswith(("19", "20")))]
    if not matches:
        return None
    match = rng.choice(matches)
    raw = match.group(0)
    value = float(raw.replace(",", "."))
    factor = rng.choice([1.5, 2.0, 0.5, 3.0])
    new = value * factor if value else 7
    new_text = str(int(round(new))) if "." not in raw and "," not in raw else f"{new:.1f}".replace(".", ",")
    if new_text == raw:
        new_text = str(int(value) + 7)
    return claim[: match.start()] + new_text + claim[match.end():]


def build_cases(frame: pd.DataFrame, limit: int | None, seed: int) -> list[dict]:
    rng = random.Random(seed)
    frame = frame.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    supported = frame[frame.labels == 0]
    refuted = frame[frame.labels == 1]
    nei = frame[frame.labels == 2]
    per_group = limit // len(GROUPS) if limit else None

    def take(rows: pd.DataFrame, n: int | None) -> pd.DataFrame:
        return rows if n is None else rows.head(n)

    cases: list[dict] = []
    for row in take(supported, per_group).itertuples():
        cases.append({"group": "A_in_corpus", "claim": row.Statement, "url": row.Url, "gold": row.Evidence, "exclude": False})
    for row in take(refuted, per_group).itertuples():
        cases.append({"group": "B_refuted", "claim": row.Statement, "url": row.Url, "gold": row.Evidence, "exclude": False})
    shifted = supported.iloc[len(supported) // 2:]  # khác tập A để không lặp claim
    for row in take(shifted, per_group).itertuples():
        cases.append({"group": "C_leave_gold_out", "claim": row.Statement, "url": row.Url, "gold": row.Evidence, "exclude": True})
    for row in take(nei, per_group).itertuples():
        cases.append({"group": "D_nei", "claim": row.Statement, "url": row.Url, "gold": row.Evidence, "exclude": False})
    perturbed = 0
    for row in supported.itertuples():
        if per_group is not None and perturbed >= per_group:
            break
        changed = perturb_number(row.Statement, rng)
        if changed:
            perturbed += 1
            cases.append({"group": "E_perturbed", "claim": changed, "url": row.Url, "gold": row.Evidence,
                          "exclude": False, "original": row.Statement})
    return cases


def correct(group: str, label: str) -> bool:
    expected = EXPECTED[group]
    return label != "SOURCE_FOUND" if expected == "NOT_FOUND" else label == expected


def summarise(records: list[dict]) -> dict:
    by_group: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        by_group[record["group"]][record["label"]] += 1
    groups = {}
    for group in GROUPS:
        counts = by_group.get(group, Counter())
        total = sum(counts.values())
        hits = sum(count for label, count in counts.items() if correct(group, label))
        groups[group] = {"n": total, "accuracy": round(hits / total, 4) if total else None,
                         "labels": dict(counts), "expected": EXPECTED[group]}
    # "Có nguồn" nhị phân: dương = nhóm A; âm = C, D, E. (B không tính – có nguồn nhưng lệch.)
    tp = by_group["A_in_corpus"]["SOURCE_FOUND"]
    fn = sum(by_group["A_in_corpus"].values()) - tp
    fp = sum(by_group[g]["SOURCE_FOUND"] for g in ("C_leave_gold_out", "D_nei", "E_perturbed"))
    tn = sum(sum(by_group[g].values()) for g in ("C_leave_gold_out", "D_nei", "E_perturbed")) - fp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracies = [g["accuracy"] for g in groups.values() if g["accuracy"] is not None]
    return {
        "groups": groups,
        "source_found_binary": {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
                                "false_found_rate": round(fp / (fp + tn), 4) if fp + tn else None},
        "mean_group_accuracy": round(sum(accuracies) / len(accuracies), 4) if accuracies else None,
    }


def retrieval_hits(cases: list[dict], legacy: BM25Retriever, pipeline: SourceAttributionPipeline, ks=(1, 3, 5)) -> dict:
    rows = [case for case in cases if case["group"] in ("A_in_corpus", "B_refuted") and isinstance(case["gold"], str)]
    hits = {"legacy_bm25_passage": Counter(), "new_hybrid_window": Counter(), "new_hybrid_reranked": Counter()}
    for case in rows:
        legacy_results = legacy.search(case["claim"], max(ks))
        candidates = pipeline.retriever.search(case["claim"], pipeline.candidate_k)
        reranked = rerank(pipeline.scorer, case["claim"], candidates, max(ks))
        for name, results in (("legacy_bm25_passage", legacy_results), ("new_hybrid_window", candidates),
                              ("new_hybrid_reranked", reranked)):
            for k in ks:
                if any(coverage(case["gold"], item.evidence.content) >= 0.8 for item in results[:k]):
                    hits[name][k] += 1
    return {name: {f"hit@{k}": round(counter[k] / len(rows), 4) for k in ks} for name, counter in hits.items()} | {"n": len(rows)}


def assess_all(pipeline: SourceAttributionPipeline, cases: list[dict], full_retriever) -> list[dict]:
    """Chạy retrieval + rerank + verifier MỘT lần, lưu assessment để sweep ngưỡng."""
    stored = []
    zero = replace(pipeline.thresholds, relevance=0.0)
    for index, case in enumerate(cases, start=1):
        pipeline.retriever = ExcludingRetriever(full_retriever, {case["url"]}) if case["exclude"] else full_retriever
        original = pipeline.thresholds
        pipeline.thresholds = zero  # verifier chấm mọi đoạn đã rerank; ngưỡng áp dụng sau
        result = pipeline.run(case["claim"])
        pipeline.thresholds = original
        stored.append({"case": case, "assessed": result.assessed, "queries": result.queries,
                       "retrieved": result.retrieved_count})
        if index % 50 == 0:
            print(f"  {index}/{len(cases)} claims", flush=True)
    pipeline.retriever = full_retriever
    return stored


def decide_with(pipeline: SourceAttributionPipeline, stored: list[dict], thresholds: AttributionThresholds,
                recompute_facets: bool = False, lexical_blend: float = 0.0) -> list[dict]:
    """``recompute_facets``: so khớp số/ngày lại bằng code hiện tại (đo tác động của thay đổi facet trên
    assessment đã lưu, không chạy lại model). Với reranker verifier trộn ``lexical_blend`` điểm lexical, điểm
    liên quan được hiệu chỉnh theo chênh lệch lexical mới − cũ (phần model giữ nguyên)."""
    pipeline.thresholds = thresholds
    new_lexical, old_lexical = LexicalSourceScorer(), LexicalSourceScorer(approximate=False)
    records = []
    for entry in stored:
        assessed = entry["assessed"]
        if recompute_facets:
            claim = entry["case"]["claim"]
            texts = [a.item.evidence.content for a in assessed]
            delta = ([lexical_blend * (n - o) for n, o in zip(new_lexical.score(claim, texts), old_lexical.score(claim, texts))]
                     if lexical_blend and texts else [0.0] * len(assessed))
            assessed = [replace(a, relevance=a.relevance + d, facets=check_facets(claim, a.item.evidence.content))
                        for a, d in zip(assessed, delta)]
        assessed = pipeline.assign_statuses(list(assessed))
        result = pipeline._decide(entry["case"]["claim"], assessed, entry["queries"], entry["retrieved"])
        records.append({"group": entry["case"]["group"], "claim": entry["case"]["claim"], "label": result.label,
                        "confidence": result.confidence,
                        "citations": [a.item.evidence.url for a in result.citations],
                        "gold_url": entry["case"]["url"]})
    return records


def legacy_records(cases: list[dict], config: dict, checker=None) -> list[dict]:
    """Pipeline cũ (BM25 top-3 → RT-V2 rank policy) với nhãn ánh xạ sang nhãn nguồn.

    ``checker`` là instance PhoBERT đã nạp (JVM VnCoreNLP chỉ khởi động được một
    lần mỗi tiến trình); policy được đặt lại đúng như config.yaml đã khóa.
    """
    from src.decision_policy import DecisionPolicy
    from src.pipeline import FactCheckingPipeline

    legacy_cfg = load_config(ROOT / "configs" / "config.yaml")
    verification = legacy_cfg["verification"]
    full = BM25Retriever(load_evidence_jsonl(ROOT / legacy_cfg["paths"]["evidence_path"]))
    kwargs = dict(top_k=3, retriever=full)
    if checker is not None:
        checker.decision_policy = DecisionPolicy(verification["temperature"], verification["decisive_min_confidence"])
        checker.retrieval_rank_bias = verification["retrieval_rank_bias"]
        kwargs["checker"] = checker
    else:
        kwargs.update(support_threshold=verification["support_threshold"], refute_markers=verification["refute_markers"])
    pipeline = FactCheckingPipeline(**kwargs)
    records = []
    for case in cases:
        pipeline.retriever = ExcludingRetriever(full, {case["url"]}) if case["exclude"] else full
        result, _ = pipeline.run(case["claim"])
        records.append({"group": case["group"], "claim": case["claim"], "label": LEGACY_TO_SOURCE[result.label]})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    parser.add_argument("--limit", type=int, default=300, help="tổng số claim (chia đều 5 nhóm); 0 = tất cả")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--config", default=str(ROOT / "configs" / "source_attribution.yaml"))
    parser.add_argument("--reranker", default=None, help="ghi đè reranker.model (vd. BAAI/bge-reranker-v2-m3)")
    parser.add_argument("--segment", action="store_true", help="tách từ VnCoreNLP cho reranker PhoBERT")
    parser.add_argument("--lexical-blend", type=float, default=None, help="reranker=verifier: tỷ trọng điểm lexical")
    parser.add_argument("--verifier", action="store_true", help="dùng verifier RT-V2 đã train")
    parser.add_argument("--sweep", action="store_true", help="dò ngưỡng trên split này (chỉ dùng dev)")
    parser.add_argument("--legacy-baseline", action="store_true", help="chạy thêm pipeline cũ để so sánh")
    parser.add_argument("--output", default=None)
    parser.add_argument("--save-assessments", default=None, help="lưu kết quả chấm (pickle) để dò ngưỡng lại không cần model")
    parser.add_argument("--load-assessments", default=None, help="nạp kết quả chấm đã lưu; bỏ qua retrieval/model")
    parser.add_argument("--recompute-facets", action="store_true",
                        help="với --load-assessments: so khớp số/ngày lại bằng code hiện tại")
    args = parser.parse_args()
    if args.sweep and args.split == "test":
        raise SystemExit("Không dò ngưỡng trên test.")

    config = load_config(args.config)
    if args.reranker:
        config["reranker"] = dict(config["reranker"], model=args.reranker, segment=args.segment)
    if args.lexical_blend is not None:
        config["reranker"] = dict(config["reranker"], lexical_blend=args.lexical_blend)
    frame = pd.read_parquet(ROOT / f"data/processed/vifactcheck_group_split/{args.split}.parquet")
    cases = build_cases(frame, args.limit or None, args.seed)
    print(f"{len(cases)} claim: {dict(Counter(c['group'] for c in cases))}")

    import pickle

    if args.load_assessments:
        with open(args.load_assessments, "rb") as handle:
            saved = pickle.load(handle)
        stored, report = saved["stored"], saved["report"]
        verifier = object() if report["verifier"] else None
        model = None  # không chạy lại model / pipeline cũ khi nạp kết quả đã lưu
        if args.legacy_baseline:
            raise SystemExit("--legacy-baseline cần chạy model; không dùng cùng --load-assessments")
        pipeline = SourceAttributionPipeline(object(), None, verifier,
                                             AttributionThresholds(**config["decision"]["thresholds"]),
                                             require_claim_numbers=bool(config["decision"].get("require_claim_numbers")))
    else:
        started = time.perf_counter()
        full_retriever = build_local_retriever(config)
        print(f"Index: {len(full_retriever.evidence_items)} cửa sổ câu ({time.perf_counter() - started:.1f}s)")
        needs_model = args.verifier or config["reranker"]["model"] == "verifier"
        model = build_verifier(dict(config, verifier=dict(config["verifier"], enabled=True))) if needs_model else None
        verifier = model if args.verifier else None
        pipeline = SourceAttributionPipeline(
            full_retriever, build_scorer(config, model), verifier, AttributionThresholds(**config["decision"]["thresholds"]),
            candidate_k=int(config["decision"]["candidate_k"]), assess_k=int(config["decision"]["assess_k"]),
            require_claim_numbers=bool(config["decision"].get("require_claim_numbers")),
        )
        legacy_bm25 = BM25Retriever(load_evidence_jsonl(ROOT / config["local"]["corpus"]))

        report: dict = {"split": args.split, "n_claims": len(cases), "reranker": config["reranker"]["model"],
                        "verifier": bool(verifier), "config": args.config}
        print("Retrieval mức đoạn (Hit@k với câu Evidence gold)…")
        report["passage_retrieval"] = retrieval_hits(cases, legacy_bm25, pipeline)
        print(json.dumps(report["passage_retrieval"], ensure_ascii=False, indent=1))

        t0 = time.perf_counter()
        stored = assess_all(pipeline, cases, full_retriever)
        report["seconds_per_claim"] = round((time.perf_counter() - t0) / max(1, len(cases)), 3)
        if args.save_assessments:
            with open(args.save_assessments, "wb") as handle:
                pickle.dump({"stored": stored, "report": report}, handle)

    configured = AttributionThresholds(**config["decision"]["thresholds"])
    blend = float(config["reranker"].get("lexical_blend", 0.0)) if config["reranker"]["model"] == "verifier" else 0.0
    records = decide_with(pipeline, stored, configured, args.recompute_facets, blend)
    report["new_pipeline"] = {"thresholds": configured.__dict__, **summarise(records)}

    if args.sweep:
        best = None
        grid = product([0.35, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95],
                       [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98],
                       [0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9])
        for relevance, support, lexical_support in grid:
            if verifier is None and lexical_support < relevance:
                continue
            thresholds = AttributionThresholds(relevance, support, 0.5, lexical_support)
            summary = summarise(decide_with(pipeline, stored, thresholds))
            key = (summary["mean_group_accuracy"] or 0, summary["source_found_binary"]["f1"])
            if best is None or key > best[0]:
                best = (key, thresholds, summary)
        report["sweep_best"] = {"thresholds": best[1].__dict__, **best[2]}
        records = decide_with(pipeline, stored, best[1])

    if args.legacy_baseline:
        print("Chạy pipeline cũ để so sánh…")
        report["legacy_pipeline"] = summarise(legacy_records(cases, config, model if args.verifier else None))

    model_path = Path(str(config["reranker"]["model"]))
    model_name = model_path.parent.name if model_path.name == "best_model" else model_path.name
    blend = config["reranker"].get("lexical_blend") if model_name == "verifier" else None
    tag = f"{args.split}_{model_name}{f'-blend{blend:g}' if blend else ''}_{'verifier' if verifier else 'noverifier'}"
    output = Path(args.output) if args.output else ROOT / f"outputs/metrics/source_attribution_{tag}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    predictions = output.with_name(output.stem + "_predictions.jsonl")
    predictions.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "passage_retrieval"}, ensure_ascii=False, indent=1))
    print(f"Đã ghi {output}")


if __name__ == "__main__":
    main()
