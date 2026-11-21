"""Chạy pipeline kiểm tra nguồn ĐẦY ĐỦ (kho cục bộ + web) trên tập claim thực tế do nhóm gán nhãn.

Đầu vào: phiếu Excel ``data/evaluation/PHIEU_GAN_NHAN_NGUON_V1.xlsx`` (tạo bằng
``scripts/create_realworld_labeling_form.py``; nhãn tự suy ra từ nhóm, dòng lỗi bị bỏ qua) hoặc file CSV theo
mẫu ``data/evaluation/source_attribution_realworld_template.csv``:

* ``group``: ``recent_real`` (tin thật sau 2023, có URL nguồn) | ``paraphrase`` (diễn đạt
  lại tin thật) | ``fabricated`` (bịa hoàn toàn) | ``perturbed`` (tin thật bị sửa số/tên/ngày);
* ``expected_label``: ``SOURCE_FOUND`` | ``SOURCE_CONFLICT`` | ``NO_SOURCE``;
* ``source_url``: URL nguồn đúng (để đo citation có trỏ đúng bài không), có thể để trống.

Cần ``TAVILY_API_KEY``; mỗi claim tốn tối đa ``requests_per_claim`` request.

    python scripts/evaluate_source_attribution_realworld.py data/evaluation/PHIEU_GAN_NHAN_NGUON_V1.xlsx
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.env_loader import load_dotenv
from src.realworld_labels import load_labeled_claims
from src.hybrid_retriever import FusedRetriever
from src.schemas import Evidence, RetrievedEvidence
from src.source_attribution import SOURCE_LABELS, is_web_retriever
from src.source_attribution_factory import build_pipeline, load_config
from src.web_retriever import WEB_RETRYABLE_STATUSES


def same_article(expected: str, cited: str) -> bool:
    """Cùng bài báo: so phần cuối đường dẫn (mã bài), bỏ qua tên miền – vd. nld.com.vn chuyển sang tuoitre.vn/nld/."""
    def tail(url: str) -> str:
        return urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1].lower()
    return expected == cited or (bool(tail(expected)) and tail(expected) == tail(cited))


REACHED = ("ok", "no_eligible_passages")


def diagnose_source(source_url: str, trace: dict | None, assessed: list[dict], relevance_threshold: float) -> dict:
    """Bài gốc (source_url) đi tới đâu trong pipeline: có trong kết quả tìm kiếm không, tải được không,
    đoạn tốt nhất của nó được chấm bao nhiêu. Chỉ đọc vết đã lưu, không gọi lại web."""
    trace = trace or {}
    hits = [r for r in trace.get("search_results", []) if r.get("url") and same_article(source_url, r["url"])]
    pages = [p for p in trace.get("pages", [])
             if same_article(source_url, p.get("url", "")) or same_article(source_url, p.get("final_url", ""))]
    # Trang trùng URL chỉ ghi "duplicate" – lấy lần xử lý thật.
    page = next((p for p in pages if p.get("outcome") != "duplicate"), pages[0] if pages else {})
    own = [a for a in assessed if same_article(source_url, a.get("url", ""))]
    best = max(own, key=lambda a: a["relevance"], default=None)
    return {
        "in_search_results": bool(hits),
        "search_rank": [hits[0]["query_index"], hits[0]["rank"]] if hits else None,
        "page_outcome": page.get("outcome"),
        "page_error": page.get("error"),
        "web_max_relevance": page.get("max_relevance"),
        "assessed_max_relevance": best["relevance"] if best else None,
        "assessed_status": best["status"] if best else None,
        "conflicting_details": best.get("conflicting_details", []) if best else [],
        "relevance_threshold": relevance_threshold,
    }


def miss_stage(source_url: str, web_status: str | None, diagnosis: dict, relevance_threshold: float) -> str:
    """Tầng làm trượt một tin thật (chỉ gọi khi không ra SOURCE_FOUND)."""
    if not source_url:
        return "no_source_url"
    if web_status not in REACHED:
        return "web_error"
    if not diagnosis["in_search_results"]:
        return "search_miss"
    if diagnosis["page_outcome"] != "used":
        return str(diagnosis["page_outcome"] or "not_read")
    if diagnosis["assessed_max_relevance"] is None:
        return "outranked"  # tải được nhưng đoạn của bài gốc không lọt top assess_k
    if diagnosis["assessed_max_relevance"] < relevance_threshold:
        return "below_threshold"
    if diagnosis["conflicting_details"]:
        return "facet_conflict"
    return "verifier"


def web_retriever_of(pipeline) -> object | None:
    retrievers = getattr(pipeline.retriever, "retrievers", [pipeline.retriever])
    return next((r for r in retrievers if is_web_retriever(r)), None)


class RecordingWeb:
    """Bọc WebRetriever thật, giữ lại kết quả lần search gần nhất để ghi vào bản ghi web."""

    is_web_retriever = True

    def __init__(self, inner) -> None:
        self.inner = inner
        self.last_claim: str | None = None
        self.last_results: list[RetrievedEvidence] = []

    @property
    def last_status(self) -> str:
        return self.inner.last_status

    @property
    def last_trace(self) -> dict:
        return self.inner.last_trace

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        self.last_claim, self.last_results = claim, []
        self.last_results = self.inner.search(claim, top_k)
        return self.last_results


class ReplayWeb:
    """Phát lại kết quả web đã ghi (theo nội dung claim) – chấm lại không cần mạng, không tốn lượt."""

    is_web_retriever = True

    def __init__(self, snapshot: dict[str, dict]) -> None:
        self.snapshot = snapshot
        self.last_status, self.last_trace = "not_run", {}

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        record = self.snapshot.get(claim)
        if record is None:
            self.last_status, self.last_trace = "not_in_snapshot", {}
            return []
        self.last_status, self.last_trace = record["status"], record["trace"]
        return [RetrievedEvidence(Evidence(**item["evidence"]), float(item["score"])) for item in record["results"]][:top_k]


def append_snapshot(path: Path, claim_id: str, recorder: RecordingWeb) -> None:
    record = {"claim_id": claim_id, "claim": recorder.last_claim, "status": recorder.last_status,
              "trace": recorder.last_trace,
              "results": [{"evidence": asdict(item.evidence), "score": item.score} for item in recorder.last_results]}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def drop_overlapping_articles(frame, other_urls: list[str]):
    """Bỏ (và in ra) claim có link bài gốc trùng bài trong phiếu khác."""
    if "source_url" not in frame or not other_urls:
        return frame
    overlap = frame.source_url.map(lambda u: bool(str(u or "")) and any(same_article(str(u), o) for o in other_urls))
    for row in frame[overlap].itertuples():
        print(f"Bỏ {row.claim_id}: bài gốc trùng phiếu khác ({row.source_url})")
    return frame[~overlap]


def load_snapshot(path: Path) -> dict[str, dict]:
    """claim → bản ghi; claim chạy nhiều lần thì lấy lần sau cùng."""
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[record["claim"]] = record
    return records


def compact_assessed(assessed: list[dict]) -> list[dict]:
    keys = ("url", "relevance", "status", "verifier_probabilities", "matched_details", "conflicting_details",
            "missing_details")
    return [{**{k: a.get(k) for k in keys}, "content": a.get("content", "")} for a in assessed]


def credit_shortfall(n_claims: int, requests_per_claim: int, budget: int, used_local: int, used_provider: int) -> int:
    """Số lượt có thể thiếu nếu chạy hết: mỗi claim tối đa requests_per_claim × 2 (run_with_retry thử lại một lần)."""
    worst_case = n_claims * requests_per_claim * 2
    return max(0, worst_case - (budget - max(used_local, used_provider)))


def credits_used(web_config: dict, api_key: str) -> tuple[int, int]:
    """(sổ máy tháng này, Tavily báo) cho key đang dùng. Tavily cập nhật trễ nên chỉ là chặn thêm."""
    from datetime import datetime, timezone
    from urllib.request import Request, urlopen

    from src.web_retriever import key_fingerprint

    local = 0
    try:
        book = json.loads((ROOT / web_config["cache"]["directory"] / "usage.json").read_text(encoding="utf-8"))
        state = book.get("accounts", {}).get(key_fingerprint(api_key), {})
        if state.get("month") == datetime.now(timezone.utc).strftime("%Y-%m"):
            local = int(state.get("requests", 0))
    except (FileNotFoundError, ValueError):
        pass
    provider = 0
    try:
        request = Request("https://api.tavily.com/usage", headers={"Authorization": f"Bearer {api_key}"})
        with urlopen(request, timeout=15) as response:
            provider = int(json.load(response).get("key", {}).get("usage") or 0)
    except Exception as error:  # không đọc được thì vẫn còn sổ máy chặn
        print(f"Không đọc được lượt dùng từ Tavily ({type(error).__name__}); chỉ dựa vào sổ trên máy.")
    return local, provider


def run_with_retry(pipeline, claim: str, max_waits: int = 12) -> tuple[dict, str | None]:
    """Chạm giới hạn request/phút → đợi rồi chạy lại; lỗi web tạm thời → thử lại một lần."""
    retried = False
    for _ in range(max_waits + 2):
        output = pipeline.run_json(claim)
        status = output["retrieval"].get("web_status")
        if status == "rate_limited":
            time.sleep(15)
            continue
        if status in WEB_RETRYABLE_STATUSES and not retried:
            retried = True
            time.sleep(5)
            continue
        return output, status
    return output, status


def summarise(rows: list[dict]) -> dict:
    by_group: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_group[row["group"]]["n"] += 1
        by_group[row["group"]]["correct"] += row["expected"] == row["predicted"]
    per_label = {}
    for label in SOURCE_LABELS:
        tp = sum(r["expected"] == label and r["predicted"] == label for r in rows)
        fp = sum(r["expected"] != label and r["predicted"] == label for r in rows)
        fn = sum(r["expected"] == label and r["predicted"] != label for r in rows)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        per_label[label] = {"precision": round(p, 4), "recall": round(r, 4),
                            "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}
    with_url = [r for r in rows if r["expected"] == "SOURCE_FOUND" and r["predicted"] == "SOURCE_FOUND"]
    not_found = [r for r in rows if r["group"] in ("fabricated", "perturbed")]
    return {
        "n": len(rows),
        "accuracy": round(sum(r["expected"] == r["predicted"] for r in rows) / max(1, len(rows)), 4),
        "macro_f1": round(sum(v["f1"] for v in per_label.values()) / len(per_label), 4),
        "per_label": per_label,
        "per_group_accuracy": {g: round(c["correct"] / c["n"], 4) for g, c in by_group.items()},
        # Báo nhầm "có nguồn": tin bịa / tin bị sửa mà hệ thống nói SOURCE_FOUND.
        "false_found_rate": round(sum(r["predicted"] == "SOURCE_FOUND" for r in not_found) / max(1, len(not_found)), 4),
        "citation_hits_expected_url": round(sum(r["cites_expected_url"] for r in with_url) / max(1, len(with_url)), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", type=Path, help="phiếu .xlsx (PHIEU_GAN_NHAN_NGUON_V1.xlsx) hoặc .csv")
    parser.add_argument("--no-web", action="store_true", help="chỉ kho cục bộ (để so sánh)")
    parser.add_argument("--no-verifier", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--groups", default="", help="chỉ chạy các nhóm này, vd. recent_real,paraphrase")
    parser.add_argument("--snapshot", type=Path, default=ROOT / ".cache/realworld_web_snapshot.jsonl",
                        help="nơi ghi kết quả web của từng claim khi chạy thật (.cache/ không commit)")
    parser.add_argument("--exclude-articles", type=Path, default=None,
                        help="bỏ claim có link bài gốc trùng bài trong phiếu này (vd. phiếu V1) – tránh rò rỉ dev/test")
    parser.add_argument("--skip-recorded", action="store_true",
                        help="web thật: bỏ claim đã có trong --snapshot (chạy nối tiếp, không tốn lượt lần nữa)")
    parser.add_argument("--limit", type=int, default=0, help="chỉ chạy N claim đầu (sau các bộ lọc)")
    parser.add_argument("--replay", type=Path, default=None,
                        help="chấm lại từ bản ghi web, không gọi Tavily (claim chưa ghi → không có web)")
    args = parser.parse_args()

    config = load_config()
    allowed_hosts = {str(item["host"]).lower() for item in config["web_retrieval"]["source_policy"]["allowlist"]}
    frame, skipped = load_labeled_claims(args.csv, allowed_hosts)
    for message in skipped:
        print(f"Bỏ qua {message}")
    if frame.empty:
        raise SystemExit("Không có claim hợp lệ nào (cột check phải là OK).")
    if not frame.expected_label.isin(SOURCE_LABELS).all():
        raise SystemExit(f"expected_label phải thuộc {SOURCE_LABELS}")
    if args.groups:
        frame = frame[frame.group.isin(args.groups.split(","))]
    if args.exclude_articles is not None:
        other, _ = load_labeled_claims(args.exclude_articles, allowed_hosts)
        frame = drop_overlapping_articles(frame, [str(u) for u in other.get("source_url", []) if str(u or "")])
    if args.skip_recorded and args.replay is None and args.snapshot.exists():
        recorded = load_snapshot(args.snapshot)
        before = len(frame)
        frame = frame[~frame.claim.astype(str).isin(recorded)]
        print(f"Bỏ {before - len(frame)} claim đã có trong {args.snapshot}.")
    if args.limit > 0:
        frame = frame.head(args.limit)
    print(f"{len(frame)} claim hợp lệ, bỏ qua {len(skipped)} dòng.")
    load_dotenv()
    live_web = not args.no_web and args.replay is None
    if live_web and not os.environ.get(load_config()["web_retrieval"]["provider"]["api_key_env"]):
        raise SystemExit("Chưa đặt TAVILY_API_KEY; dùng --no-web nếu chỉ muốn đo kho cục bộ.")
    if live_web:
        web_config = config["web_retrieval"]
        limits = web_config["limits"]
        budget, per_claim = int(limits["monthly_credit_budget"]), int(limits["requests_per_claim"])
        used_local, used_provider = credits_used(web_config, os.environ[web_config["provider"]["api_key_env"]])
        shortfall = credit_shortfall(len(frame), per_claim, budget, used_local, used_provider)
        print(f"Credit: đã dùng {max(used_local, used_provider)}/{budget}; lần này tối đa {len(frame) * per_claim * 2}.")
        if shortfall:
            raise SystemExit(f"Có thể vượt hạn mức {budget} credit (thiếu tới {shortfall}). Chạy ít claim hơn "
                             "(--groups) hoặc dùng --replay để chấm lại từ bản ghi.")

    pipeline = build_pipeline(use_web=live_web, use_verifier=not args.no_verifier)
    recorder = None
    if args.replay is not None:
        replay = ReplayWeb(load_snapshot(args.replay))
        print(f"Phát lại web từ {args.replay} ({len(replay.snapshot)} claim đã ghi).")
        pipeline.retriever = FusedRetriever([pipeline.retriever, replay], [1.0, float(config["web"].get("weight", 1.0))],
                                            candidates_per_retriever=pipeline.candidate_k)
    elif live_web:
        fused = pipeline.retriever
        index = next(i for i, r in enumerate(fused.retrievers) if is_web_retriever(r))
        recorder = fused.retrievers[index] = RecordingWeb(fused.retrievers[index])
    web = web_retriever_of(pipeline)
    threshold = float(pipeline.thresholds.relevance)
    rows = []
    for record in frame.itertuples():
        output, status = run_with_retry(pipeline, str(record.claim))
        if status == "budget_exhausted":
            print("Hết hạn mức web của tháng – dừng sớm, chỉ chấm các claim đã chạy.")
            break
        if recorder is not None:
            append_snapshot(args.snapshot, str(record.claim_id), recorder)
        cited = [c["url"] for c in output["citations"]]
        source_url = str(getattr(record, "source_url", "") or "")
        assessed = output["retrieval"]["assessed"]
        trace = getattr(web, "last_trace", None) if web is not None else None
        row = {
            "claim_id": record.claim_id, "group": record.group, "claim": str(record.claim),
            "expected": record.expected_label, "source_url": source_url,
            "predicted": output["verdict"]["label"], "confidence": output["verdict"]["confidence"],
            "cited_urls": cited, "cites_expected_url": bool(source_url) and any(same_article(source_url, u) for u in cited),
            "independent_sources": output["verdict"]["independent_sources"], "web_status": status,
            # Chi tiết để phân tích lỗi mà không tốn lại lượt Tavily.
            "best_relevance": max((a["relevance"] for a in assessed), default=None),
            "assessed": compact_assessed(assessed),
            "web_trace": trace,
            "last_errors": list(getattr(pipeline.retriever, "last_errors", [])),
        }
        if source_url:
            row["source_diagnosis"] = diagnose_source(source_url, trace, assessed, threshold)
        if row["expected"] == "SOURCE_FOUND" and row["predicted"] != "SOURCE_FOUND":
            row["miss_stage"] = ("no_web" if web is None
                                 else miss_stage(source_url, status, row.get("source_diagnosis", {}), threshold))
        rows.append(row)
        web_note = "" if status in (None, *REACHED) else f"  [web: {status}]"
        stage_note = f"  ({row['miss_stage']})" if "miss_stage" in row else ""
        print(f"{record.claim_id}: {record.expected_label} → {output['verdict']['label']}{web_note}{stage_note}",
              flush=True)

    report = {"web": not args.no_web, "web_replay": str(args.replay) if args.replay else None,
              "groups": args.groups or "all", "verifier": not args.no_verifier, **summarise(rows),
              "web_status_counts": dict(Counter(str(r["web_status"]) for r in rows)),
              # Tin thật bị trượt: trượt ở tầng nào (tìm kiếm / tải trang / ngưỡng / facet / verifier).
              "miss_stage_counts": dict(Counter(r["miss_stage"] for r in rows if "miss_stage" in r))}
    if not args.no_web:
        # Chỉ các claim tra web thành công: tách lỗi mạng/hạn mức khỏi lỗi của mô hình.
        reached = [r for r in rows if r["web_status"] in REACHED]
        report["web_reached"] = summarise(reached)
    mode = "local" if args.no_web else ("replay" if args.replay else "web")
    output = args.output or ROOT / f"outputs/metrics/source_attribution_realworld_{mode}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"report": report, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
