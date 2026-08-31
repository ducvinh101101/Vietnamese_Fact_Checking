# Backlog chung

| ID | Việc cần làm | Người phụ trách | Trạng thái | Điều kiện hoàn thành |
|---|---|---|---|---|
| D1 | Tải và audit ViFactCheck | Vinh | Hoàn thành | 7.232 mẫu; không thiếu trường bắt buộc; có audit và split theo URL |
| M1 | TF-IDF + SVM baseline | Vinh | Hoàn thành | E1 group split: Macro-F1 test 40,15%; có confusion matrix và dự đoán |
| M2 | Fine-tune PhoBERT-base | Vinh | Hoàn thành | E2 group split: Macro-F1 test 81,07%; cải thiện 40,92 điểm % so với E1 |
| R1 | Đổi dữ liệu mẫu sang passage ViFactCheck | Quang | To do | JSONL hợp lệ, có test loader |
| R2 | Đánh giá BM25 Recall@3/5 | Quang | To do | Có metrics và 10 truy vấn kiểm tra |
| P1 | Thay rule checker bằng verifier đã fine-tune | Vinh + Quang | To do | Pipeline dùng `VerificationResult` không đổi |
| U1 | Hoàn thiện Streamlit | Quang | To do | Hiển thị label, confidence, evidence và URL |
| Q1 | Phân tích lỗi + báo cáo | Vinh + Quang | To do | Có ít nhất 10 mẫu lỗi phân loại |
