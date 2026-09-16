# W3-08 — Query, filter, rerank và dedup evidence

`MetadataRerankedRetriever` giữ BM25 làm candidate generator, chuẩn hóa claim thành
một query tái lập, lọc `source_type`/khoảng `published_at`, rerank bằng overlap
query + authority policy và khử trùng `(URL, normalized content)`. Không gọi hay
thay đổi verifier của Vinh. `published_at=null` được cấu hình giữ/bỏ rõ ràng.

Chạy `python scripts/run_w3_08_reranking.py` để tạo top-3 cho 1.080 query dev
frozen. Đây là artefact retrieval, không phải Recall/MRR/nDCG hoặc kết quả E2E;
metric protocol vẫn thuộc W5-01.
