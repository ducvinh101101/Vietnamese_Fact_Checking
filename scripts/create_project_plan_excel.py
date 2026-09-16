"""Tạo workbook kế hoạch triển khai dự án cho hai người."""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "KE_HOACH_TRIEN_KHAI_2_NGUOI.xlsx"

NAVY = "17365D"
BLUE = "D9EAF7"
TEAL = "0F6B78"
GREEN = "E2F0D9"
YELLOW = "FFF2CC"
RED = "FCE4D6"
GRAY = "F2F2F2"
WHITE = "FFFFFF"
THIN_GRAY = Side(style="thin", color="D9E1F2")
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
SECTION_FILL = PatternFill("solid", fgColor=TEAL)
HEADER_FONT = Font(color=WHITE, bold=True)
TITLE_FONT = Font(color=WHITE, bold=True, size=16)


def style_title(ws, title: str, last_column: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_column)
    cell = ws.cell(1, 1, title)
    cell.fill = HEADER_FILL
    cell.font = TITLE_FONT
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28


def style_header(ws, row: int, columns: list[str]) -> None:
    for index, value in enumerate(columns, start=1):
        cell = ws.cell(row, index, value)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=THIN_GRAY)
    ws.row_dimensions[row].height = 34


def style_table(ws, start_row: int, end_row: int, column_count: int) -> None:
    for row in ws.iter_rows(min_row=start_row, max_row=end_row, min_col=1, max_col=column_count):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(bottom=THIN_GRAY)


def set_widths(ws, widths: dict[str, float]) -> None:
    for column, width in widths.items():
        ws.column_dimensions[column].width = width


def create_overview(workbook: Workbook) -> None:
    ws = workbook.active
    ws.title = "Tổng quan"
    style_title(ws, "KẾ HOẠCH TRIỂN KHAI — HỆ THỐNG KIỂM CHỨNG THÔNG TIN TIẾNG VIỆT", 6)
    ws.merge_cells("A3:F3")
    ws["A3"] = "Thời lượng: 6 tuần | Quy mô: 2 người | Mục tiêu: MVP chạy cục bộ, có bằng chứng và đánh giá được"
    ws["A3"].alignment = Alignment(wrap_text=True)
    ws["A3"].font = Font(italic=True, color="595959")

    rows = [
        ("Mốc", "Kết quả cần bàn giao", "Người chịu trách nhiệm", "Điều kiện hoàn thành"),
        ("Cuối tuần 1", "Dữ liệu đã audit; baseline TF-IDF/SVM; BM25 chạy với dữ liệu mẫu", "Vinh + Quang", "Có EDA, metrics baseline, kho evidence JSONL"),
        ("Cuối tuần 2", "Retriever có Recall@3/5; verifier nâng cao bắt đầu", "Vinh + Quang", "Có bảng so sánh BM25 và ít nhất một cấu hình nâng cao"),
        ("Cuối tuần 3", "Pipeline end-to-end có citation và xử lý NEI", "Vinh + Quang", "Chạy claim → evidence → label, có test"),
        ("Cuối tuần 4", "Ứng dụng Streamlit, báo cáo, slide và demo offline", "Vinh + Quang", "README, số liệu test, 3 kịch bản demo"),
        ("Cuối tuần 5", "Đánh giá temporal/source split, citation audit và ablation", "Vinh + Quang", "Báo cáo oracle/retrieval/end-to-end và calibration"),
        ("Cuối tuần 6", "Freeze release, báo cáo và demo tái lập", "Vinh + Quang", "Cài từ đầu, test tự động, slide và demo offline"),
    ]
    for r_index, row in enumerate(rows, start=5):
        for c_index, value in enumerate(row, start=1):
            ws.cell(r_index, c_index, value)
    style_header(ws, 5, list(rows[0]))
    style_table(ws, 6, 11, 4)

    ws["A14"] = "Phân vai cố định"
    ws["A14"].fill = SECTION_FILL
    ws["A14"].font = HEADER_FONT
    ws.merge_cells("A14:F14")
    roles = [
        ("Vinh", "Dữ liệu & mô hình", "Audit ViFactCheck, split, TF-IDF/SVM, PhoBERT/XLM-R, metrics, phân tích lỗi"),
        ("Quang", "Retrieval & sản phẩm", "Chunking, BM25/dense, index, pipeline, Streamlit, demo và tài liệu chạy"),
        ("Cả hai", "Tích hợp & báo cáo", "Quyết định thí nghiệm, review code, kiểm thử, báo cáo, slide và thuyết trình"),
    ]
    for r_index, row in enumerate(roles, start=15):
        for c_index, value in enumerate(row, start=1):
            ws.cell(r_index, c_index, value)
    style_table(ws, 15, 17, 3)
    set_widths(ws, {"A": 20, "B": 28, "C": 72, "D": 26, "E": 15, "F": 15})
    ws.freeze_panes = "A5"


