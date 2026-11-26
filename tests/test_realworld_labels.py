import importlib.util
from pathlib import Path

import pytest

from src.realworld_labels import GOOGLE_CHECKED, DISAGREE, check_row, load_labeled_claims, url_host

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {"vov.vn", "vnexpress.net", "www.sggp.org.vn"}
CLAIM = "Từ ngày 1/7/2025, 34 tỉnh, thành trên cả nước vận hành chính quyền 2 cấp."


@pytest.mark.parametrize("row, expected", [
    ({"group": "recent_real", "claim": CLAIM, "source_url": "https://vov.vn/a.vov"}, "OK"),
    ({"group": "paraphrase", "claim": CLAIM, "source_url": "https://VNEXPRESS.net/a.html"}, "OK"),
    ({"group": "perturbed", "claim": CLAIM, "source_url": "https://www.sggp.org.vn/a", "changed_detail": "34 → 45"}, "OK"),
    ({"group": "fabricated", "claim": CLAIM, "google_checked": GOOGLE_CHECKED}, "OK"),
    ({"group": "", "claim": CLAIM}, "Chọn nhóm"),
    ({"group": "recent_real", "claim": "Ngắn quá", "source_url": "https://vov.vn/a"}, "Claim quá ngắn"),
    ({"group": "recent_real", "claim": CLAIM}, "Thiếu link nguồn"),
    ({"group": "recent_real", "claim": CLAIM, "source_url": "http://vov.vn/a"}, "Link phải bắt đầu bằng https://"),
    ({"group": "recent_real", "claim": CLAIM, "source_url": "https://vov.vn/a?utm=1"}, "Xóa phần ?... hoặc #... ở cuối link"),
    ({"group": "recent_real", "claim": CLAIM, "source_url": "https://www.facebook.com/1"}, "Trang không thuộc danh sách nguồn"),
    ({"group": "perturbed", "claim": CLAIM, "source_url": "https://vov.vn/a"}, "Ghi chi tiết đã sửa (vd. 34 → 45)"),
    ({"group": "fabricated", "claim": CLAIM, "google_checked": "Chưa tìm"}, "Chưa tìm Google"),
    ({"group": "recent_real", "claim": "  "}, ""),
])
def test_check_row(row, expected):
    assert check_row(row, HOSTS) == expected


def test_url_host_requires_https_and_lowercases():
    assert url_host("https://VOV.vn/a/b") == "vov.vn"
    assert url_host("http://vov.vn/a") == ""


def test_load_csv_keeps_given_labels(tmp_path):
    path = tmp_path / "claims.csv"
    path.write_text("claim_id,group,claim,expected_label,source_url\n"
                    f'a,recent_real,"{CLAIM}",SOURCE_FOUND,https://vov.vn/a\n'
                    "b,fabricated,Câu bịa đủ dài để kiểm tra,WRONG,\n", encoding="utf-8")
    frame, warnings = load_labeled_claims(path, HOSTS)
    assert frame.claim_id.tolist() == ["a"]
    assert warnings == ["b: expected_label sai"]


