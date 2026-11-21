"""Tạo phiếu gán nhãn claim thực tế cho bài toán kiểm tra nguồn.

    python scripts/create_realworld_labeling_form.py

Ra file ``data/evaluation/PHIEU_GAN_NHAN_NGUON_V1.xlsx`` gồm 5 sheet: Hướng dẫn, Gán nhãn, Ví dụ,
Nguồn hợp lệ (đọc từ configs/source_attribution.yaml) và Tiến độ. Không ghi đè file đã có
(dùng --force nếu thật sự muốn tạo lại phiếu trắng).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

from src.realworld_labels import (
    AGREE, DISAGREE, GOOGLE_CHECKED, GOOGLE_NOT_CHECKED, GROUP_LABEL, HEADER_ROW, MIN_CLAIM_CHARS, SHEET_NAME,
)
from src.source_attribution_factory import load_config

OUTPUT = ROOT / "data" / "evaluation" / "PHIEU_GAN_NHAN_NGUON_V1.xlsx"
N_ROWS = 300
FIRST = HEADER_ROW + 1
LAST = HEADER_ROW + N_ROWS
TARGETS = {"recent_real": 100, "paraphrase": 60, "fabricated": 70, "perturbed": 70}
GROUP_VI = {
    "recent_real": "Tin thật (2024 trở đi)",
    "paraphrase": "Tin thật viết lại bằng từ khác",
    "fabricated": "Tin bịa",
    "perturbed": "Tin thật bị sửa 1 chi tiết",
}

FONT = "Arial"
NAVY, TEAL, WHITE = "17365D", "0F6B78", "FFFFFF"
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")   # vàng = ô bạn nhập
AUTO_FILL = PatternFill("solid", fgColor="EDEDED")    # xám = tự tính, không sửa
OK_FILL = PatternFill("solid", fgColor="E2F0D9")
ERR_FILL = PatternFill("solid", fgColor="FCE4D6")
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
SECTION_FILL = PatternFill("solid", fgColor=TEAL)
GRID = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
WRAP = Alignment(wrap_text=True, vertical="top")

# (mã cột, tên tiếng Việt, độ rộng, ô nhập?)
COLUMNS = [
    ("claim_id", "Mã", 8, False),
    ("group", "Nhóm (chọn)", 14, True),
    ("claim", "Câu phát biểu (claim)", 60, True),
    ("source_url", "Link bài gốc", 45, True),
    ("changed_detail", "Chi tiết đã sửa (nhóm perturbed)", 20, True),
    ("google_checked", "Đã tìm Google? (nhóm fabricated)", 22, True),
    ("annotator", "Người gán", 12, True),
    ("notes", "Ghi chú", 28, True),
    ("expected_label", "Nhãn (tự điền)", 18, False),
    ("host", "Tên miền (tự điền)", 20, False),
    ("check", "Kiểm tra (tự điền)", 30, False),
    ("reviewer", "Người kiểm tra chéo", 14, True),
    ("reviewer_agrees", "Đồng ý? (chọn)", 14, True),
]
COL = {code: chr(ord("A") + i) for i, (code, *_rest) in enumerate(COLUMNS)}
SOURCES_SHEET = "Nguồn hợp lệ"


def font(**kwargs) -> Font:
    return Font(name=FONT, **kwargs)


def title(ws, text: str, subtitle: str, width: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    ws.cell(1, 1, text).font = font(bold=True, size=15, color=WHITE)
    ws.cell(1, 1).fill = HEAD_FILL
    ws.cell(1, 1).alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 28
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
    ws.cell(2, 1, subtitle).font = font(italic=True, color="595959")


def header(ws, row: int, values: list[str]) -> None:
    for index, value in enumerate(values, start=1):
        cell = ws.cell(row, index, value)
        cell.font, cell.fill, cell.border = font(bold=True, color=WHITE), HEAD_FILL, GRID
        cell.alignment = Alignment(wrap_text=True, vertical="center")


def label_formula(r: int) -> str:
    g = f"{COL['group']}{r}"
    return (f'=IF({g}="","",IF(OR({g}="recent_real",{g}="paraphrase"),"SOURCE_FOUND",'
            f'IF({g}="perturbed","SOURCE_CONFLICT",IF({g}="fabricated","NO_SOURCE","?"))))')


def host_formula(r: int) -> str:
    u = f"TRIM({COL['source_url']}{r})"
    return f'=IF(LOWER(LEFT({u},8))<>"https://","",LOWER(MID({u},9,FIND("/",{u}&"/",9)-9)))'


def check_formula(r: int, n_sources: int) -> str:
    c, g, u = (f"{COL[k]}{r}" for k in ("claim", "group", "source_url"))
    e, f, label, host = (f"{COL[k]}{r}" for k in ("changed_detail", "google_checked", "expected_label", "host"))
    claims = f"${COL['claim']}${FIRST}:${COL['claim']}${LAST}"
    sources = f"'{SOURCES_SHEET}'!$A$5:$A${4 + n_sources}"
    return (
        f'=IF(TRIM({c})="","",'
        f'IF(OR({g}="",{label}="?"),"Chọn nhóm",'
        f'IF(LEN(TRIM({c}))<{MIN_CLAIM_CHARS},"Claim quá ngắn",'
        f'IF(AND({g}<>"fabricated",TRIM({u})=""),"Thiếu link nguồn",'
        f'IF(AND(TRIM({u})<>"",LOWER(LEFT(TRIM({u}),8))<>"https://"),"Link phải bắt đầu bằng https://",'
        f'IF(OR(ISNUMBER(FIND("?",{u})),ISNUMBER(FIND("#",{u}))),"Xóa phần ?... hoặc #... ở cuối link",'
        f'IF(AND({host}<>"",ISNA(MATCH({host},{sources},0))),"Trang không thuộc danh sách nguồn",'
        f'IF(AND({g}="perturbed",TRIM({e})=""),"Ghi chi tiết đã sửa (vd. 34 → 45)",'
        f'IF(AND({g}="fabricated",{f}<>"{GOOGLE_CHECKED}"),"Chưa tìm Google",'
        f'IF(SUMPRODUCT(--(LOWER(TRIM({claims}))=LOWER(TRIM({c}))))>1,"Trùng claim với dòng khác","OK"))))))))))'
    )


def build_label_sheet(wb: Workbook, n_sources: int) -> None:
    ws = wb.create_sheet(SHEET_NAME)
    width = len(COLUMNS)
    title(ws, "PHIẾU GÁN NHÃN – KIỂM TRA NGUỒN",
          "Chỉ nhập vào ô VÀNG. Ô XÁM tự tính – không sửa. Cột “Kiểm tra” phải là OK. Đọc sheet “Hướng dẫn” trước.",
          width)
    for index, (_code, vi, w, is_input) in enumerate(COLUMNS, start=1):
        cell = ws.cell(3, index, vi)
        cell.font = font(bold=True, size=9, color="000000" if is_input else "595959")
        cell.fill = INPUT_FILL if is_input else AUTO_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = GRID
        ws.column_dimensions[chr(ord("A") + index - 1)].width = w
    ws.row_dimensions[3].height = 32
    header(ws, HEADER_ROW, [code for code, *_ in COLUMNS])

    for r in range(FIRST, LAST + 1):
        ws.cell(r, 1, f"rw{r - HEADER_ROW:03d}")
        ws[f"{COL['expected_label']}{r}"] = label_formula(r)
        ws[f"{COL['host']}{r}"] = host_formula(r)
        ws[f"{COL['check']}{r}"] = check_formula(r, n_sources)
        for index, (_code, _vi, _w, is_input) in enumerate(COLUMNS, start=1):
            cell = ws.cell(r, index)
            cell.fill = INPUT_FILL if is_input else AUTO_FILL
            cell.border, cell.alignment, cell.font = GRID, WRAP, font(size=10)

    def dropdown(code: str, values: list[str], prompt: str) -> None:
        dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True,
                            showErrorMessage=True, errorTitle="Giá trị không hợp lệ",
                            error="Hãy chọn trong danh sách.", showInputMessage=True, promptTitle="Chọn",
                            prompt=prompt)
        ws.add_data_validation(dv)
        dv.add(f"{COL[code]}{FIRST}:{COL[code]}{LAST}")

    dropdown("group", list(GROUP_LABEL), "recent_real / paraphrase / fabricated / perturbed")
    dropdown("google_checked", [GOOGLE_CHECKED, GOOGLE_NOT_CHECKED], "Chỉ cần cho nhóm fabricated")
    dropdown("reviewer_agrees", [AGREE, DISAGREE], "Người kiểm tra chéo chọn")

    check_range = f"{COL['check']}{FIRST}:{COL['check']}{LAST}"
    ws.conditional_formatting.add(check_range, CellIsRule(operator="equal", formula=['"OK"'], fill=OK_FILL,
                                                          font=Font(name=FONT, color="006100", bold=True)))
    first_check = f"{COL['check']}{FIRST}"
    ws.conditional_formatting.add(check_range, FormulaRule(
        formula=[f'AND({first_check}<>"",{first_check}<>"OK")'], fill=ERR_FILL, font=Font(name=FONT, color="9C0006")))
    ws.freeze_panes = f"{COL['claim']}{FIRST}"
    ws.auto_filter.ref = f"A{HEADER_ROW}:{COL['reviewer_agrees']}{LAST}"


def build_sources_sheet(wb: Workbook, allowlist: list[dict]) -> None:
    ws = wb.create_sheet(SOURCES_SHEET)
    title(ws, "25 NGUỒN HỢP LỆ", "Link bài gốc phải thuộc đúng một tên miền trong cột A (hệ thống chỉ đọc các trang này). "
          "Danh sách lấy từ configs/source_attribution.yaml.", 4)
    header(ws, 4, ["Tên miền", "Tên", "Loại", "Trang chủ"])
    for r, item in enumerate(allowlist, start=5):
        for c, key in enumerate(("host", "name", "category", "reference"), start=1):
            ws.cell(r, c, str(item.get(key, ""))).font = font(size=10)
    for col, w in zip("ABCD", (24, 36, 14, 36)):
        ws.column_dimensions[col].width = w


def build_progress_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("Tiến độ")
    title(ws, "TIẾN ĐỘ", "Tự cập nhật khi bạn nhập ở sheet “Gán nhãn”. Không cần sửa sheet này.", 6)
    header(ws, 4, ["Nhóm", "Ý nghĩa", "Chỉ tiêu", "Đã xong (OK)", "Còn lỗi", "% chỉ tiêu"])
    src = f"'{SHEET_NAME}'!"
    groups = f"{src}${COL['group']}${FIRST}:${COL['group']}${LAST}"
    checks = f"{src}${COL['check']}${FIRST}:${COL['check']}${LAST}"
    for r, (group, target) in enumerate(TARGETS.items(), start=5):
        ws.cell(r, 1, group)
        ws.cell(r, 2, GROUP_VI[group])
        ws.cell(r, 3, target)
        ws.cell(r, 4, f'=COUNTIFS({groups},A{r},{checks},"OK")')
        ws.cell(r, 5, f'=SUMPRODUCT(({groups}=A{r})*({checks}<>"")*({checks}<>"OK"))')
        ws.cell(r, 6, f"=IF(C{r}=0,0,D{r}/C{r})").number_format = "0%"
    total = 5 + len(TARGETS)
    ws.cell(total, 1, "TỔNG").font = font(bold=True)
    for c in "CDE":
        ws[f"{c}{total}"] = f"=SUM({c}5:{c}{total - 1})"
        ws[f"{c}{total}"].font = font(bold=True)
    ws[f"F{total}"] = f"=IF(C{total}=0,0,D{total}/C{total})"
    ws[f"F{total}"].number_format = "0%"
    ws[f"F{total}"].font = font(bold=True)

    agree = f"{src}${COL['reviewer_agrees']}${FIRST}:${COL['reviewer_agrees']}${LAST}"
    row = total + 2
    ws.cell(row, 1, "Kiểm tra chéo").font = font(bold=True)
    ws.cell(row + 1, 1, "Số claim đã được kiểm tra chéo")
    ws.cell(row + 1, 4, f'=COUNTIF({agree},"{AGREE}")+COUNTIF({agree},"{DISAGREE}")')
    ws.cell(row + 2, 1, "Số claim người kiểm tra KHÔNG đồng ý (cần bàn lại)")
    ws.cell(row + 2, 4, f'=COUNTIF({agree},"{DISAGREE}")')
    ws.cell(row + 3, 1, "Tỷ lệ đồng ý")
    ws.cell(row + 3, 4, f"=IF(D{row + 1}=0,0,1-D{row + 2}/D{row + 1})").number_format = "0%"
    ws.cell(row + 4, 1, "Mục tiêu: kiểm tra chéo ≥ 60 claim; tỷ lệ đồng ý ≥ 90%.").font = font(italic=True, color="595959")
    for col, w in zip("ABCDEF", (22, 32, 10, 14, 10, 12)):
        ws.column_dimensions[col].width = w
    for r in range(5, row + 5):
        for c in range(1, 7):
            if ws.cell(r, c).font.name != FONT:
                ws.cell(r, c).font = font(size=10, bold=ws.cell(r, c).font.bold)


EXAMPLE_URL = ("https://vov.vn/chinh-tri/toan-canh-ngay-dau-van-hanh-chinh-quyen-dia-phuong-2-cap-tai-34-tinh-"
               "thanh-pho-post1211311.vov")
GOOD_EXAMPLES = [
    ("recent_real", "Từ ngày 1/7/2025, 34 tỉnh, thành trên cả nước chính thức vận hành chính quyền địa phương 2 cấp.",
     EXAMPLE_URL, "", "", "Viết gọn một ý có trong bài, giữ nguyên số 34 và ngày 1/7/2025."),
    ("paraphrase", "Kể từ đầu tháng 7/2025, bộ máy chính quyền ở 34 tỉnh, thành phố hoạt động theo mô hình hai cấp "
     "gồm cấp tỉnh và cấp xã.", EXAMPLE_URL, "", "", "Cùng ý với bài nhưng dùng từ khác; số liệu giữ nguyên."),
    ("perturbed", "Từ ngày 1/7/2025, 45 tỉnh, thành trên cả nước chính thức vận hành chính quyền địa phương 2 cấp.",
     EXAMPLE_URL, "34 → 45", "", "Chỉ sửa MỘT chi tiết; vẫn dán link bài gốc."),
    ("fabricated", "Bộ Y tế khuyến cáo uống nước chanh ấm mỗi sáng giúp chữa khỏi ung thư gan.", "", "",
     GOOGLE_CHECKED, "Đã tìm Google, không có bài nào đưa tin này → để trống link."),
]
BAD_EXAMPLES = [
    ("Giá vàng sẽ còn tăng mạnh trong năm tới.", "Là dự đoán/ý kiến – không có đúng sai về nguồn.", "Bỏ, chọn câu khác."),
    ("GDP quý III tăng 7% và lạm phát giảm còn 3%.", "Hai ý trong một câu.", "Tách thành 2 dòng, mỗi dòng một ý."),
    ("Link: https://vnexpress.net/bai-viet-123.html?utm_source=facebook", "Có phần ?utm_... ở cuối.",
     "Xóa từ dấu ? trở đi: https://vnexpress.net/bai-viet-123.html"),
    ("Link: https://www.facebook.com/... hoặc báo không có trong sheet Nguồn hợp lệ",
     "Hệ thống chỉ đọc 25 trang hợp lệ.", "Tìm cùng tin đó trên một trang hợp lệ."),
    ("Hà Nội cấm hoàn toàn xe máy chạy xăng từ ngày 1/1/2026 (định gán fabricated)",
     "Có tin THẬT gần giống về lộ trình hạn chế xe máy xăng ở Hà Nội → không phải tin bịa.",
     "Luôn tìm Google trước. Có tin thật gần giống → dùng nhóm perturbed (ghi chi tiết đã sửa) hoặc bỏ."),
    ("Chép nguyên cả đoạn 4–5 câu từ bài báo.", "Claim quá dài, nhiều ý.", "Rút lại thành 1 câu, 1 ý."),
    ("Bài báo năm 2019.", "Tin cũ có thể đã nằm sẵn trong kho dữ liệu → không đo được khả năng tìm trên web.",
     "Chỉ dùng bài từ năm 2024 trở đi."),
]


def build_examples_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("Ví dụ")
    title(ws, "VÍ DỤ MẪU", "Bốn dòng điền đúng (mỗi nhóm một dòng, cùng một bài báo thật) và các lỗi hay gặp.", 6)
    header(ws, 4, ["Nhóm", "Câu phát biểu (claim)", "Link bài gốc", "Chi tiết đã sửa", "Đã tìm Google?", "Vì sao đúng"])
    for r, values in enumerate(GOOD_EXAMPLES, start=5):
        for c, value in enumerate(values, start=1):
            cell = ws.cell(r, c, value)
            cell.font, cell.alignment, cell.border, cell.fill = font(size=10), WRAP, GRID, OK_FILL
    row = 5 + len(GOOD_EXAMPLES) + 1
    ws.cell(row, 1, "LỖI HAY GẶP").font = font(bold=True, color=WHITE)
    ws.cell(row, 1).fill = SECTION_FILL
    header(ws, row + 1, ["Ví dụ sai", "Vì sao sai", "Sửa thế nào"])
    for r, values in enumerate(BAD_EXAMPLES, start=row + 2):
        for c, value in enumerate(values, start=1):
            cell = ws.cell(r, c, value)
            cell.font, cell.alignment, cell.border, cell.fill = font(size=10), WRAP, GRID, ERR_FILL
    for col, w in zip("ABCDEF", (34, 55, 45, 14, 22, 40)):
        ws.column_dimensions[col].width = w


GUIDE = [
    ("h", "1. Phiếu này để làm gì?"),
    ("p", "Hệ thống của nhóm trả lời: một câu phát biểu có nguồn báo chí thật hay không. Để đo nó đúng bao nhiêu trên "
          "tin THẬT ngoài đời (không phải dữ liệu ViFactCheck), nhóm cần ~300 câu đã biết trước đáp án. Bạn viết câu, "
          "chọn nhóm; phiếu tự điền nhãn đúng và tự báo lỗi."),
    ("h", "2. Màu ô"),
    ("p", "VÀNG = ô bạn nhập.   XÁM = phiếu tự tính, KHÔNG sửa (Mã, Nhãn, Tên miền, Kiểm tra)."),
    ("p", "Cột “Kiểm tra” hiện OK (xanh) là dòng đã đạt. Hiện chữ đỏ thì đọc lỗi và sửa (xem mục 7)."),
    ("h", "3. Chia việc (2 người)"),
    ("p", "Người A làm rw001–rw150, người B làm rw151–rw300. Mỗi người: 50 recent_real, 30 paraphrase, "
          "35 fabricated, 35 perturbed. Xem số đã làm ở sheet “Tiến độ”."),
    ("p", "Mỗi bài báo dùng tối đa 3 claim; lấy bài từ nhiều chủ đề (thời sự, kinh tế, y tế, giáo dục, thể thao, "
          "pháp luật…) và nhiều trang khác nhau, không dồn vào một trang."),
    ("h", "4. Nhóm recent_real – tin thật (làm trước tiên)"),
    ("s", "Bước 1. Mở một trang trong sheet “Nguồn hợp lệ” (vd. vnexpress.net, tuoitre.vn, vov.vn)."),
    ("s", "Bước 2. Chọn một bài đăng từ năm 2024 trở đi. Xem ngày đăng ở đầu bài."),
    ("s", "Bước 3. Chọn MỘT câu có thông tin cụ thể (số liệu, ngày, tên người/nơi, sự kiện). Viết lại gọn thành một câu, "
          "giữ nguyên số, ngày, tên. Dán vào cột “Câu phát biểu”."),
    ("s", "Bước 4. Copy link trên thanh địa chỉ, dán vào “Link bài gốc”. Nếu link có dấu ? hoặc # thì xóa từ dấu đó trở đi."),
    ("s", "Bước 5. Cột “Nhóm” chọn recent_real. Cột “Người gán” ghi tên bạn. Kiểm tra cột “Kiểm tra” = OK."),
    ("h", "5. Nhóm paraphrase – tin thật viết lại"),
    ("s", "Lấy một tin thật (có thể từ bài bạn vừa dùng). Viết lại bằng từ khác, đổi cấu trúc câu, nhưng GIỮ NGUYÊN ý và "
          "mọi con số/ngày/tên. Vẫn dán link bài gốc. Chọn nhóm paraphrase."),
    ("p", "Ví dụ: “giảm 500 đồng/lít” → “rẻ đi 500 đồng mỗi lít”; “khánh thành” → “chính thức đưa vào sử dụng”."),
    ("h", "6. Nhóm perturbed – tin thật bị sửa một chi tiết"),
    ("s", "Lấy một tin thật, sửa ĐÚNG MỘT chi tiết: con số, ngày tháng, tên người hoặc địa danh. Không sửa ý chính."),
    ("s", "Ghi chi tiết đã sửa vào cột “Chi tiết đã sửa”, dạng gốc → mới (vd. 34 → 45; 1/7 → 1/9; Đà Nẵng → Huế)."),
    ("s", "Vẫn dán link bài GỐC. Chọn nhóm perturbed."),
    ("h", "7. Nhóm fabricated – tin bịa"),
    ("s", "Tự nghĩ một tin nghe có vẻ thật nhưng KHÔNG có thật, kiểu tin giả hay lan trên mạng (y tế, chính sách, "
          "người nổi tiếng, thiên tai…)."),
    ("s", "BẮT BUỘC: dán câu đó vào Google, đọc kết quả trang đầu. Nếu có bài thật đưa tin giống hoặc gần giống → "
          "KHÔNG dùng làm fabricated (chuyển sang perturbed hoặc bỏ)."),
    ("s", "Không thấy tin thật nào → cột “Đã tìm Google?” chọn “" + GOOGLE_CHECKED + "”. Để trống link. Chọn nhóm fabricated."),
    ("p", "Không bịa tin bôi nhọ một người cụ thể có thật. Dùng chủ đề chung (sản phẩm, chính sách, sức khỏe…)."),
    ("h", "8. Cột “Kiểm tra” báo lỗi → sửa thế nào"),
    ("p", "Chọn nhóm → chọn nhóm ở cột “Nhóm” (bấm vào ô, chọn trong danh sách)."),
    ("p", "Claim quá ngắn → câu phải có ít nhất " + str(MIN_CLAIM_CHARS) + " ký tự và đủ thông tin."),
    ("p", "Thiếu link nguồn → recent_real, paraphrase, perturbed đều phải có link bài gốc."),
    ("p", "Link phải bắt đầu bằng https:// → copy lại link đầy đủ từ trình duyệt."),
    ("p", "Xóa phần ?... hoặc #... ở cuối link → xóa từ dấu ? hoặc # trở đi."),
    ("p", "Trang không thuộc danh sách nguồn → tìm cùng tin trên một trang ở sheet “Nguồn hợp lệ”. Chú ý www: "
          "www.sggp.org.vn và www.who.int phải có www; các trang báo còn lại viết không có www."),
    ("p", "Ghi chi tiết đã sửa → nhóm perturbed phải ghi chi tiết đã đổi."),
    ("p", "Chưa tìm Google → nhóm fabricated phải tìm Google và chọn “" + GOOGLE_CHECKED + "”."),
    ("p", "Trùng claim với dòng khác → hai dòng có cùng câu; sửa hoặc xóa một dòng."),
    ("h", "9. Quy tắc viết claim"),
    ("p", "• Một câu, một ý. Có hai ý (“A tăng và B giảm”) thì tách thành hai dòng."),
    ("p", "• Phải là sự kiện kiểm chứng được. Không dùng ý kiến, dự đoán, cảm nhận (“sẽ tăng”, “là đúng đắn”)."),
    ("p", "• Viết tiếng Việt có dấu, câu hoàn chỉnh, không chép nguyên cả đoạn dài."),
    ("p", "• Phân vân thì ghi lý do vào “Ghi chú”, không đoán."),
    ("h", "10. Kiểm tra chéo (sau khi mỗi người xong phần mình)"),
    ("s", "Mỗi người chọn ~30 dòng của người kia (rải đều 4 nhóm). Mở link, đọc bài, kiểm tra claim có đúng với nhóm không."),
    ("s", "Ghi tên vào “Người kiểm tra chéo”, chọn “" + AGREE + "” hoặc “" + DISAGREE + "”. Dòng “"
          + DISAGREE + "” sẽ bị bỏ khi chấm cho đến khi hai người bàn lại và sửa."),
    ("p", "Sheet “Tiến độ” hiện tỷ lệ đồng ý; mục tiêu ≥ 90%."),
    ("h", "11. Lưu file và làm việc chung"),
    ("p", "• Lưu đúng định dạng .xlsx (File → Save). KHÔNG cần đổi sang CSV."),
    ("p", "• Hai người làm chung một file: đưa lên OneDrive/Google Drive và mở cùng lúc, hoặc mỗi người một bản rồi "
          "dán phần của mình (rw151–rw300) vào file chung."),
    ("p", "• Không xóa hay chèn cột, không đổi tên sheet “" + SHEET_NAME + "” – script đọc đúng vị trí này."),
    ("h", "12. Chấm điểm (khi đã xong)"),
    ("p", "Mở PowerShell ở thư mục dự án và chạy (key Tavily đọc từ file .env):"),
    ("c", r".venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_GAN_NHAN_NGUON_V1.xlsx"),
    ("c", r".venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_GAN_NHAN_NGUON_V1.xlsx --no-web"),
    ("p", "Lệnh đầu có web (tốn ~2 lượt Tavily/claim, chỉ chạy 1–2 lần); lệnh sau chỉ dùng kho cục bộ, không tốn lượt. "
          "Dòng không OK được bỏ qua và in ra màn hình. Kết quả ghi vào outputs/metrics/source_attribution_realworld_*.json."),
    ("p", "Nên chạy thử khi mới có ~20 claim OK để phát hiện lỗi sớm."),
]


def build_guide_sheet(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "Hướng dẫn"
    title(ws, "HƯỚNG DẪN GÁN NHÃN – KIỂM TRA NGUỒN", "Đọc hết một lượt (~10 phút) trước khi bắt đầu. "
          "Ví dụ cụ thể ở sheet “Ví dụ”.", 2)
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 120
    r = 4
    for kind, text in GUIDE:
        if kind == "h" and r > 4:
            r += 1  # dòng trống trước mỗi mục
        cell = ws.cell(r, 2, text)
        if kind == "h":
            cell.font, cell.fill = font(bold=True, size=12, color=WHITE), SECTION_FILL
        elif kind == "c":
            cell.font, cell.fill = Font(name="Consolas", size=10), AUTO_FILL
        else:
            cell.font = font(size=10, bold=text.startswith("Bước"))
            cell.alignment = Alignment(wrap_text=True, vertical="top", indent=1 if kind == "s" else 0)
            ws.row_dimensions[r].height = 15 * max(1, -(-len(text) // 125))
        r += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--force", action="store_true", help="ghi đè phiếu đã có (MẤT dữ liệu đã gán)")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        raise SystemExit(f"{args.output} đã tồn tại – không ghi đè (dùng --force nếu chắc chắn).")
    allowlist = load_config()["web_retrieval"]["source_policy"]["allowlist"]
    wb = Workbook()
    build_guide_sheet(wb)
    build_label_sheet(wb, len(allowlist))
    build_examples_sheet(wb)
    build_sources_sheet(wb, allowlist)
    build_progress_sheet(wb)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.output)
    print(f"Đã tạo {args.output}")


if __name__ == "__main__":
    main()
