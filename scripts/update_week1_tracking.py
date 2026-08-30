"""Đồng bộ trạng thái công việc Vinh tuần 1 vào các tài liệu theo dõi."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise ValueError(f"Không tìm thấy đoạn cần cập nhật trong {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        ROOT / "scripts" / "create_project_plan_excel.py",
        '("W1-01", "Tuần 1", "Dữ liệu", "Tải ViFactCheck, kiểm tra schema, nhãn, bản ghi thiếu và trùng lặp", "Vinh", "Quang", 1.5, "", "data audit + dataset revision", "Cao", "Chưa bắt đầu", ""),',
        '("W1-01", "Tuần 1", "Dữ liệu", "Tải ViFactCheck, kiểm tra schema, nhãn, bản ghi thiếu và trùng lặp", "Vinh", "Quang", 1.5, "", "data audit + dataset revision", "Cao", "Hoàn thành", "Audit: 7.232 mẫu, không thiếu trường bắt buộc"),',
    )
    replace_once(
        ROOT / "scripts" / "create_project_plan_excel.py",
        '("W1-02", "Tuần 1", "Dữ liệu", "Kiểm tra trùng URL/context; tạo split chống rò rỉ và ghi seed", "Vinh", "", 1.0, "W1-01", "train/dev/test + báo cáo split", "Cao", "Chưa bắt đầu", ""),',
        '("W1-02", "Tuần 1", "Dữ liệu", "Kiểm tra trùng URL/context; tạo split chống rò rỉ và ghi seed", "Vinh", "", 1.0, "W1-01", "train/dev/test + báo cáo split", "Cao", "Hoàn thành", "Split 70/15/15 theo URL; rò rỉ URL = 0"),',
    )
    replace_once(
        ROOT / "scripts" / "create_project_plan_excel.py",
        '("W1-03", "Tuần 1", "Mô hình", "Xây TF-IDF word+char n-gram và Linear SVM baseline", "Vinh", "", 1.5, "W1-02", "E1 metrics + confusion matrix", "Cao", "Chưa bắt đầu", ""),',
        '("W1-03", "Tuần 1", "Mô hình", "Xây TF-IDF word+char n-gram và Linear SVM baseline", "Vinh", "", 1.5, "W1-02", "E1 metrics + confusion matrix", "Cao", "Hoàn thành", "E1 group split: Macro-F1 test 40,15%"),',
    )
    replace_once(
        ROOT / "scripts" / "create_project_plan_excel.py",
        '("E1", "Baseline verifier", "TF-IDF word+char + Linear SVM; claim–gold evidence", "Vinh", "Macro-F1", "", "", "Chưa bắt đầu", ""),',
        '("E1", "Baseline verifier", "TF-IDF word+char + Linear SVM; claim–gold evidence", "Vinh", "Macro-F1", "Test: 40,15%", "Giữ làm baseline chính", "Hoàn thành", "C=0,25; group split"),',
    )


if __name__ == "__main__":
    main()