def create_plan(workbook: Workbook) -> None:
    ws = workbook.create_sheet("Kế hoạch 6 tuần")
    headers = ["ID", "Tuần", "Nhóm việc", "Công việc", "Chủ trì", "Phối hợp", "Ngày công", "Phụ thuộc", "Đầu ra", "Ưu tiên", "Trạng thái", "Ghi chú"]
    style_title(ws, "KẾ HOẠCH CÔNG VIỆC CHI TIẾT", len(headers))
    style_header(ws, 3, headers)
    tasks = [
        ("W1-01", "Tuần 1", "Dữ liệu", "Tải ViFactCheck, kiểm tra schema, nhãn, bản ghi thiếu và trùng lặp", "Vinh", "Quang", 1.5, "", "data audit + dataset revision", "Cao", "Hoàn thành", "Audit: 7.232 mẫu, không thiếu trường bắt buộc"),
        ("W1-02", "Tuần 1", "Dữ liệu", "Kiểm tra trùng URL/context; tạo split chống rò rỉ và ghi seed", "Vinh", "", 1.0, "W1-01", "train/dev/test + báo cáo split", "Cao", "Hoàn thành", "Split 70/15/15 theo URL; rò rỉ URL = 0"),
        ("W1-03", "Tuần 1", "Mô hình", "Xây TF-IDF word+char n-gram và Linear SVM baseline", "Vinh", "", 1.5, "W1-02", "E1 metrics + confusion matrix", "Cao", "Hoàn thành", "E1 group split: Macro-F1 test 40,15%"),
        ("W1-04", "Tuần 1", "Retrieval", "Chuẩn hóa schema evidence JSONL và chia passage theo câu", "Quang", "Vinh", 1.5, "W1-01", "evidence corpus", "Cao", "Hoàn thành", "5.845 passage từ 1.041 URL ViFactCheck; JSONL hợp lệ, loader đã kiểm tra"),
        ("W1-05", "Tuần 1", "Sản phẩm", "Thiết lập repository, config, test và Streamlit dữ liệu mẫu", "Vinh", "Quang", 1.0, "", "MVP chạy cục bộ", "Cao", "Hoàn thành", "Khung đã tạo"),
        ("W2-01", "Tuần 2", "Retrieval", "Xây BM25, đánh giá Recall@3, Recall@5, MRR và latency", "Quang", "Vinh", 1.5, "W1-04", "E3 retrieval metrics", "Cao", "Chưa bắt đầu", ""),
        ("W2-02", "Tuần 2", "Mô hình", "Fine-tune PhoBERT hoặc XLM-R với claim–evidence", "Vinh", "", 2.0, "W1-02", "E2 verifier checkpoint + metrics", "Cao", "Hoàn thành", "PhoBERT-base Kaggle: Macro-F1 test 81,07%"),
        ("W2-03", "Tuần 2", "Nghiên cứu", "So sánh baseline và transformer theo Macro-F1, F1 từng nhãn", "Vinh", "Quang", 0.5, "W1-03; W2-02", "bảng so sánh model", "Cao", "Hoàn thành", "E2 hơn E1 40,92 điểm Macro-F1"),
        ("W2-04", "Tuần 2", "Retrieval", "Thử dense retrieval/FAISS và hybrid RRF nếu BM25 ổn định", "Quang", "", 1.5, "W2-01", "E4/E5 metrics hoặc quyết định bỏ", "Trung bình", "Chưa bắt đầu", ""),
        ("W2-05", "Tuần 2", "Tích hợp", "Chốt interface Retriever và Verifier; review chung", "Vinh", "Quang", 0.5, "W2-01; W2-02", "hợp đồng tích hợp", "Cao", "Hoàn thành", "Protocol, dependency injection, contract doc và test bàn giao"),
        ("W2-06", "Tuần 2", "Mô hình", "Chạy E7 PhoBERT biến thể batch ở giới hạn 256 token", "Vinh", "", 0.5, "W2-02", "E7 metrics + quyết định", "Trung bình", "Hoàn thành", "Test Macro-F1 80,25%; giữ E2 81,07%"),
        ("W2-07", "Tuần 2", "Web retrieval", "Chốt search provider, allowlist nguồn uy tín và chính sách API key", "Quang", "Vinh", 0.5, "", "kế hoạch + config nguồn", "Cao", "Chưa bắt đầu", "Có thể làm song song; API key ngoài Git"),
        ("W3-05", "Tuần 3", "Web retrieval", "Tìm web, lọc allowlist, trích passage và lưu metadata nguồn", "Quang", "Vinh", 1.5, "W2-07", "web evidence retriever", "Cao", "Chưa bắt đầu", "URL, domain, title, fetched_at; timeout/cache"),
        ("W4-05", "Tuần 4", "Đánh giá", "Đo web/local/hybrid retrieval và Macro-F1 end-to-end", "Vinh", "Quang", 1.0, "W3-05", "báo cáo web end-to-end", "Cao", "Chưa bắt đầu", "Tách oracle, retrieval và end-to-end"),
        ("W3-01", "Tuần 3", "Pipeline", "Tích hợp retrieval → verifier → SUPPORTED/REFUTED/NEI", "Quang", "Vinh", 1.5, "W2-05", "pipeline end-to-end", "Cao", "Chưa bắt đầu", ""),
        ("W3-02", "Tuần 3", "Mô hình", "Hiệu chỉnh confidence và chọn ngưỡng NEI trên dev", "Vinh", "Quang", 1.0, "W2-02", "ngưỡng + calibration report", "Cao", "Hoàn thành", "E6 oracle dev: T=1,140542; ECE 3,74%→2,91%; threshold 0,0; retrieval-gating chờ E2E"),
        ("W3-03", "Tuần 3", "Chất lượng", "Kiểm tra citation ID/URL, JSON output và trường hợp không có evidence", "Quang", "", 1.0, "W3-01", "test pipeline", "Cao", "Chưa bắt đầu", ""),
        ("W3-04", "Tuần 3", "Nghiên cứu", "Phân tích 10 lỗi, phân loại lỗi retrieval/verifier/NEI", "Vinh", "Quang", 1.0, "W3-01", "error analysis", "Trung bình", "Hoàn thành", "W4-02 local: audit 10/415 lỗi; 14 retrieval URL-miss, 249 NEI, 152 verifier; web/hybrid chờ Quang"),
        ("W4-01", "Tuần 4", "Giao diện", "Hoàn thiện Streamlit: kết quả từng nhánh, evidence, nguồn, cache", "Quang", "Vinh", 1.5, "W3-01", "app demo", "Cao", "Chưa bắt đầu", ""),
        ("W4-02", "Tuần 4", "Đánh giá", "Chạy test end-to-end, bảng metric và biểu đồ", "Vinh", "Quang", 1.5, "W3-02", "final metrics", "Cao", "Hoàn thành", "E11 local BM25→PhoBERT, 1.076 test: Macro-F1 62,94%; F1 NEI 67,32%; citation URL-match 92,19%; web/hybrid chưa đo"),
        ("W4-03", "Tuần 4", "Tài liệu", "Hoàn thiện README, báo cáo phương pháp/kết quả, giới hạn", "Vinh", "Quang", 1.5, "W4-02", "README + báo cáo", "Cao", "Đang thực hiện", "Vinh hoàn thành báo cáo local W4-03; README/demo UI và web/hybrid chờ phần Quang"),
        ("W4-04", "Tuần 4", "Demo", "Chuẩn bị 3 case demo, slide và phương án offline dự phòng", "Quang", "Vinh", 1.0, "W4-01", "slide + demo script", "Cao", "Chưa bắt đầu", ""),
        ("W1-06", "Tuần 1", "Dữ liệu", "Chốt schema article/claim/evidence và metadata nguồn-thời gian", "Vinh", "Quang", 0.5, "W1-01", "data contract + manifest", "Cao", "Hoàn thành", "Data contract v1.0, manifest và loader tương thích ngược; 5.845 passages/1.041 URL đã kiểm tra"),
        ("W1-07", "Tuần 1", "Chất lượng", "Khóa môi trường, chạy pytest và ghi manifest/hash artefact", "Quang", "Vinh", 0.5, "W1-05", "reproducibility baseline", "Cao", "Chưa bắt đầu", "Cài từ đầu và test CI/local"),
        ("W2-08", "Tuần 2", "Content", "Xây baseline content-only TF-IDF/SVM trên tiêu đề + nội dung", "Vinh", "", 1.5, "W1-06", "E9 metrics + risk score", "Cao", "Hoàn thành", "VFND article-only: OOF Macro-F1 77,27%; ROC-AUC 88,21%; không dùng score làm evidence"),
        ("W2-09", "Tuần 2", "Content", "Fine-tune PhoBERT/XLM-R cho content-risk và calibration", "Vinh", "", 1.5, "W2-08", "E10 metrics + calibration", "Trung bình", "Hoàn thành", "E10 OOF Macro-F1 48,59%; ROC-AUC 70,20%; không rò rỉ domain; kém E9 nên giữ E9"),
        ("W2-10", "Tuần 2", "Retrieval", "Thiết kế corpus ingestion, query set gold và tiêu chí Recall/MRR/nDCG", "Quang", "Vinh", 1.0, "W1-06", "evaluation protocol", "Cao", "Chưa bắt đầu", "Không dùng 10 query tự phát làm benchmark"),
        ("W3-06", "Tuần 3", "Claim", "Tách claim nguyên tử và liên kết claim_id với article_id", "Vinh", "Quang", 1.5, "W1-06", "claim decomposition prototype", "Cao", "Hoàn thành", "Tách bảo toàn nguyên văn; ID ổn định, liên kết article_id; E11 ablation chờ retrieval"),
        ("W3-07", "Tuần 3", "Retrieval", "Nạp corpus passage có metadata nguồn/thời gian và dedup", "Quang", "Vinh", 1.5, "W2-10", "versioned evidence corpus", "Cao", "Chưa bắt đầu", "Lưu published_at/retrieved_at/source_type"),
        ("W3-08", "Tuần 3", "Retrieval", "Sinh query, lọc thời gian/nguồn, rerank và khử trùng evidence", "Quang", "Vinh", 1.5, "W3-07", "reranked top-k evidence", "Cao", "Chưa bắt đầu", "Giữ evidence ủng hộ và phản bác"),
        ("W4-06", "Tuần 4", "Fusion", "Tổng hợp verdict nhiều claim lên cấp bài, kết hợp content-risk minh bạch", "Vinh", "Quang", 1.5, "W3-06; W3-01", "article-level explanation", "Cao", "Đang thực hiện", "Vinh: Article→claim→verdict→aggregation đã xong; chờ UI/retrieval benchmark, không gán cả bài là giả"),
        ("W5-01", "Tuần 5", "Đánh giá", "Đo BM25/dense/hybrid/reranker trên tập query cố định", "Quang", "Vinh", 1.5, "W3-08", "Recall@k, MRR, nDCG, latency", "Cao", "Chưa bắt đầu", "Chọn retrieval theo dev/protocol"),
        ("W5-02", "Tuần 5", "Đánh giá", "Đánh giá content-only, verifier oracle và RAG end-to-end tách riêng", "Vinh", "Quang", 1.5, "W4-06; W5-01", "bảng metric ba tầng", "Cao", "Chưa bắt đầu", "Không trộn metric khác protocol"),
        ("W5-03", "Tuần 5", "Đánh giá", "Temporal/source-held-out test, calibration và citation faithfulness audit", "Vinh", "Quang", 1.5, "W5-02", "external validity report", "Cao", "Chưa bắt đầu", "Review thủ công 50 citation"),
        ("W6-01", "Tuần 6", "Chất lượng", "Tái lập từ đầu: môi trường, dataset/model manifest và test tự động", "Quang", "Vinh", 1.0, "W5-03", "release checklist", "Cao", "Chưa bắt đầu", "pytest bắt buộc pass"),
        ("W6-02", "Tuần 6", "Báo cáo", "Ablation, phân tích lỗi cuối và giới hạn khoa học", "Vinh", "Quang", 1.0, "W5-03", "report results", "Cao", "Chưa bắt đầu", "Nêu rõ failure cases"),
        ("W6-03", "Tuần 6", "Demo", "Đóng gói demo bài viết→claim→evidence→verdict và slide", "Quang", "Vinh", 1.5, "W6-01; W6-02", "final demo + slides", "Cao", "Chưa bắt đầu", "Có offline fallback"),
    ]
    tasks.sort(key=lambda row: tuple(int(part) for part in row[0][1:].split("-")))
    for row_index, row in enumerate(tasks, start=4):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row_index, column_index, value)
    style_table(ws, 4, 3 + len(tasks), len(headers))
    ws.auto_filter.ref = f"A3:L{3 + len(tasks)}"
    ws.freeze_panes = "A4"
    set_widths(ws, {"A": 11, "B": 11, "C": 15, "D": 53, "E": 14, "F": 14, "G": 11, "H": 20, "I": 33, "J": 12, "K": 18, "L": 24})
    for row in range(4, 4 + len(tasks)):
        ws.row_dimensions[row].height = 44

    validation_status = DataValidation(type="list", formula1='"Chưa bắt đầu,Đang thực hiện,Chờ phản hồi,Hoàn thành,Tạm hoãn"')
    validation_priority = DataValidation(type="list", formula1='"Cao,Trung bình,Thấp"')
    ws.add_data_validation(validation_status)
    ws.add_data_validation(validation_priority)
    validation_status.add(f"K4:K{3 + len(tasks)}")
    validation_priority.add(f"J4:J{3 + len(tasks)}")
    ws.conditional_formatting.add(f"K4:K{3 + len(tasks)}", CellIsRule(operator="equal", formula=['"Hoàn thành"'], fill=PatternFill("solid", fgColor=GREEN)))
    ws.conditional_formatting.add(f"K4:K{3 + len(tasks)}", CellIsRule(operator="equal", formula=['"Chờ phản hồi"'], fill=PatternFill("solid", fgColor=YELLOW)))
    ws.conditional_formatting.add(f"K4:K{3 + len(tasks)}", CellIsRule(operator="equal", formula=['"Tạm hoãn"'], fill=PatternFill("solid", fgColor=RED)))


