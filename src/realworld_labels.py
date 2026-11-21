"""Đọc và kiểm tra phiếu gán nhãn claim thực tế (kiểm tra nguồn).

Phiếu Excel do ``scripts/create_realworld_labeling_form.py`` tạo; sheet ``Gán nhãn`` có hàng tiêu đề
(mã cột tiếng Anh) ở hàng 4. Quy tắc kiểm tra ở đây GIỐNG công thức cột ``check`` trong Excel, nhưng
được tính lại bằng Python nên không phụ thuộc giá trị công thức đã lưu trong file.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

SHEET_NAME = "Gán nhãn"
HEADER_ROW = 4  # hàng tiêu đề (đếm từ 1) trong sheet Gán nhãn
GROUP_LABEL = {
    "recent_real": "SOURCE_FOUND",
    "paraphrase": "SOURCE_FOUND",
    "perturbed": "SOURCE_CONFLICT",
    "fabricated": "NO_SOURCE",
}
GOOGLE_CHECKED = "Đã tìm – không thấy tin thật"
GOOGLE_NOT_CHECKED = "Chưa tìm"
AGREE, DISAGREE = "Đồng ý", "Không đồng ý"
MIN_CLAIM_CHARS = 15
COLUMNS = ["claim_id", "group", "claim", "source_url", "changed_detail", "google_checked", "annotator",
           "notes", "expected_label", "host", "check", "reviewer", "reviewer_agrees"]


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return " ".join(str(value).split())


def url_host(url: str) -> str:
    url = _text(url)
    if not url.lower().startswith("https://"):
        return ""
    return (urlsplit(url).hostname or "").lower()


def check_row(row: dict, allowed_hosts: set[str], duplicate: bool = False) -> str:
    """Trả về "OK", thông báo lỗi, hoặc "" nếu dòng trống (không có claim)."""
    claim, group, url = _text(row.get("claim")), _text(row.get("group")), _text(row.get("source_url"))
    if not claim:
        return ""
    if group not in GROUP_LABEL:
        return "Chọn nhóm"
    if len(claim) < MIN_CLAIM_CHARS:
        return "Claim quá ngắn"
    if group != "fabricated" and not url:
        return "Thiếu link nguồn"
    if url and not url.lower().startswith("https://"):
        return "Link phải bắt đầu bằng https://"
    if "?" in url or "#" in url:
        return "Xóa phần ?... hoặc #... ở cuối link"
    if url and url_host(url) not in allowed_hosts:
        return "Trang không thuộc danh sách nguồn"
    if group == "perturbed" and not _text(row.get("changed_detail")):
        return "Ghi chi tiết đã sửa (vd. 34 → 45)"
    if group == "fabricated" and _text(row.get("google_checked")) != GOOGLE_CHECKED:
        return "Chưa tìm Google"
    if duplicate:
        return "Trùng claim với dòng khác"
    return "OK"


def load_labeled_claims(path: Path, allowed_hosts: set[str]) -> tuple[pd.DataFrame, list[str]]:
    """Đọc phiếu .xlsx (hoặc .csv) → (các dòng hợp lệ, danh sách cảnh báo về dòng bị bỏ qua).

    * Nhãn ``expected_label`` luôn suy ra từ ``group`` với file .xlsx; file .csv phải tự có cột này.
    * Bỏ qua dòng trống, dòng lỗi và dòng người kiểm tra chéo đánh "Không đồng ý".
    """
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(path, sheet_name=SHEET_NAME, header=HEADER_ROW - 1, dtype=object)
        frame["expected_label"] = frame["group"].map(lambda g: GROUP_LABEL.get(_text(g), ""))
    else:
        frame = pd.read_csv(path, dtype=object)
        missing = {"claim_id", "group", "claim", "expected_label"} - set(frame.columns)
        if missing:
            raise SystemExit(f"Thiếu cột: {sorted(missing)}")
    frame = frame[frame["claim"].map(_text) != ""].copy()
    normalized = frame["claim"].map(lambda c: _text(c).lower())
    duplicates = normalized.duplicated(keep=False)
    warnings, keep = [], []
    for (index, row), is_dup in zip(frame.iterrows(), duplicates):
        row_dict = row.to_dict()
        claim_id = _text(row_dict.get("claim_id")) or f"dòng {index + HEADER_ROW + 1}"
        if path.suffix.lower() in {".xlsx", ".xlsm"}:
            status = check_row(row_dict, allowed_hosts, bool(is_dup))
        else:
            status = "OK" if _text(row_dict.get("expected_label")) in set(GROUP_LABEL.values()) else "expected_label sai"
        if status != "OK":
            warnings.append(f"{claim_id}: {status}")
        elif _text(row_dict.get("reviewer_agrees")) == DISAGREE:
            warnings.append(f"{claim_id}: người kiểm tra chéo không đồng ý")
        else:
            keep.append(index)
    result = frame.loc[keep].copy()
    for column in ("claim_id", "group", "claim", "source_url", "expected_label"):
        if column not in result:
            result[column] = ""
        result[column] = result[column].map(_text)
    return result.reset_index(drop=True), warnings
