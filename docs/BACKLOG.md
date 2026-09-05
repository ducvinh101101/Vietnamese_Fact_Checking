# Backlog chung

| ID | Việc cần làm | Người phụ trách | Trạng thái | Điều kiện hoàn thành |
|---|---|---|---|---|
| D1 | Tải và audit ViFactCheck | Vinh | Hoàn thành | 7.232 mẫu; không thiếu trường bắt buộc; có audit và split theo URL |
| M1 | TF-IDF + SVM baseline | Vinh | Hoàn thành | E1 group split: Macro-F1 test 40,15%; có confusion matrix và dự đoán |
| M2 | Fine-tune PhoBERT-base | Vinh | Hoàn thành | E2 group split: Macro-F1 test 81,07%; cải thiện 40,92 điểm % so với E1 |
| R1 | Đổi dữ liệu mẫu sang passage ViFactCheck | Quang | Hoàn thành | 5.845 passage từ 1.041 URL ViFactCheck; JSONL hợp lệ, loader đã kiểm tra |
| W1-07 | Khóa môi trường, chạy pytest và ghi manifest/hash artefact | Quang | Hoàn thành | `requirements.lock` (79 dependency), manifest SHA-256 11 artefact và pytest 10/10 pass |
| R2 | Đánh giá BM25 Recall@3/5 | Quang | Hoàn thành | URL-level test: Recall@3 98,14%; Recall@5 98,98%; MRR@5 0,9671; p95 81,20 ms; 10 truy vấn audit |
| W2-04 | Thử dense/FAISS và hybrid RRF | Quang | Hoàn thành | Dev 1.080 query: Recall@5 BM25 98,52%, dense 95,65%, RRF 98,43%; giữ BM25; báo cáo `W2_04_DENSE_HYBRID.md` |
| P1 | Tích hợp kỹ thuật verifier PhoBERT | Vinh | Hoàn thành | Pipeline dùng `VerificationResult` không đổi; smoke test đạt |
| W2-05 | Chốt interface Retriever và Verifier; review chung | Vinh + Quang | Hoàn thành | `src/contracts.py`, dependency injection trong pipeline, integration contract và test bàn giao |
| U1 | Hoàn thiện Streamlit | Quang | To do | Hiển thị label, confidence, evidence và URL |
| Q1 | Phân tích lỗi + báo cáo | Vinh + Quang | To do | Có ít nhất 10 mẫu lỗi phân loại |
| V3 | Bộ 18 claim kiểm thử thủ công + script tái lập | Vinh | Hoàn thành | Có nhãn kỳ vọng, kết quả và ghi rõ giới hạn retrieval mẫu |
| V4 | Đọc thủ công 10 lỗi E2 và phân loại nguyên nhân | Vinh | Hoàn thành | Review tại `REVIEW_10_LOI_E2.md`; không bao gồm retrieval |
| V5 | Chạy E7 biến thể batch ở giới hạn 256 token | Vinh | Hoàn thành | Macro-F1 test 80,25%; giữ E2 (81,07%) |

| R3 | Chốt search provider, allowlist nguồn web và chính sách API key | Quang | Hoàn thành | W2-07: Tavily basic, allowlist 3 host, YAML + chính sách key/quota; validator và test offline. Live retrieval thuộc W3-05 |
| R4 | Web retrieval: lọc domain, trích passage, metadata URL/thời điểm | Quang | Chưa bắt đầu | 100% evidence qua allowlist; có timeout/cache và test |
| R5 | Đánh giá retrieval web/cục bộ/hợp nhất và end-to-end | Vinh + Quang | Chưa bắt đầu | Recall@3/5, MRR, latency, Macro-F1 end-to-end tách riêng |
## Mở rộng phạm vi đề tài — roadmap 6 tuần

| P2 | Đánh giá pipeline PhoBERT trên retrieved evidence thật | Vinh + Quang | Chưa bắt đầu | Macro-F1 end-to-end, citation audit và NEI analysis |
| C1 | Chuẩn hóa schema bài viết/claim/evidence và metadata nguồn-thời gian | Vinh + Quang | Hoàn thành | Data contract v1.0, manifest và loader tương thích ngược |
| C2 | Baseline content-only TF-IDF/SVM trên title + body | Vinh | Hoàn thành | E9 VFND article-only, nested source-domain OOF: Macro-F1 77,27%; ROC-AUC 88,21%; risk score không dùng làm evidence |
| C3 | Content-risk PhoBERT/XLM-R | Vinh | Hoàn thành | E10 PhoBERT nested source-domain OOF: Macro-F1 48,59%; ROC-AUC 70,20%; xác minh không rò rỉ domain. Kém E9 nên giữ E9 làm baseline triển khai |
| C4 | Claim decomposition và tổng hợp cấp bài | Vinh | Đang thực hiện | W3-06 và policy aggregation đã xong độc lập; chờ Quang nối retrieval→verifier để chạy E11 end-to-end |
| C5 | Corpus ingestion, query generation, time/source filter và reranker | Quang | Chưa bắt đầu | Passage corpus có metadata; Recall@k/MRR/nDCG/latency |
| C6 | Temporal/source-held-out test, joint score và citation faithfulness audit | Vinh + Quang | Chưa bắt đầu | Báo cáo oracle/retrieval/E2E; 50 citation review; calibration |
| C7 | Reproducible release | Quang | Chưa bắt đầu | Cài từ đầu, pytest chạy, manifest/hash và demo offline |