def create_experiments(workbook: Workbook) -> None:
    ws = workbook.create_sheet("Theo dõi thí nghiệm")
    headers = ["Mã", "Mục tiêu", "Cấu hình", "Chủ trì", "Metric chính", "Kết quả", "Quyết định", "Trạng thái", "Commit / ghi chú"]
    style_title(ws, "NHẬT KÝ THÍ NGHIỆM VÀ QUYẾT ĐỊNH", len(headers))
    style_header(ws, 3, headers)
    rows = [
        ("E1", "Baseline verifier", "TF-IDF word+char + Linear SVM; claim–gold evidence", "Vinh", "Macro-F1", "Test: 40,15%", "Giữ làm baseline chính", "Hoàn thành", "C=0,25; group split"),
        ("E2", "Verifier nâng cao", "PhoBERT-base; claim–gold evidence", "Vinh", "Macro-F1 / F1 theo nhãn", "Test: 81,07%", "Model tốt nhất hiện tại", "Hoàn thành", "Kaggle GPU; early stop epoch 5"),
        ("E3", "BM25 retrieval", "BM25 trên passage corpus", "Quang", "Recall@3, Recall@5, MRR, latency", "", "", "Chưa bắt đầu", ""),
        ("E4", "Dense retrieval", "Embedding + FAISS", "Quang", "Recall@5, latency", "", "Chỉ giữ nếu tốt hơn BM25", "Chưa bắt đầu", ""),
        ("E5", "Hybrid end-to-end", "BM25 + dense RRF → verifier", "Vinh + Quang", "Macro-F1 end-to-end", "", "", "Chưa bắt đầu", ""),
        ("E6", "NEI / abstention", "Temperature scaling PhoBERT; decisive threshold trên dev gold evidence", "Vinh", "Macro-F1, F1 NEI, ECE, Brier", "OOF Macro-F1: 85,01%; NEI F1: 89,33%; ECE: 2,91%", "Dùng T=1,140542; threshold=0,0", "Hoàn thành", "Oracle dev only; retrieval-gating chờ E2E"),
        ("E7", "PhoBERT batch variant", "Claim–gold evidence; max_length=256; effective batch=16", "Vinh", "Dev Macro-F1", "Test: 80,25%", "Giữ E2", "Hoàn thành", "Dev 84,18% < E2 85,01%"),
        ("E8", "Web retrieval uy tín", "Allowlist + passage extraction + local/web fusion", "Quang + Vinh", "Recall@3/5, MRR, latency, Macro-F1 E2E", "", "Chỉ triển khai sau khi chốt provider/allowlist", "Chưa bắt đầu", "Không dùng API key trong Git"),
        ("E9", "Content baseline", "TF-IDF/SVM; title + body", "Vinh", "Macro-F1, AUC, calibration", "OOF Macro-F1: 77,27%; ROC-AUC: 88,21%", "Baseline content-risk; không dùng làm evidence", "Hoàn thành", "VFND article-only; nested source-domain CV"),
        ("E10", "Content transformer", "PhoBERT/XLM-R; title + body", "Vinh", "Macro-F1, AUC, calibration", "OOF Macro-F1: 48,59%; ROC-AUC: 70,20%", "Không chọn; E9 cao hơn", "Hoàn thành", "Nested source-domain CV, temperature calibration; không rò rỉ domain"),
        ("E11", "Claim decomposition", "Có/không tách claim nguyên tử", "Vinh + Quang", "Recall@k, E2E Macro-F1", "", "", "Chưa bắt đầu", "Article-level ablation"),
        ("E12", "Reranking & filters", "Query generation + time/source filter + reranker", "Quang", "Recall@k, MRR, nDCG, latency", "", "", "Chưa bắt đầu", "So với BM25/dense/hybrid"),
        ("E13", "External validity", "Temporal/source-held-out + citation audit", "Vinh + Quang", "Joint score, ECE/Brier, faithfulness", "", "", "Chưa bắt đầu", "50 citation review"),
    ]
    for row_index, row in enumerate(rows, start=4):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row_index, column_index, value)
    style_table(ws, 4, 3 + len(rows), len(headers))
    ws.auto_filter.ref = f"A3:I{3 + len(rows)}"
    ws.freeze_panes = "A4"
    set_widths(ws, {"A": 10, "B": 24, "C": 48, "D": 15, "E": 27, "F": 18, "G": 28, "H": 18, "I": 28})


