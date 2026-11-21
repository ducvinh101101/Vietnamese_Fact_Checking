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


def _eval_module():
    spec = importlib.util.spec_from_file_location("rw_eval", ROOT / "scripts" / "evaluate_source_attribution_realworld.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_article_ignores_host_change():
    module = _eval_module()
    assert module.same_article("https://nld.com.vn/nld/bai-abc-1962.htm", "https://tuoitre.vn/nld/bai-abc-1962.htm")
    assert not module.same_article("https://vnexpress.net/a-1.html", "https://vnexpress.net/b-2.html")


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
