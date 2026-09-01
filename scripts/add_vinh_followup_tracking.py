"""Record Vinh-only follow-up work without changing Quang's tasks."""
from pathlib import Path


def replace_in(path: Path, replacements: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(f"Missing expected text in {path}: {old}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


replace_in(
    Path("kaggle/train_phobert_e7_long_context.py"),
    {
        "E3 — PhoBERT-base": "E7 — PhoBERT-base",
        "phobert_e3": "phobert_e7",
        "E3_long_context": "E7_long_context",
        "e3_phobert": "e7_phobert",
    },
)
replace_in(
    Path("docs/KAGGLE_PHOBERT_E7.md"),
    {
        "# E3 —": "# E7 —",
        "E3 chỉ": "E7 chỉ",
        "| E3 |": "| E7 |",
        "tác động của độ dài đầu vào.\n": "tác động của độ dài đầu vào.\n",
        "[train_phobert_e3_long_context.py](../kaggle/train_phobert_e3_long_context.py)": "[train_phobert_e7_long_context.py](../kaggle/train_phobert_e7_long_context.py)",
        "phobert_e3/e3_phobert_metrics.json": "phobert_e7/e7_phobert_metrics.json",
        "e3_phobert_test_predictions.csv": "e7_phobert_test_predictions.csv",
        "E3 là model": "E7 là model",
        "Nếu E3 không": "Nếu E7 không",
    },
)

backlog = Path("docs/BACKLOG.md")
text = backlog.read_text(encoding="utf-8")
rows = """| V3 | Bộ 18 claim kiểm thử thủ công + script tái lập | Vinh | Hoàn thành | Có nhãn kỳ vọng, kết quả và ghi rõ giới hạn retrieval mẫu |
| V4 | Đọc thủ công 10 lỗi E2 và phân loại nguyên nhân | Vinh | Đang thực hiện | Hoàn tất bảng nhận xét trong `PHAN_TICH_LOI_E2.md` |
| V5 | Chuẩn bị E7 PhoBERT ngữ cảnh 384 token trên Kaggle | Vinh | Sẵn sàng chạy | Script, giả thuyết và tiêu chí chọn model rõ ràng |
"""
if "| V3 |" not in text:
    backlog.write_text(text.rstrip() + "\n" + rows, encoding="utf-8")

plan = Path("scripts/create_project_plan_excel.py")
text = plan.read_text(encoding="utf-8")
anchor = '        ("W2-05", "Tuần 2", "Tích hợp", "Chốt interface Retriever và Verifier; review chung", "Vinh", "Quang", 0.5, "W2-01; W2-02", "hợp đồng tích hợp", "Cao", "Chưa bắt đầu", ""),\n'
new_task = '        ("W2-06", "Tuần 2", "Mô hình", "Chuẩn bị E7 PhoBERT với ngữ cảnh 384 token trên Kaggle", "Vinh", "", 0.5, "W2-02", "script + tiêu chí chọn model", "Trung bình", "Sẵn sàng chạy", "Giữ split/seed; chỉ đổi max_length và batch"),\n'
if new_task not in text:
    if anchor not in text:
        raise RuntimeError("Missing task insertion point.")
    text = text.replace(anchor, anchor + new_task)
experiment_anchor = '        ("E6", "NEI / abstention", "Ngưỡng retrieval + verifier confidence", "Vinh", "F1 NEI", "", "", "Chưa bắt đầu", ""),\n'
experiment = '        ("E7", "PhoBERT long context", "Claim–gold evidence; max_length=384; effective batch=16", "Vinh", "Dev Macro-F1", "", "Chỉ thay E2 nếu dev Macro-F1 cao hơn", "Sẵn sàng chạy", "Kaggle; seed=42; không đổi split"),\n'
if experiment not in text:
    if experiment_anchor not in text:
        raise RuntimeError("Missing experiment insertion point.")
    text = text.replace(experiment_anchor, experiment_anchor + experiment)
text = text.replace('    ws.auto_filter.ref = "A3:I9"', '    ws.auto_filter.ref = f"A3:I{3 + len(rows)}"')
plan.write_text(text, encoding="utf-8")
print("Updated Vinh-only backlog and workbook generator.")
