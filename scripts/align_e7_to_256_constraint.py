"""Align E7 docs and tracking with Kaggle's 256-token constraint."""
from pathlib import Path


def replace(path: Path, changes: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in changes.items():
        if old not in text:
            raise RuntimeError(f"Expected text was not found in {path}: {old}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


replace(
    Path("kaggle/train_phobert_e7_long_context.py"),
    {
        "E7 — PhoBERT-base với ngữ cảnh dài hơn": "E7 — PhoBERT-base, biến thể batch ở giới hạn 256 token",
        "MAX_LENGTH = 384": "MAX_LENGTH = 256",
    },
)
Path("docs/KAGGLE_PHOBERT_E7.md").write_text(
    """# E7 — PhoBERT-base, biến thể batch ở giới hạn 256 token

Kaggle hiện giới hạn `max_length=256`, nên E7 không kiểm tra ngữ cảnh dài hơn. E7 giữ dữ liệu, group split, seed, model và max length như E2; chỉ dùng train batch 8 với gradient accumulation 2 (effective batch vẫn là 16).

## Kết quả

E7 đạt Dev Macro-F1 84,18% và Test Macro-F1 80,25%, thấp hơn E2 lần lượt 0,83 và 0,82 điểm phần trăm. Giữ E2 làm model tốt nhất.

Tệp chạy và kết quả: `train_phobert_e7_long_context.py`, `e7_phobert_metrics.json`, `e7_phobert_test_predictions.csv`. Tên file được giữ để không phá vỡ đường dẫn đã dùng; nội dung không còn là thí nghiệm long context.
""",
    encoding="utf-8",
)
replace(
    Path("docs/PHAN_TICH_LOI_E2.md"),
    {
        "E3 chỉ thay đổi độ dài đầu vào từ 256 lên 384 token và giảm batch để giữ bộ nhớ GPU ổn định. Mục tiêu là kiểm tra giả thuyết: các cặp claim–evidence dài bị cắt ở E2, làm giảm khả năng nhận biết mâu thuẫn. Không thay đổi split, seed, model hay cách word segmentation; do đó có thể so sánh trực tiếp với E2.": "E7 đã chạy ở giới hạn 256 token của Kaggle nên chỉ là biến thể batch, không kiểm tra giả thuyết ngữ cảnh dài. E7 có Macro-F1 thấp hơn E2 0,82 điểm phần trăm; giữ E2 làm model tốt nhất.",
    },
)
replace(
    Path("docs/REVIEW_10_LOI_E2.md"),
    {
        "## Tiêu chí đánh giá E7": "## Kết quả E7 và hướng tiếp theo",
        "E7 có ý nghĩa nếu đồng thời đạt các điều kiện sau:": "E7 thực tế phải giữ `max_length=256`, nên không kiểm tra ngữ cảnh dài. Kết quả Test Macro-F1 80,25%, thấp hơn E2 81,07%; giữ E2. Khi có thể thử cấu hình mới, dùng các điều kiện sau:",
        "3. Lỗi `REFUTED → SUPPORTED` giảm từ **57** xuống dưới 50.\n4. Với 10 mẫu review này, ghi lại dự đoán E7; kỳ vọng cải thiện ở các mẫu #3, #4, #6, #7, không kỳ vọng cải thiện rõ ở #1, #2, #9, #10.\n\nKhông thay E2 chỉ vì một vài ví dụ đẹp; quyết định dựa trên dev Macro-F1 rồi mới báo cáo test một lần.": "3. Lỗi `REFUTED → SUPPORTED` giảm nhưng không chỉ bằng cách chuyển hàng loạt sang NOT_ENOUGH_INFO.\n4. Review lại các mẫu #3, #4, #6, #7; không kỳ vọng cấu hình batch đơn thuần sửa các mẫu #1, #2, #9, #10.\n\nKhông thay E2 chỉ vì một vài ví dụ đẹp; quyết định dựa trên dev Macro-F1 rồi mới báo cáo test một lần.",
    },
)
replace(
    Path("docs/BACKLOG.md"),
    {
        "| V5 | Chuẩn bị E7 PhoBERT ngữ cảnh 384 token trên Kaggle | Vinh | Sẵn sàng chạy | Script, giả thuyết và tiêu chí chọn model rõ ràng |": "| V5 | Chạy E7 biến thể batch ở giới hạn 256 token | Vinh | Hoàn thành | Macro-F1 test 80,25%; giữ E2 (81,07%) |",
    },
)
replace(
    Path("scripts/create_project_plan_excel.py"),
    {
        '("W2-06", "Tuần 2", "Mô hình", "Chuẩn bị E7 PhoBERT với ngữ cảnh 384 token trên Kaggle", "Vinh", "", 0.5, "W2-02", "script + tiêu chí chọn model", "Trung bình", "Sẵn sàng chạy", "Giữ split/seed; chỉ đổi max_length và batch")': '("W2-06", "Tuần 2", "Mô hình", "Chạy E7 PhoBERT biến thể batch ở giới hạn 256 token", "Vinh", "", 0.5, "W2-02", "E7 metrics + quyết định", "Trung bình", "Hoàn thành", "Test Macro-F1 80,25%; giữ E2 81,07%")',
        '("E7", "PhoBERT long context", "Claim–gold evidence; max_length=384; effective batch=16", "Vinh", "Dev Macro-F1", "", "Chỉ thay E2 nếu dev Macro-F1 cao hơn", "Sẵn sàng chạy", "Kaggle; seed=42; không đổi split")': '("E7", "PhoBERT batch variant", "Claim–gold evidence; max_length=256; effective batch=16", "Vinh", "Dev Macro-F1", "Test: 80,25%", "Giữ E2", "Hoàn thành", "Dev 84,18% < E2 85,01%")',
    },
)
print("Aligned E7 documentation and tracking with the 256-token constraint.")
