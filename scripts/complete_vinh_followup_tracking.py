"""Finish the E7 rename and record Vinh-only tasks idempotently."""
from pathlib import Path


doc = Path("docs/KAGGLE_PHOBERT_E7.md")
text = doc.read_text(encoding="utf-8")
for old, new in {
    "# E3 —": "# E7 —",
    "| E2 | E3 |": "| E2 | E7 |",
    "Vì vậy E3 cô lập": "Vì vậy E7 cô lập",
    "train_phobert_e3_long_context.py": "train_phobert_e7_long_context.py",
    "../kaggle/train_phobert_e3_long_context.py": "../kaggle/train_phobert_e7_long_context.py",
    "phobert_e3/e3_phobert_metrics.json": "phobert_e7/e7_phobert_metrics.json",
    "e3_phobert_test_predictions.csv": "e7_phobert_test_predictions.csv",
    "chấp nhận E3 là": "chấp nhận E7 là",
    "Nếu E3 không": "Nếu E7 không",
}.items():
    text = text.replace(old, new)
doc.write_text(text, encoding="utf-8")

backlog = Path("docs/BACKLOG.md")
backlog_text = backlog.read_text(encoding="utf-8")
rows = """| V3 | Bộ 18 claim kiểm thử thủ công + script tái lập | Vinh | Hoàn thành | Có nhãn kỳ vọng, kết quả và ghi rõ giới hạn retrieval mẫu |
| V4 | Đọc thủ công 10 lỗi E2 và phân loại nguyên nhân | Vinh | Đang thực hiện | Hoàn tất bảng nhận xét trong `PHAN_TICH_LOI_E2.md` |
| V5 | Chuẩn bị E7 PhoBERT ngữ cảnh 384 token trên Kaggle | Vinh | Sẵn sàng chạy | Script, giả thuyết và tiêu chí chọn model rõ ràng |
"""
if "| V3 |" not in backlog_text:
    backlog.write_text(backlog_text.rstrip() + "\n" + rows, encoding="utf-8")

plan = Path("scripts/create_project_plan_excel.py")
plan_text = plan.read_text(encoding="utf-8")
task = '        ("W2-06", "Tuần 2", "Mô hình", "Chuẩn bị E7 PhoBERT với ngữ cảnh 384 token trên Kaggle", "Vinh", "", 0.5, "W2-02", "script + tiêu chí chọn model", "Trung bình", "Sẵn sàng chạy", "Giữ split/seed; chỉ đổi max_length và batch"),\n'
task_anchor = '        ("W2-05", "Tuần 2", "Tích hợp", "Chốt interface Retriever và Verifier; review chung", "Vinh", "Quang", 0.5, "W2-01; W2-02", "hợp đồng tích hợp", "Cao", "Chưa bắt đầu", ""),\n'
if task not in plan_text:
    plan_text = plan_text.replace(task_anchor, task_anchor + task)
experiment = '        ("E7", "PhoBERT long context", "Claim–gold evidence; max_length=384; effective batch=16", "Vinh", "Dev Macro-F1", "", "Chỉ thay E2 nếu dev Macro-F1 cao hơn", "Sẵn sàng chạy", "Kaggle; seed=42; không đổi split"),\n'
experiment_anchor = '        ("E6", "NEI / abstention", "Ngưỡng retrieval + verifier confidence", "Vinh", "F1 NEI", "", "", "Chưa bắt đầu", ""),\n'
if experiment not in plan_text:
    plan_text = plan_text.replace(experiment_anchor, experiment_anchor + experiment)
plan_text = plan_text.replace('    ws.auto_filter.ref = "A3:I9"', '    ws.auto_filter.ref = f"A3:I{3 + len(rows)}"')
plan.write_text(plan_text, encoding="utf-8")
print("Completed Vinh-only follow-up tracking.")
