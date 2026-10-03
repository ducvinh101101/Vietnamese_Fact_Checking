"""Golden test cho chuỗi RAG web -> xác minh.

Hai chế độ:

  # 1) Deterministic (mặc định): dựng sẵn bằng chứng từ YAML, không cần mạng/PhoBERT.
  #    Kiểm từng mắt xích: fusion -> neo thời gian -> gộp URL + rerank -> guard.
  py -3.13 scripts/run_golden_eval.py

  # 2) Live: bắn claim thật lên web (cần TAVILY_API_KEY) và kiểm TÍNH CHẤT dữ liệu
  #    web lấy về (có bài mới có ngày? đoạn top có khớp chủ đề? có bẫy 'trái chiều'?).
  py -3.13 scripts/run_golden_eval.py --live

Thoát mã != 0 nếu có case FAIL (dùng được trong CI).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fusion_retriever import FusionRetriever
from src.pipeline import FactCheckingPipeline
from src.schemas import Evidence, RetrievedEvidence, VerificationResult
from src.temporal_gate import TemporalGateRetriever
from src.topical_rerank import TopicalRerankRetriever, relevance
from src.verdict_guard import GuardedVerifier

GOLDEN_PATH = ROOT / "tests" / "golden" / "golden_web_cases.yaml"


# --- Stub cho chế độ deterministic -------------------------------------------

class _StubRetriever:
    """Trả danh sách bằng chứng cố định (mô phỏng local hoặc web)."""

    def __init__(self, items: list[RetrievedEvidence]) -> None:
        self.items = items

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        return self.items[:top_k]


class _ScriptedVerifier:
    """Verifier giả: trả nhãn cấu hình sẵn, trích dẫn đoạn hạng cao nhất (như PhoBERT
    thường bám đoạn top). Nếu không còn bằng chứng -> NEI."""

    def __init__(self, label: str) -> None:
        self.label = label

    def verify(self, claim: str, items: list[RetrievedEvidence]) -> VerificationResult:
        if not items or self.label == "NOT_ENOUGH_INFO":
            return VerificationResult("NOT_ENOUGH_INFO", 0.0, [], "scripted")
        return VerificationResult(self.label, 0.9, [items[0].evidence.passage_id], "scripted")


def _build_evidence(entries: list[dict], origin: str, start: int) -> list[RetrievedEvidence]:
    out: list[RetrievedEvidence] = []
    for i, e in enumerate(entries or []):
        idx = start + i
        pid = f"{'web' if origin == 'web' else 'local'}-{idx:03d}"
        out.append(RetrievedEvidence(
            Evidence(
                document_id=e["url"], passage_id=pid, content=e["content"],
                url=e["url"], source=e.get("source", "Nguồn"),
                published_at=e.get("published_at"),
            ),
            score=float(1000 - idx),  # giảm dần theo thứ tự liệt kê
        ))
    return out


def load_cases(path: Path = GOLDEN_PATH) -> tuple[dict, list[dict]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("defaults", {}), data["cases"]


def evaluate_case(case: dict, defaults: dict) -> dict:
    """Chạy một case qua TOÀN chuỗi và so với expect. Trả dict kết quả + danh sách lỗi."""
    as_of = date.fromisoformat(case.get("as_of", defaults.get("as_of", "2026-10-03")))
    w_today = int(defaults.get("recency_today", 10))
    w_current = int(defaults.get("recency_current", 365))

    local = _StubRetriever(_build_evidence(case.get("local", []), "local", 0))
    web = _StubRetriever(_build_evidence(case.get("web", []), "web", 500))

    fusion = FusionRetriever(local, web, candidate_k=20)
    gate = TemporalGateRetriever(fusion, as_of=as_of, window_today=w_today,
                                 window_current=w_current, candidate_k=20)
    retriever = TopicalRerankRetriever(gate, candidate_k=20)
    guard = GuardedVerifier(_ScriptedVerifier(case.get("verifier_says", "SUPPORTED")))
    pipeline = FactCheckingPipeline(retriever=retriever, checker=guard, top_k=5)

    result, retrieved = pipeline.run(case["claim"])

    cited_ids = set(result.evidence_ids)
    cited = [it.evidence for it in retrieved if it.evidence.passage_id in cited_ids]
    expect = case.get("expect", {})
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    if "label" in expect:
        check(result.label == expect["label"],
              f"label: cần {expect['label']}, được {result.label}")
    if "gate_class" in expect:
        want = None if expect["gate_class"] in (None, "none") else expect["gate_class"]
        check(gate.last_class == want, f"gate_class: cần {want}, được {gate.last_class}")
    if "gate_applied" in expect:
        check(gate.last_applied == expect["gate_applied"],
              f"gate_applied: cần {expect['gate_applied']}, được {gate.last_applied}")
    if "guard_downgraded" in expect:
        check(guard.last_downgraded == expect["guard_downgraded"],
              f"guard_downgraded: cần {expect['guard_downgraded']}, được {guard.last_downgraded}")
    if "retrieved_count" in expect:
        check(len(retrieved) == expect["retrieved_count"],
              f"retrieved_count: cần {expect['retrieved_count']}, được {len(retrieved)}")
    if "dropped_undated_min" in expect:
        check(gate.last_dropped_undated >= expect["dropped_undated_min"],
              f"dropped_undated: cần >= {expect['dropped_undated_min']}, được {gate.last_dropped_undated}")
    if "cited_content_contains" in expect:
        txt = " ".join(e.content for e in cited)
        check(expect["cited_content_contains"] in txt,
              f"cited_content: không chứa {expect['cited_content_contains']!r}")
    if "cited_url_contains" in expect:
        urls = " ".join(e.url for e in cited)
        check(expect["cited_url_contains"] in urls,
              f"cited_url: không chứa {expect['cited_url_contains']!r}")
    if "cited_origin" in expect:
        origins = {"web" if e.passage_id.startswith("web-") else "local" for e in cited}
        check(expect["cited_origin"] in origins or (not cited and expect["cited_origin"] == "none"),
              f"cited_origin: cần {expect['cited_origin']}, được {origins or 'none'}")

    return {"id": case["id"], "issue": case.get("issue", ""), "ok": not failures,
            "failures": failures, "label": result.label}


# --- Chế độ live: kiểm tính chất dữ liệu web thật ----------------------------

def run_live(claims: list[str], recency_today: int, recency_current: int) -> int:
    """Bắn claim thật lên web và kiểm TÍNH CHẤT bằng chứng lấy về (không gọi verifier)."""
    import os
    from copy import deepcopy
    from src.io_utils import load_evidence_jsonl
    from src.query_enrichment import TimeAwareRetriever, recency_class
    from src.reranked_retriever import MetadataRerankedRetriever
    from src.retriever import BM25Retriever
    from src.web_retriever import WebRetriever

    def _load_dotenv(path: Path) -> None:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, val = line.partition("=")
                os.environ.setdefault(k.strip(), val.strip().strip('"').strip("'"))

    _load_dotenv(ROOT / ".env")
    wcfg = deepcopy(yaml.safe_load((ROOT / "configs/web_retrieval.yaml").read_text(encoding="utf-8")))
    wcfg["enabled"] = True
    wcfg["cache"] = dict(wcfg["cache"]); wcfg["cache"]["directory"] = str(ROOT / ".cache/web_retrieval")
    if not os.environ.get(wcfg["provider"]["api_key_env"]):
        print("[live] Thiếu TAVILY_API_KEY — bỏ qua chế độ live.", file=sys.stderr)
        return 0
    web = WebRetriever(wcfg)

    rr = yaml.safe_load((ROOT / "configs/reranked_retrieval.yaml").read_text(encoding="utf-8"))
    local = MetadataRerankedRetriever(BM25Retriever(load_evidence_jsonl(ROOT / rr["corpus"])), rr)

    problems = 0
    for claim in claims:
        cls = recency_class(claim)
        web_layer = TimeAwareRetriever(web, enabled=True)
        fusion = FusionRetriever(local, web_layer, candidate_k=20)
        gate = TemporalGateRetriever(fusion, window_today=recency_today, window_current=recency_current, candidate_k=20)
        rerank = TopicalRerankRetriever(gate, candidate_k=20)
        kept = rerank.search(claim, top_k=5)

        web_kept = [k for k in kept if k.evidence.passage_id.startswith("web-")]
        top_rel = relevance(claim, kept[0].evidence.content) if kept else 0.0
        trap = any("trái chiều" in k.evidence.content.casefold() for k in kept[:1])

        print("\n" + "-" * 70)
        print(f"CLAIM: {claim}  (loại: {cls or 'phi thời sự'})")
        print(f"  giữ {len(kept)} bằng chứng ({len(web_kept)} web) | loại cũ {gate.last_dropped_stale}, "
              f"không ngày {gate.last_dropped_undated} | độ khớp đoạn top: {top_rel:.2f}")
        for i, k in enumerate(kept, 1):
            e = k.evidence
            when = e.published_at[:10] if e.published_at else "không rõ"
            print(f"   [{i}] {'web' if e.passage_id.startswith('web-') else 'local'} | {when} | {e.url}")
        # Cảnh báo tính chất xấu
        if cls is not None and not web_kept:
            print("  ⚠ KHÔNG có bằng chứng WEB mới — claim thời sự dễ ra NEI."); problems += 1
        if kept and top_rel <= 0:
            print("  ⚠ Đoạn top LẠC chủ đề (độ khớp <= 0) — nguy cơ verdict sai."); problems += 1
        if trap:
            print("  ⚠ Đoạn top nói 'trái chiều' — guard sẽ (và nên) hạ xuống NEI."); problems += 1
    print("\n" + "=" * 70)
    print(f"[live] Hoàn tất {len(claims)} claim, {problems} cảnh báo tính chất.")
    return 0  # live chỉ cảnh báo, không fail CI


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Kiểm tính chất dữ liệu web THẬT (cần TAVILY_API_KEY)")
    parser.add_argument("--claim", action="append", help="Claim cho chế độ live (lặp lại được)")
    args = parser.parse_args()

    defaults, cases = load_cases()

    if args.live:
        claims = args.claim or [
            "Giá xăng tăng từ chiều nay",
            "Tổng thống Mỹ hiện nay là Trump",
            "Tỷ giá USD hôm nay tăng mạnh",
        ]
        return run_live(claims, int(defaults.get("recency_today", 10)), int(defaults.get("recency_current", 365)))

    results = [evaluate_case(c, defaults) for c in cases]
    passed = sum(r["ok"] for r in results)
    print("=" * 70)
    print("GOLDEN TEST — chuỗi RAG web -> xác minh (deterministic)")
    print("=" * 70)
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"[{mark}] {r['id']:<28} {r['issue']}")
        for f in r["failures"]:
            print(f"        └─ {f}")
    print("-" * 70)
    print(f"{passed}/{len(results)} case PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
