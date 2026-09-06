# W4-03 — Báo cáo pipeline cục bộ

> Cập nhật 2026-09-07: bảng dưới là kết quả lịch sử của policy rank. Runtime đang dùng ứng viên AGG-V1 được chọn trên dev (OOF accuracy 70,19%, Macro-F1 69,78%); chưa có đánh giá thực tế độc lập cho ứng viên này. Xem [rà soát mục tiêu 80%](REAL_WORLD_ACCURACY_PLAN.md).

## Kết luận ngắn

Pipeline cục bộ `BM25 top-3 → PhoBERT E2 → verdict/citation` đã được đánh giá trên 1.076 mẫu test giữ lại. Sau baseline W4-02, E11 chọn policy theo rank/NEI hoàn toàn trên dev rồi xác nhận một lần trên test. Kết quả tốt nhất hiện tại là **Macro-F1 62,94%**, accuracy **64,96%**. Đây là kết quả retrieval-to-verdict thực tế của kho local, không phải kết quả oracle E2 với gold evidence.

## Thiết lập tái lập

| Thành phần | Cấu hình cố định |
| --- | --- |
| Corpus | ViFactCheck local, 5.845 passage |
| Retrieval | BM25, top-k = 3 |
| Verifier | PhoBERT E2, claim–passage, tối đa 256 token |
| Quyết định | Three-way SUPPORTED/REFUTED/NEI; temperature 1,140542; rank bias 1,0; decisive threshold 0,60 |
| Test | `vifactcheck_group_split/test.parquet`, 1.076 mẫu, URL-disjoint với train/dev |
| Thời điểm chọn tham số | E6 OOF trên dev gold-evidence; test không được dùng để tune |

Hash config/corpus/split và từng prediction/citation được lưu trong [W4-02 metrics](../outputs/metrics/w4_02_local_end_to_end_test.json).

## Kết quả W4-02

| Metric | Giá trị |
| --- | ---: |
| Accuracy | 64,96% |
| Macro-F1 | 62,94% |
| F1 SUPPORTED | 71,69% |
| F1 REFUTED | 49,81% |
| F1 NOT_ENOUGH_INFO | 67,32% |
| URL-level Recall@3 | 98,14% |
| Citation URL khớp URL annotation | 92,19% |
| Latency trung bình / p95 | 692,14 ms / 948,77 ms |

So với W4-02 max-confidence baseline, E11 tăng 3,45 điểm Macro-F1 và 11,06 điểm citation URL-match nhờ ưu tiên passage hạng cao và NEI có điều kiện; tham số chỉ chọn trên dev. E2 oracle (gold evidence) vẫn đạt Macro-F1 81,07%, cao hơn E11 18,13 điểm %, nên retrieval/candidate evidence và quyết định trên evidence thật vẫn là nút thắt. URL-level không chứng minh passage cụ thể đủ để entail hay refute claim.

Confusion matrix (hàng = gold, cột = dự đoán; thứ tự SUPPORTED, REFUTED, NEI):

```text
[[328,   8,  32],
 [134, 129,  93],
 [ 85,  25, 242]]
```

## Phân tích lỗi W3-04

Audit W3-04 baseline có 415 lỗi, trong đó chỉ 14 lỗi `retrieval_url_miss`; phần lớn là NEI hoặc verifier dù URL vàng đã có. E11 làm giảm lỗi từ 415 còn 377, chủ yếu nhờ NEI/citation; F1 REFUTED vẫn chỉ 49,81%, vì vậy không nên khẳng định hệ thống đã bắt phủ định/đảo thực thể tốt. Audit baseline 10 mẫu vẫn ở [W3-04](W3_04_PIPELINE_ERROR_ANALYSIS.md).

## Giới hạn khoa học và phạm vi chưa làm

- Chỉ có corpus BM25 cục bộ; chưa có web retrieval, allowlist live, dense/hybrid hay reranker.
- Relevance và citation-match hiện chỉ là URL-level proxy; chưa có qrels passage-level hoặc review thủ công 50 citation.
- E6 chỉ hiệu chỉnh trên dev với gold evidence; chưa có retrieval-gating/hard-negative training được chọn hợp lệ.
- Chưa có temporal/source-held-out test, calibration end-to-end hoặc đánh giá content-risk fusion.

Vì vậy kết quả này hoàn thành **W4-02 local** và phần báo cáo/kết quả của **W4-03 (Vinh)**, không thay thế R5/C6/W5-02/W5-03 hay đánh giá hệ thống web đầy đủ.

## Bước tiếp theo

1. Quang hoàn thiện web/hybrid retrieval và benchmark theo protocol query frozen.
2. Hai người đo lại retrieval và verdict cho local/web/hybrid tách riêng; không dùng test này để chọn tham số.
3. Vinh thực hiện passage/citation faithfulness audit, temporal/source-held-out test và error analysis sau reranker.
