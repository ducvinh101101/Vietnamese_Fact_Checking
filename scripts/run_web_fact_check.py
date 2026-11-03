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
from pathlib import Path


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


from src.system_builder import SystemOptions, build_system, load_config, load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", required=True, help="Phát biểu cần kiểm chứng")
    parser.add_argument("--source-url", action="append", default=[],
                        help="URL nguồn để đọc trực tiếp; lặp lại tối đa 3 lần")
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
    window_today = args.recency_days if args.recency_days is not None else args.recency_today
    window_current = args.recency_days if args.recency_days is not None else args.recency_current

    # Dựng qua src/system_builder.py — CÙNG cách dựng với giao diện Streamlit (chế độ hybrid):
    # local W3-08 + web -> RRF -> neo thời gian -> gộp URL/xếp chủ đề -> verifier theo config
    # (RT-V2, evidence_view, minimal_pair) + guard cho nhánh thời sự.
    system = build_system(SystemOptions(
        mode="hybrid", use_web=not args.local_only, as_of=as_of, top_k=args.top_k,
        candidate_k=args.candidate_k, window_today=window_today, window_current=window_current,
        time_enrich=not args.no_time_enrich, temporal_gate=not args.no_temporal_gate,
        keep_undated=args.keep_undated, topical_rerank=not args.no_topical_rerank,
        guard=not args.no_guard, local_plain=args.local_plain, require_phobert=args.require_phobert,
    ), config=load_config(ROOT, args.config))
    pipeline, gate, guard, web_layer = system.pipeline, system.gate, system.guard, system.web_layer
    fallback_reason = system.fallback_reason
    if not args.local_only and not system.settings.get("web"):
        print(f"[web] {system.web_status}", file=sys.stderr)
    if args.source_url:
        if web_layer is None:
            parser.error("--source-url cần bật nhánh web")
        if len(args.source_url) > 3:
            parser.error("Chỉ nhận tối đa 3 --source-url")
        web_layer.source_urls = tuple(args.source_url)
    try:
        result, retrieved = pipeline.run(args.claim)
    finally:
        if web_layer is not None:
            web_layer.source_urls = ()
    if fallback_reason:
        print(
            "[runtime] PhoBERT bị Windows Application Control chặn; đang dùng rule-based fallback. "
            "Kết quả chỉ dùng để kiểm tra retrieval/luồng CLI, không dùng để đánh giá chất lượng mô hình.",
            file=sys.stderr,
        )
    cited = {e for e in result.evidence_ids}
    if web_layer is not None and web_layer.last_enriched_query:
        print(f"[web] Claim thời sự — truy vấn web đã chèn ngày: {web_layer.last_enriched_query!r}", file=sys.stderr)
        for attempt in getattr(web_layer.inner, "last_attempts", []):
            print(f"[web] {attempt['stage']}: {attempt['status']} ({attempt['count']} passages)", file=sys.stderr)
    if gate.last_applied:
        cls_label = "theo-ngày" if gate.last_class == "today" else "hiện-tại"
        print(
            f"[gate] Claim thời sự ({cls_label}) — neo thời gian: giữ bằng chứng từ {gate.last_cutoff}"
            f" trở đi (cửa sổ {gate.last_window} ngày). Giữ {gate.last_kept};"
            f" loại {gate.last_dropped} (quá cũ: {gate.last_dropped_stale}, không rõ ngày: {gate.last_dropped_undated},"
            f" sau ngày tham chiếu: {gate.last_dropped_future}).",
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
    if system.fusion is not None and system.fusion.last_web_error:
        print(f"[web] Nhánh web lỗi, đã lùi về local: {system.fusion.last_web_error}", file=sys.stderr)
    if web_layer is not None:
        for row in getattr(web_layer.inner, "last_candidates", []):
            if row['status'] == 'rejected':
                print(f"[web] Loại {row['url']}: {row.get('reason', 'không rõ')}", file=sys.stderr)
        if getattr(web_layer.inner, "last_error", None):
            print(f"[web] {web_layer.inner.last_error}", file=sys.stderr)
    if system.minimal_pair is not None and system.minimal_pair.last_reason:
        print(f"[minimal-pair] Đã điều chỉnh verdict: {system.minimal_pair.last_reason}", file=sys.stderr)
    if guard is not None and guard.last_downgraded:
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
        if e.published_at_source:
            when += f" [ngày từ {e.published_at_source}]"
        print(f" {star} [{rank}] ({origin}) {e.source}{when} — {e.url}")
        print(f"      {e.content[:160]}")
    if not any(e.evidence.passage_id in cited for e in retrieved):
        print("   (không trích dẫn — NEI hoặc không đủ bằng chứng)")
    print("=" * 70)


if __name__ == "__main__":
    main()