def test_generated_form_round_trip(tmp_path):
    """Phiếu tạo bằng script đọc lại được; nhãn suy ra từ nhóm; bỏ dòng lỗi, trùng và dòng không đồng ý."""
    from openpyxl import load_workbook

    spec = importlib.util.spec_from_file_location("form", ROOT / "scripts" / "create_realworld_labeling_form.py")
    form = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(form)
    path = tmp_path / "phieu.xlsx"
    import sys
    argv, sys.argv = sys.argv, ["x", "--output", str(path)]
    try:
        form.main()
    finally:
        sys.argv = argv

    wb = load_workbook(path)
    ws = wb[form.SHEET_NAME]
    col = {code: i + 1 for i, (code, *_rest) in enumerate(form.COLUMNS)}
    rows = [
        {"group": "recent_real", "claim": CLAIM, "source_url": "https://vov.vn/a.vov"},
        {"group": "fabricated", "claim": "Uống nước chanh ấm chữa khỏi ung thư gan.", "google_checked": GOOGLE_CHECKED},
        {"group": "perturbed", "claim": "Một tin bị sửa số nhưng quên ghi chi tiết.", "source_url": "https://vov.vn/b"},
        {"group": "paraphrase", "claim": "Kể từ tháng 7/2025 chính quyền 34 tỉnh hoạt động hai cấp.",
         "source_url": "https://vov.vn/a.vov", "reviewer_agrees": DISAGREE},
    ]
    for offset, values in enumerate(rows):
        for key, value in values.items():
            ws.cell(form.FIRST + offset, col[key], value)
    wb.save(path)

    hosts = {item["host"] for item in form.load_config()["web_retrieval"]["source_policy"]["allowlist"]}
    frame, warnings = load_labeled_claims(path, hosts)
    assert frame.claim_id.tolist() == ["rw001", "rw002"]
    assert frame.expected_label.tolist() == ["SOURCE_FOUND", "NO_SOURCE"]
    assert warnings == ["rw003: Ghi chi tiết đã sửa (vd. 34 → 45)", "rw004: người kiểm tra chéo không đồng ý"]
    with pytest.raises(SystemExit):
        form.main.__globals__["sys"].argv = ["x", "--output", str(path)]
        form.main()


def test_dev_form_prefix_and_targets(tmp_path):
    """Phiếu dev: mã dv…, số dòng = tổng chỉ tiêu, nhóm sai bị từ chối."""
    import sys
    from openpyxl import load_workbook

    spec = importlib.util.spec_from_file_location("form_dev", ROOT / "scripts" / "create_realworld_labeling_form.py")
    form = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(form)
    path = tmp_path / "dev.xlsx"
    argv, sys.argv = sys.argv, ["x", "--output", str(path), "--prefix", "dv",
                                "--targets", "recent_real=3,paraphrase=2,fabricated=1,perturbed=1"]
    try:
        form.main()
    finally:
        sys.argv = argv
    ws = load_workbook(path)[form.SHEET_NAME]
    assert ws.cell(form.FIRST, 1).value == "dv001"
    assert ws.cell(form.FIRST + 6, 1).value == "dv007"
    assert ws.cell(form.FIRST + 7, 1).value is None
    with pytest.raises(SystemExit):
        form.parse_targets("recent_real=3,bogus=2")


def test_drop_overlapping_articles():
    import pandas as pd

    module = _eval_module()
    frame = pd.DataFrame({"claim_id": ["dv001", "dv002", "dv003"], "claim": ["a", "b", "c"],
                          "source_url": ["https://vnexpress.net/x-1.html", "https://vov.vn/y-2.vov", ""]})
    kept = module.drop_overlapping_articles(frame, ["https://vnexpress.net/x-1.html"])
    assert kept.claim_id.tolist() == ["dv002", "dv003"]


