# Quy trình nghiên cứu có thể tái lập

## Mỗi thí nghiệm cần lưu

- Mã thí nghiệm: `E1`, `E2`, …
- Commit Git và revision của dataset.
- Split, seed, số mẫu và kiểm tra trùng URL/context.
- Cấu hình model, retrieval và ngưỡng NEI.
- Macro-F1, F1 từng nhãn, Recall@3/5, latency.
- 3–5 lỗi điển hình và kết luận hành động tiếp theo.

Lưu metadata cạnh kết quả trong `outputs/metrics/<experiment>.json`; chỉ commit file nhỏ này, không commit artefact lớn.

## Thứ tự thí nghiệm

1. `E1`: TF-IDF + Linear SVM với claim–gold evidence.
2. `E2`: PhoBERT với claim–gold evidence.
3. `E3`: BM25 và Recall@3/5.
4. `E4`: BM25 → verifier (end-to-end).
5. `E5`: dense/hybrid chỉ khi E3 ổn định.

## Tiêu chí quyết định

- Chọn verifier theo Macro-F1 validation, không theo accuracy.
- Chỉ giữ hybrid nếu Recall@5 tốt hơn BM25 và không làm demo quá chậm.
- Chọn ngưỡng `NOT_ENOUGH_INFO` trên validation; không tinh chỉnh theo test.
- Báo cáo tách ba tầng: oracle evidence, retrieval, end-to-end.

## Quy tắc thí nghiệm web retrieval

- Ghi phiên bản allowlist, nhà cung cấp search, thời điểm chạy, quota và cache policy.
- Không lưu API key trong Git; lưu metadata URL/domain/title/fetched_at cạnh kết quả.
- Đánh giá tách retrieval cục bộ, web retrieval và hợp nhất; báo cáo tỷ lệ evidence ngoài allowlist phải bằng 0.
- Snapshot tập query trước khi đo để kết quả web có thể đối chiếu lại.

## Mở rộng thí nghiệm cho đề tài đầy đủ

6. `E9`: content-only TF-IDF/SVM trên title + body.
7. `E10`: content-only PhoBERT/XLM-R risk score.
8. `E11`: claim decomposition và article aggregation ablation.
9. `E12`: query generation, temporal/source filtering và reranker.
10. `E13`: temporal/source-held-out end-to-end và citation audit.

Mỗi E9–E13 phải báo cáo protocol riêng; không so sánh trực tiếp metric content-only với metric verifier dùng gold evidence.

## Thứ tự báo cáo cuối

1. Content-only: E9/E10.
2. Oracle verifier: E1/E2/E7.
3. Retrieval: E3/E4/E5/E8/E12.
4. End-to-end và external validity: E11/E13.

Mỗi bảng kết quả phải nêu rõ loại input/evidence; không dùng một con số Macro-F1 để đại diện toàn hệ thống.
