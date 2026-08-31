"""Đồng bộ E2 PhoBERT hoàn thành vào backlog và workbook nguồn."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise ValueError(f"Không tìm thấy đoạn cần cập nhật trong {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    backlog = ROOT / "docs" / "BACKLOG.md"
    text = backlog.read_text(encoding="utf-8")
    anchor = "| M1 | TF-IDF + SVM baseline | Vinh | Hoàn thành | E1 group split: Macro-F1 test 40,15%; có confusion matrix và dự đoán |"
    row = "| M2 | Fine-tune PhoBERT-base | Vinh | Hoàn thành | E2 group split: Macro-F1 test 81,07%; cải thiện 40,92 điểm % so với E1 |"
    if row not in text:
        if anchor not in text:
            raise ValueError("Không tìm thấy hàng M1 trong backlog")
        backlog.write_text(text.replace(anchor, anchor + "\n" + row, 1), encoding="utf-8")

    plan_source = ROOT / "scripts" / "create_project_plan_excel.py"
    replace_once(
        plan_source,
        '("W2-02", "Tuần 2", "Mô hình", "Fine-tune PhoBERT hoặc XLM-R với claim–evidence", "Vinh", "", 2.0, "W1-02", "E2 verifier checkpoint + metrics", "Cao", "Chưa bắt đầu", ""),',
        '("W2-02", "Tuần 2", "Mô hình", "Fine-tune PhoBERT hoặc XLM-R với claim–evidence", "Vinh", "", 2.0, "W1-02", "E2 verifier checkpoint + metrics", "Cao", "Hoàn thành", "PhoBERT-base Kaggle: Macro-F1 test 81,07%"),',
    )
    replace_once(
        plan_source,
        '("W2-03", "Tuần 2", "Nghiên cứu", "So sánh baseline và transformer theo Macro-F1, F1 từng nhãn", "Vinh", "Quang", 0.5, "W1-03; W2-02", "bảng so sánh model", "Cao", "Chưa bắt đầu", ""),',
        '("W2-03", "Tuần 2", "Nghiên cứu", "So sánh baseline và transformer theo Macro-F1, F1 từng nhãn", "Vinh", "Quang", 0.5, "W1-03; W2-02", "bảng so sánh model", "Cao", "Hoàn thành", "E2 hơn E1 40,92 điểm Macro-F1"),',
    )
    replace_once(
        plan_source,
        '("E2", "Verifier nâng cao", "PhoBERT hoặc XLM-R; claim–gold evidence", "Vinh", "Macro-F1 / F1 theo nhãn", "", "", "Chưa bắt đầu", ""),',
        '("E2", "Verifier nâng cao", "PhoBERT-base; claim–gold evidence", "Vinh", "Macro-F1 / F1 theo nhãn", "Test: 81,07%", "Model tốt nhất hiện tại", "Hoàn thành", "Kaggle GPU; early stop epoch 5"),',
    )


if __name__ == "__main__":
    main()