def _eval_module():
    spec = importlib.util.spec_from_file_location("rw_eval", ROOT / "scripts" / "evaluate_source_attribution_realworld.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_article_ignores_host_change():
    module = _eval_module()
    assert module.same_article("https://nld.com.vn/nld/bai-abc-1962.htm", "https://tuoitre.vn/nld/bai-abc-1962.htm")
    assert not module.same_article("https://vnexpress.net/a-1.html", "https://vnexpress.net/b-2.html")


SRC = "https://vnexpress.net/bai-goc-123.html"


def _trace(*pages, search=(SRC,)):
    return {"queries": ["q"], "provider_error": None,
            "search_results": [{"query_index": 0, "rank": i, "url": u, "title": None, "score": None}
                               for i, u in enumerate(search)],
            "pages": list(pages)}


def _assessed(relevance, status, conflicting=(), url=SRC):
    return {"url": url, "relevance": relevance, "status": status, "conflicting_details": list(conflicting)}


@pytest.mark.parametrize("trace, assessed, web_status, stage", [
    (_trace(search=("https://vnexpress.net/khac-9.html",)), [], "ok", "search_miss"),
    (_trace({"url": SRC, "outcome": "fetch_failed", "error": "SSL"}), [], "ok", "fetch_failed"),
    (_trace({"url": SRC, "outcome": "not_read"}), [], "ok", "not_read"),
    (_trace({"url": SRC, "outcome": "used", "max_relevance": 0.9}), [], "ok", "outranked"),
    (_trace({"url": SRC, "outcome": "used"}), [_assessed(0.68, "unrelated")], "ok", "below_threshold"),
    (_trace({"url": SRC, "outcome": "used"}), [_assessed(0.9, "conflicts", ["số 162.400"])], "ok", "facet_conflict"),
    (_trace({"url": SRC, "outcome": "used"}), [_assessed(0.9, "related")], "ok", "verifier"),
    (_trace(), [], "pages_unreachable", "web_error"),
])
def test_diagnose_source_assigns_failure_stage(trace, assessed, web_status, stage):
    module = _eval_module()
    diagnosis = module.diagnose_source(SRC, trace, assessed, relevance_threshold=0.7)
    assert module.miss_stage(SRC, web_status, diagnosis, 0.7) == stage


def test_diagnose_source_reports_best_passage_of_expected_article():
    module = _eval_module()
    trace = _trace({"url": "https://vnexpress.net/bai-goc-123.html", "final_url": SRC, "outcome": "used",
                    "max_relevance": 0.55}, search=("https://x.vn/a", SRC))
    assessed = [_assessed(0.9, "supports", url="https://x.vn/a"), _assessed(0.4, "unrelated"),
                _assessed(0.6, "related", ["thời gian 21/11"])]
    d = module.diagnose_source(SRC, trace, assessed, relevance_threshold=0.7)
    assert d["in_search_results"] and d["search_rank"] == [0, 1]
    assert d["page_outcome"] == "used" and d["web_max_relevance"] == 0.55
    assert d["assessed_max_relevance"] == 0.6 and d["assessed_status"] == "related"
    assert d["conflicting_details"] == ["thời gian 21/11"]
    assert module.miss_stage("", "ok", d, 0.7) == "no_source_url"


def test_main_saves_per_claim_details_and_miss_stages(tmp_path, monkeypatch):
    import json
    import sys
    from types import SimpleNamespace

    module = _eval_module()
    path = tmp_path / "claims.csv"
    path.write_text("claim_id,group,claim,expected_label,source_url\n"
                    f'a,recent_real,"{CLAIM}",SOURCE_FOUND,{SRC}\n', encoding="utf-8")

    class WebRetriever:
        last_status = "ok"
        last_trace = _trace({"url": SRC, "outcome": "used", "max_relevance": 0.6})

    class Pipeline:
        retriever = SimpleNamespace(retrievers=[object(), WebRetriever()], last_errors=[])
        thresholds = SimpleNamespace(relevance=0.7)

        def run_json(self, claim):
            return {"verdict": {"label": "NO_SOURCE", "confidence": 0.3, "independent_sources": []},
                    "citations": [],
                    "retrieval": {"web_status": "ok", "assessed": [
                        {**_assessed(0.68, "unrelated"), "content": "x" * 900, "verifier_probabilities": None}]}}

    monkeypatch.setattr(module, "build_pipeline", lambda *_, **__: Pipeline())
    monkeypatch.setattr(module, "load_config", lambda: {"web_retrieval": {
        "source_policy": {"allowlist": [{"host": "vov.vn"}, {"host": "vnexpress.net"}]},
        "provider": {"api_key_env": "X_KEY"},
        "limits": {"monthly_credit_budget": 900, "requests_per_claim": 2}}})
    monkeypatch.setattr(module, "credits_used", lambda *_: (0, 0))  # không gọi Tavily trong test
    monkeypatch.setattr(module, "load_dotenv", lambda: None)
    monkeypatch.setenv("X_KEY", "k")
    out = tmp_path / "out.json"
    snap = tmp_path / "snap.jsonl"
    monkeypatch.setattr(sys, "argv", ["x", str(path), "--output", str(out), "--snapshot", str(snap)])
    module.main()
    assert json.loads(snap.read_text(encoding="utf-8"))["claim_id"] == "a"
    saved = json.loads(out.read_text(encoding="utf-8"))
    row = saved["rows"][0]
    assert row["miss_stage"] == "below_threshold" and saved["report"]["miss_stage_counts"] == {"below_threshold": 1}
    assert row["source_diagnosis"]["assessed_max_relevance"] == 0.68
    assert row["web_trace"]["queries"] == ["q"] and row["best_relevance"] == 0.68
    assert row["assessed"][0]["content"] == "x" * 900 and row["last_errors"] == []


def test_web_snapshot_round_trip_replays_without_network(tmp_path):
    """Bản ghi web của lần chạy thật → chấm lại (đổi facet/ngưỡng) không tốn lượt Tavily."""
    from src.schemas import Evidence, RetrievedEvidence

    module = _eval_module()
    item = RetrievedEvidence(Evidence("web-1", "web-1-p01", "Nội dung đoạn báo.", url=SRC, domain="vnexpress.net"), 0.8)

    class WebRetriever:
        last_status, last_trace = "ok", {"queries": ["q"], "pages": []}

        def search(self, claim, top_k=3):
            return [item]

    recorder = module.RecordingWeb(WebRetriever())
    assert recorder.search("claim a", 20) == [item] and recorder.last_status == "ok"
    path = tmp_path / "snap.jsonl"
    module.append_snapshot(path, "rw1", recorder)
    replay = module.ReplayWeb(module.load_snapshot(path))
    assert replay.search("claim a", 20) == [item]
    assert replay.last_status == "ok" and replay.last_trace == {"queries": ["q"], "pages": []}
    replay.search("claim chưa ghi", 20)
    assert replay.last_status == "not_in_snapshot"


def test_web_status_detects_wrapped_web_retrievers():
    from src.hybrid_retriever import FusedRetriever, HybridSourceRetriever
    from src.source_attribution import SourceAttributionPipeline
    from src.schemas import Evidence

    module = _eval_module()
    corpus = [Evidence("d", "d-p1", "Hà Nội có mưa lớn vào chiều nay theo trung tâm khí tượng.")]
    replay = module.ReplayWeb({})
    pipeline = SourceAttributionPipeline(FusedRetriever([HybridSourceRetriever(corpus, window=1), replay]))
    assert pipeline.run_json("Hà Nội có mưa lớn chiều nay")["retrieval"]["web_status"] == "not_in_snapshot"
    assert module.web_retriever_of(pipeline) is replay


def test_credit_guard_refuses_runs_that_could_exceed_budget():
    module = _eval_module()
    # 50 claim × 2 request + 10% = 110 lượt dự kiến
    assert module.planned_credits(50, 2) == 110
    assert module.credit_shortfall(50, 2, budget=900, used_local=600, used_provider=0) == 0
    assert module.credit_shortfall(50, 2, budget=900, used_local=800, used_provider=0) == 10
    # chừa 100 credit cho demo
    assert module.credit_shortfall(50, 2, budget=900, used_local=700, used_provider=0, reserve=100) == 10
    # Tavily thấy nhiều hơn sổ máy (key dùng ở máy khác) → lấy số lớn hơn
    assert module.credit_shortfall(50, 2, budget=900, used_local=100, used_provider=850) == 60
    # 370 claim (dev + 300) vừa một tháng mới, vẫn chừa 100 cho demo
    assert module.credit_shortfall(370, 2, budget=900, used_local=0, used_provider=0, reserve=100) == 14


def test_run_with_retry_waits_on_rate_limit_and_retries_transient_once(monkeypatch):
    module = _eval_module()
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)

    class Pipeline:
        def __init__(self, statuses):
            self.statuses, self.calls = statuses, 0

        def run_json(self, claim):
            status = self.statuses[min(self.calls, len(self.statuses) - 1)]
            self.calls += 1
            return {"retrieval": {"web_status": status}}

    limited = Pipeline(["rate_limited", "rate_limited", "ok"])
    assert module.run_with_retry(limited, "c")[1] == "ok" and limited.calls == 3
    flaky = Pipeline(["pages_unreachable"])
    assert module.run_with_retry(flaky, "c")[1] == "pages_unreachable" and flaky.calls == 2