def create_checklist(workbook: Workbook) -> None:
    ws = workbook.create_sheet("Checklist demo")
    headers = ["Hạng mục", "Nội dung kiểm tra", "Người phụ trách", "Trạng thái", "Ghi chú"]
    style_title(ws, "CHECKLIST TRƯỚC KHI DEMO / NỘP BÀI", len(headers))
    style_header(ws, 3, headers)
    rows = [
        ("Dữ liệu", "Có revision dataset, thống kê nhãn và kiểm tra rò rỉ", "Vinh", "Chưa bắt đầu", ""),
        ("Mô hình", "Có baseline, model tốt nhất và metric test", "Vinh", "Chưa bắt đầu", ""),
        ("Retrieval", "Hiển thị được top-k evidence có ID và URL", "Quang", "Chưa bắt đầu", ""),
        ("Pipeline", "Có xử lý NOT_ENOUGH_INFO và lỗi input", "Vinh + Quang", "Chưa bắt đầu", ""),
        ("Giao diện", "App chạy trên máy thuyết trình, đã cache model/index", "Quang", "Chưa bắt đầu", ""),
        ("Demo", "Có case SUPPORTED, REFUTED, NEI và ảnh/chụp dự phòng", "Quang", "Chưa bắt đầu", ""),
        ("Báo cáo", "Có mô tả phương pháp, metric, lỗi và giới hạn", "Vinh + Quang", "Chưa bắt đầu", ""),
        ("Content", "Có baseline content-only và nêu rõ đây là risk score, không phải evidence", "Vinh", "Chưa bắt đầu", ""),
        ("Claim", "Một bài viết được tách claim nguyên tử và tổng hợp verdict minh bạch", "Vinh", "Chưa bắt đầu", ""),
        ("Nguồn", "Evidence có title, URL, thời gian, loại nguồn và authority score", "Quang", "Chưa bắt đầu", ""),
        ("Tái lập", "Cài từ đầu chạy pytest, manifest dữ liệu/model và demo offline", "Quang", "Chưa bắt đầu", ""),
    ]
    for row_index, row in enumerate(rows, start=4):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row_index, column_index, value)
    style_table(ws, 4, 3 + len(rows), len(headers))
    ws.freeze_panes = "A4"
    set_widths(ws, {"A": 18, "B": 62, "C": 17, "D": 18, "E": 28})
    validation = DataValidation(type="list", formula1='"Chưa bắt đầu,Đang thực hiện,Hoàn thành,Không áp dụng"')
    ws.add_data_validation(validation)
    validation.add(f"D4:D{3 + len(rows)}")


def main() -> None:
    workbook = Workbook()
    create_overview(workbook)
    create_plan(workbook)
    create_experiments(workbook)
    create_checklist(workbook)
    for sheet in workbook.worksheets:
        sheet.sheet_view.showGridLines = False
    workbook.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
