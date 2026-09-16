# E11 — Policy theo hạng evidence cho pipeline local

## Mục tiêu

Giảm trường hợp passage hạng thấp nhưng overconfident ghi đè evidence hạng cao, đồng thời đưa verdict quyết đoán thiếu confidence về `NOT_ENOUGH_INFO`. Đây là thay đổi **policy inference**, không fine-tune lại PhoBERT và không dùng test để chọn tham số.

## Chọn tham số trên dev

Trên 1.080 dev claim, script tạo BM25 top-3 và xác suất PhoBERT đã temperature-scale. Grid nhỏ chọn `rank_bias` và `decisive_min_confidence` theo Macro-F1; khi hòa, ưu tiên F1 REFUTED rồi F1 NEI. Test không được mở.

| Policy dev | Macro-F1 | F1 REFUTED | F1 NEI |
| --- | ---: | ---: | ---: |
| Max confidence cũ (`bias=0`, threshold=0) | 58,49% | 48,31% | 58,79% |
| Được chọn (`bias=1`, threshold=0,60) | **63,08%** | **50,78%** | **66,57%** |

`rank_bias=1` nhân điểm chọn evidence với `1/rank`; confidence hiển thị vẫn là xác suất đã hiệu chỉnh không bị nhân trọng số. Nếu nhãn SUPPORTED/REFUTED thắng nhưng confidence thấp hơn 0,60, policy trả NEI từ candidate có xác suất NEI theo hạng tốt nhất.

Artifact: `outputs/metrics/e11_dev_rank_aware_policy.json` và `outputs/predictions/e11_dev_rank_aware_candidates.csv`.

## Xác nhận test giữ lại

Sau khi khóa `bias=1,0`, `threshold=0,60`, một lượt test riêng trên 1.076 mẫu xác nhận policy có lợi ngoài dev:

| Metric test local | W4-02 baseline | E11 rank-aware | Chênh lệch |
| --- | ---: | ---: | ---: |
| Accuracy | 61,43% | **64,96%** | +3,53 điểm % |
| Macro-F1 | 59,49% | **62,94%** | +3,45 điểm % |
| F1 REFUTED | 48,03% | **49,81%** | +1,78 điểm % |
| F1 NEI | 61,68% | **67,32%** | +5,64 điểm % |
| Citation URL-match | 81,13% | **92,19%** | +11,06 điểm % |

Artifact xác nhận: `outputs/metrics/e11_rank_aware_local_end_to_end_test.json` và `outputs/predictions/e11_rank_aware_local_end_to_end_test.csv`. Baseline W4-02 vẫn được giữ nguyên để so sánh.

## Điều cần lưu ý

Đây không giải quyết passage relevance hay web retrieval. Nó chỉ là policy đã chứng minh cải thiện trên dev. Đánh giá test sau policy này là báo cáo xác nhận, không được quay lại để chọn lại grid.
