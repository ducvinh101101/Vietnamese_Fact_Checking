# Kế hoạch đầy đủ cho đề tài: Phân tích nội dung + RAG fact-checking

Kế hoạch này mở rộng dự án từ MVP kiểm chứng một claim thành hệ thống xử lý bài viết tiếng Việt: phân tích rủi ro nội dung, tách claim, truy xuất evidence có kiểm soát và tổng hợp kết quả ở cấp bài.

## Phạm vi 6 tuần

| Giai đoạn | Kết quả chính | Điều kiện hoàn thành |
|---|---|---|
| Tuần 1 | Dữ liệu, split, schema bài viết/evidence, môi trường tái lập | Có manifest dữ liệu, test chạy được, schema metadata nguồn/thời gian |
| Tuần 2 | Baseline content-only và verifier gold-evidence | So sánh content-only với E1/E2 theo protocol tách biệt |
| Tuần 3 | Corpus evidence, claim decomposition, BM25/dense/reranker | Có passage corpus, Recall@k/MRR/latency và tập query gold cố định |
| Tuần 4 | Web retrieval uy tín, fusion và article aggregation | Citation có URL/thời gian; claim nhiều câu được tổng hợp minh bạch |
| Tuần 5 | Đánh giá end-to-end, temporal/source split và ablation | Tách oracle/retrieval/end-to-end; citation audit và calibration |
| Tuần 6 | Freeze release, báo cáo, demo và tái lập | Cài từ đầu chạy được; README, báo cáo, slide và demo offline |

## Các bổ sung bắt buộc

1. **Content branch:** nhận title + body, trả risk score; không được dùng score này như bằng chứng sai/đúng.
2. **Claim decomposition:** tách bài thành claim nguyên tử có chủ thể, thuộc tính, thời gian; giữ liên kết claim ↔ article.
3. **Evidence metadata:** bắt buộc title, URL, published_at, retrieved_at, source_type, authority_score và phiên bản corpus.
4. **Retrieval thực:** BM25, dense, fusion, rerank, lọc nguồn/thời gian, khử trùng và đo Recall@k/MRR/nDCG/latency.
5. **Article aggregation:** hiển thị verdict từng claim; kết luận cấp bài phải phân biệt “có claim bị bác bỏ” với “toàn bài là giả”.
6. **Đánh giá chuẩn:** oracle evidence, retrieval và end-to-end; F1 từng nhãn, calibration, citation correctness, joint verdict–evidence score và test theo thời gian/nguồn.

## Quy tắc quyết định

- Chỉ thay E2 khi dev Macro-F1 cao hơn; test chỉ để báo cáo cuối.
- Chỉ giữ dense/hybrid khi vượt BM25 theo Recall@5 và latency phù hợp demo.
- Không gọi một bài viết là “tin giả” khi evidence chỉ bác bỏ một claim; báo cáo tỷ lệ claim theo ba nhãn.
- Không đưa web result ngoài allowlist vào verifier.
- API key, checkpoint, raw data và web cache không commit Git.
