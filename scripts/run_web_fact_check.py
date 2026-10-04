"""Chạy kiểm chứng end-to-end CÓ web retrieval cho một claim (CLI thủ công).

Luồng: claim -> [BM25 local + Tavily web qua allowlist] --RRF fusion--> top-k
-> PhoBERT (verifier đã khóa trong config.yaml) -> verdict + citation có nguồn.

    # 1. Đặt API key (PowerShell), xin tại https://www.tavily.com (gói free 1.000 credit/tháng)
    $env:TAVILY_API_KEY = "tvly-xxxxxxxx"

    # 2. Chạy
    py -3.13 scripts/run_web_fact_check.py --claim "Giá xăng tăng từ chiều nay"

    # Chỉ local (không gọi web) để đối chiếu:
    py -3.13 scripts/run_web_fact_check.py --claim "..." --local-only

Nếu thiếu API key hoặc web lỗi, hệ thống tự lùi về local (fail_to: local_only) và
in cảnh báo — vẫn ra verdict, chỉ không có bằng chứng web.
"""

from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Windows may default redirected stdout/stderr to a legacy code page.  The CLI
# reports Vietnamese claim/evidence text, so keep logs usable in terminals and
# redirected acceptance runs alike.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(ROOT / ".cache/huggingface"))


def load_dotenv(path: Path) -> None:
    """Nạp KEY=VALUE từ .env vào os.environ (không ghi đè biến đã có).

    Dự án không dùng python-dotenv; hàm này đọc .env thủ công để key đặt trong
    file được nhận mà không cần set env tay. Bỏ qua dòng trống và dòng bắt đầu #.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


load_dotenv(ROOT / ".env")

from src.fusion_retriever import FusionRetriever
from src.fact_checker import RuleBasedFactChecker
from src.io_utils import load_evidence_jsonl
from src.phobert_fact_checker import PhoBERTFactChecker
from src.pipeline import FactCheckingPipeline
from src.query_enrichment import TimeAwareRetriever
from src.retriever import BM25Retriever
from src.reranked_retriever import MetadataRerankedRetriever
from src.temporal_gate import TemporalGateRetriever
from src.topical_rerank import TopicalRerankRetriever
from src.verdict_guard import GuardedVerifier
from src.web_retriever import WebRetriever


def load_web_retriever() -> tuple[WebRetriever | None, str]:
    """Nạp WebRetriever từ configs/web_retrieval.yaml, bật enabled tại runtime."""
    config_path = ROOT / "configs" / "web_retrieval.yaml"
    config = deepcopy(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    config["enabled"] = True
    config["cache"] = dict(config["cache"])
    config["cache"]["directory"] = str(ROOT / ".cache" / "web_retrieval")
    key_env = config["provider"]["api_key_env"]
    if not os.environ.get(key_env):
        return None, f"Thiếu biến môi trường {key_env}; chạy local-only."
    return WebRetriever(config), "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", required=True, help="Phát biểu cần kiểm chứng")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/config.yaml")
    parser.add_argument("--top-k", type=int, default=5, help="Số bằng chứng đưa vào verifier và hiển thị")
    parser.add_argument("--candidate-k", type=int, default=20, help="Số ứng viên mỗi nguồn (local/web) lấy trước khi trộn RRF")
    parser.add_argument("--local-only", action="store_true", help="Không gọi web")
    parser.add_argument("--as-of", help="Ngày tham chiếu YYYY-MM-DD cho claim thời sự (mặc định: hôm nay)")
    parser.add_argument("--no-time-enrich", action="store_true", help="Tắt tự động chèn ngày vào truy vấn web")
    parser.add_argument("--local-plain", action="store_true", help="Dùng BM25 thuần cho local thay vì rerank W3-08")
    parser.add_argument("--recency-today", type=int, default=10,
                        help="Cửa sổ (ngày) cho claim theo NGÀY (hôm nay/chiều nay): mặc định 10")
    parser.add_argument("--recency-current", type=int, default=365,
                        help="Cửa sổ (ngày) cho claim HIỆN TẠI (hiện nay/đương nhiệm): mặc định 365")
    parser.add_argument("--recency-days", type=int, default=None,
                        help="Ép một cửa sổ chung cho cả hai loại (ghi đè --recency-today/-current)")
    parser.add_argument("--no-temporal-gate", action="store_true",
                        help="Tắt neo thời gian (không loại bằng chứng cũ cho claim thời sự)")
    parser.add_argument("--keep-undated", action="store_true",
                        help="Giữ cả bằng chứng không rõ ngày đăng khi neo thời gian (mặc định: loại)")
    parser.add_argument("--no-topical-rerank", action="store_true",
                        help="Tắt gộp theo URL + xếp theo độ khớp chủ đề (ưu tiên bài giá bán lẻ)")
    parser.add_argument("--no-guard", action="store_true",
                        help="Tắt guard hạ SUPPORTED/REFUTED xuống NEI khi bằng chứng không vững")
    parser.add_argument("--require-phobert", action="store_true",
                        help="Không fallback khi Windows chặn Torch; dừng với lỗi để chẩn đoán runtime PhoBERT")
    args = parser.parse_args()

    from datetime import date
    as_of = date.fromisoformat(args.as_of) if args.as_of else None

    config = yaml.safe_load((args.config if args.config.is_absolute() else ROOT / args.config).read_text(encoding="utf-8"))
    v = config["verification"]

    if args.local_plain:
        local = BM25Retriever(load_evidence_jsonl(ROOT / config["paths"]["evidence_path"]))
    else:
        # Mặc định: BM25 trên corpus v2 -> lọc nguồn/thời gian + rerank authority (W3-08)
        rr = yaml.safe_load((ROOT / "configs/reranked_retrieval.yaml").read_text(encoding="utf-8"))
        local = MetadataRerankedRetriever(
            BM25Retriever(load_evidence_jsonl(ROOT / rr["corpus"])), rr,
        )

    window_today = args.recency_days if args.recency_days is not None else args.recency_today
    window_current = args.recency_days if args.recency_days is not None else args.recency_current

    web = None
    if not args.local_only:
        web, status = load_web_retriever()
        if web is None:
            print(f"[web] {status}", file=sys.stderr)

    web_layer = None
    if web is not None:
        web_layer = TimeAwareRetriever(
            web, as_of=as_of, enabled=not args.no_time_enrich,
            window_today=window_today, window_current=window_current,
        )

    fusion = FusionRetriever(local, web_layer or web, candidate_k=args.candidate_k)
    # Neo thời gian: với claim thời sự, loại bằng chứng cũ hơn cửa sổ cho phép;
    # hết bằng chứng mới -> pipeline trả NEI thay vì SUPPORTED bằng bài cũ.
    gate = TemporalGateRetriever(
        fusion, as_of=as_of, window_today=window_today, window_current=window_current,
        candidate_k=args.candidate_k, drop_unknown_dates=not args.keep_undated,
        enabled=not args.no_temporal_gate,
    )
    # Gộp mỗi URL một đoạn khớp nhất + ưu tiên bài đúng chủ đề (giá bán lẻ trong nước
    # hơn giá dầu thế giới). Chạy SAU neo thời gian để chỉ xếp lại bằng chứng đủ mới.
    retriever = TopicalRerankRetriever(
        gate, candidate_k=args.candidate_k, enabled=not args.no_topical_rerank,
    )
    fallback_reason = None
    try:
        checker = PhoBERTFactChecker(
            str(ROOT / v["model_path"]), str(ROOT / v["vncorenlp_dir"]),
            int(v["max_length"]), float(v.get("temperature", 1.0)),
            float(v.get("decisive_min_confidence", 0.0)), float(v.get("retrieval_rank_bias", 0.0)),
            aggregation_model_path=str(ROOT / v["aggregation_model_path"]) if v.get("aggregation_model_path") else None,
        )
    except RuntimeError as error:
        if args.require_phobert or "Application Control policy has blocked" not in str(error):
            raise
        fallback_reason = str(error)
        checker = RuleBasedFactChecker(
            support_threshold=float(v.get("support_threshold", 0.45)),
            refute_markers=v.get("refute_markers"),
        )
    # Guard an toàn: hạ SUPPORTED/REFUTED xuống NEI khi bằng chứng trích dẫn lạc chủ
    # đề hoặc ngược chiều (chống false positive). Bọc trong suốt quanh verifier.
    guard = GuardedVerifier(checker, enabled=not args.no_guard)
    pipeline = FactCheckingPipeline(retriever=retriever, checker=guard, top_k=args.top_k)

    result, retrieved = pipeline.run(args.claim)
    if fallback_reason:
        print(
            "[runtime] PhoBERT bị Windows Application Control chặn; đang dùng rule-based fallback. "
            "Kết quả chỉ dùng để kiểm tra retrieval/luồng CLI, không dùng để đánh giá chất lượng mô hình.",
            file=sys.stderr,
        )
    cited = {e for e in result.evidence_ids}
    if web_layer is not None and web_layer.last_enriched_query:
        print(f"[web] Claim thời sự — truy vấn web đã chèn ngày: {web_layer.last_enriched_query!r}", file=sys.stderr)
    if gate.last_applied:
        cls_label = "theo-ngày" if gate.last_class == "today" else "hiện-tại"
        print(
            f"[gate] Claim thời sự ({cls_label}) — neo thời gian: giữ bằng chứng từ {gate.last_cutoff}"
            f" trở đi (cửa sổ {gate.last_window} ngày). Giữ {gate.last_kept};"
            f" loại {gate.last_dropped} (quá cũ: {gate.last_dropped_stale}, không rõ ngày: {gate.last_dropped_undated}).",
            file=sys.stderr,
        )
        if gate.last_dropped_items:
            print("[gate] Chi tiết bằng chứng bị loại (lý do | nguồn | ngày | URL):", file=sys.stderr)
            for reason, item in gate.last_dropped_items:
                e = item.evidence
                origin = "web" if str(e.passage_id).startswith("web-") else "local"
                when = e.published_at[:10] if e.published_at else "không rõ"
                print(f"   - [{reason}] ({origin}) {e.source} | {when} | {e.url}", file=sys.stderr)
        if gate.last_kept == 0:
            print(
                "[gate] Không còn bằng chứng đủ mới. Nhìn danh sách trên: nếu phần WEB "
                "đều 'không rõ' thì nguồn không lộ ngày (cần vá cách đọc ngày); nếu web có "
                "ngày nhưng đều cũ thì đúng là chưa có tin mới (NEI hợp lệ); có thể nới "
                "cửa sổ bằng --recency-current/--recency-today.",
                file=sys.stderr,
            )
    if guard.last_downgraded:
        print(f"[guard] {guard.last_reason} — đã hạ verdict xuống NEI.", file=sys.stderr)

    print("\n" + "=" * 70)
    print(f"CLAIM: {args.claim}")
    print(f"VERDICT: {result.label}" + (f"  (điểm mô hình {result.confidence:.3f})" if result.label != "NOT_ENOUGH_INFO" else ""))
    print(f"Giải thích: {result.explanation}")
    if result.label == "NOT_ENOUGH_INFO" and gate.last_applied and gate.last_dropped and not retrieved:
        print("  → Không còn bằng chứng đủ mới cho claim thời sự này (bài tìm được quá cũ so với ngày tham chiếu).")
    print("-" * 70)
    print("Bằng chứng truy xuất (★ = được trích dẫn):")
    for rank, item in enumerate(retrieved, start=1):
        e = item.evidence
        origin = "web" if str(e.passage_id).startswith("web-") else "local"
        star = "★" if e.passage_id in cited else " "
        when = f"  [đăng {e.published_at[:10]}]" if e.published_at else "  [ngày đăng: không rõ]"
        print(f" {star} [{rank}] ({origin}) {e.source}{when} — {e.url}")
        print(f"      {e.content[:160]}")
    if not any(e.evidence.passage_id in cited for e in retrieved):
        print("   (không trích dẫn — NEI hoặc không đủ bằng chứng)")
    print("=" * 70)


if __name__ == "__main__":
    main()
