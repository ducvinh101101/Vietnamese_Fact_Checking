# Việc còn lại của Vinh — phân loại theo phụ thuộc

Mã giữ nguyên theo workbook `KE_HOACH_TRIEN_KHAI_2_NGUOI.xlsx`; hậu tố a/b là hai lượt chạy trong cùng một dòng kế hoạch.

Ngày lập: 2026-09-12. Chỉ liệt kê hạng mục thuộc phần Vinh (dữ liệu, verifier, calibration, aggregation, đánh giá, báo cáo). Không bao gồm và không can thiệp phần Quang (corpus ingestion, dense/rerank, web retrieval, Streamlit, release).

## A. Chạy được ngay trên máy, không chờ ai

| Mã | Việc | Input đã có | Đầu ra mong đợi |
| --- | --- | --- | --- |
| W5-05 | Re-calibrate và khóa config cho checkpoint được chọn | `models/rt_v1_silver/best_model`, `scripts/tune_local_end_to_end_policy.py` | temperature + ngưỡng mới, aggregator fit lại, `configs/config.yaml` đã khóa |
| W5-06a | Phân xử 53 cặp `needs_human_review` | `data/evaluation/train_pair_human_adjudication_v1_worksheet.csv` | CSV v2 có nhãn người, tên người duyệt, lý do |
| W5-06b | Spot-check 50 cặp silver, tính tỷ lệ đồng thuận người–AI | `data/evaluation/train_pair_silver_spotcheck_v1_worksheet.csv` + `_key.csv` | Con số đồng thuận theo từng nhãn |
| W5-03a | Audit citation faithfulness 50 mẫu | `outputs/predictions/rt_v1_silver_tuned_e2e_dev.csv` | Tỷ lệ passage được trích dẫn thực sự entail claim |
| W5-03b | Temporal / source held-out test | `Url` + thời gian trong ViFactCheck | Báo cáo external validity trên corpus local |
| E11 | Ablation claim decomposition cấp bài | query set v1 frozen, aggregation component | Có/không tách claim trên BM25 local |
| W4-06 | Nối content-risk E9 vào aggregation cấp bài | `models/e1_tfidf_linear_svm.joblib`, E9 metrics | Verdict cấp bài hiển thị kèm risk score, ghi rõ không phải evidence |
| W6-02 | Viết ablation + giới hạn khoa học cho báo cáo cuối | Toàn bộ metrics đã có | Phần báo cáo hoàn chỉnh |

## B. Không chờ người, nhưng cần một lượt GPU

| Mã | Việc | Trạng thái |
| --- | --- | --- |
| W5-04a | Đối chứng gold-only (train tiếp E2 chỉ trên 5.075 cặp gold) | **Chưa chạy.** `models/` chỉ có `rt_v1_silver`. Thiếu lượt này thì không tách được phần cải thiện do nhãn silver với phần do huấn luyện thêm |
| W5-04b | RT-V2 balanced | Bundle `kaggle/retrieval_finetune_v2_balanced.zip` đã đóng gói 2026-09-11, chưa train |

Cả hai dùng chung cell fine-tune trong [KAGGLE_RETRIEVAL_FINETUNE_V1.md](KAGGLE_RETRIEVAL_FINETUNE_V1.md). Nên chạy liền nhau trong một buổi, cùng seed và cấu hình, đổi `TRAIN_FILE` và `OUTPUT_DIR`.

## C. Thuộc phần Vinh nhưng đang thực sự vướng

| Mã | Việc | Vướng ở đâu |
| --- | --- | --- |
| C6 | Bộ gold thực tế ≥300 claim | Kế hoạch yêu cầu hai reviewer độc lập; một mình không khóa được gold. Phần làm được một mình là chuẩn bị tiêu chí chọn claim, template CSV và quy tắc tách sự kiện |
| — | W4-05, W5-01, phần retrieval của W5-02 | Chờ web/hybrid của Quang |

## Runbook W5-05 — re-calibrate và khóa config

Thứ tự bắt buộc. Không đảo.

```powershell
# 1. Tao ban sao config cho ung vien, giu nguyen corpus/BM25/top_k/max_length
#    configs/rt_v1_silver.yaml  -> model_path: models/rt_v1_silver/best_model
#                                  temperature: 1.0, aggregation_model_path: null

# 2. Sinh cache du doan dev moi cho checkpoint duoc chon
py -3.13 scripts/evaluate_local_end_to_end.py `
  --config configs/rt_v1_silver.yaml `
  --split data/processed/vifactcheck_group_split/dev.parquet `
  --metrics outputs/metrics/rt_v1_silver_e2e_dev_v2.json `
  --predictions outputs/predictions/rt_v1_silver_e2e_dev_v2.csv

# 3. Chon temperature + nguong tren dev theo nhom URL
py -3.13 scripts/tune_local_end_to_end_policy.py --config configs/rt_v1_silver.yaml
```

Ba lưu ý:

1. **Luôn truyền `--split .../dev.parquet`** — mặc định của script cũ là test.
2. **Không chạy `audit_accuracy_gap.py` hoặc `calibrate_aggregation_guard.py` cho RT-V1.** Hai script này đọc cache E2 cũ và có thể ghi đè `models/aggregation/dev_logistic_v1.json` đang dùng. AGG-V1 fit trên logits E2 nên không tái sử dụng được cho checkpoint mới; phải fit lại từ cache mới.
3. Dùng đường dẫn output mới cho mỗi lượt; evaluator hiện có thể ghi đè output trùng tên.

Chỉ đổi `configs/config.yaml` sau khi đã khóa cả verifier lẫn policy. Test cũ đã bị xem nhiều lần, không dùng để chọn lại.

## Ghi chú ưu tiên

Theo [phân tích lỗi RT-V1](RT_V1_ERROR_CITATION_ANALYSIS.md): chỉ 7/299 lỗi còn lại đến từ retrieval, và 175/299 lỗi có nhãn vàng REFUTED, trong đó nhóm REFUTED → NEI không sửa được bằng ngưỡng. Vì vậy thứ tự có lợi nhất là **W5-04 → W5-05**, rồi mới tới W5-03 và E11.
