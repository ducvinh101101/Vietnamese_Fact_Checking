# Hướng dẫn các việc còn lại cần GPU hoặc người đọc

Ngày: 2026-10-11. Mọi phần code của sản phẩm đã xong; các việc dưới đây **không thể** (hoặc không được phép) làm bằng AI: cần GPU để huấn luyện, hoặc cần người đọc để nhãn có giá trị. Mỗi việc ghi rõ lệnh, thời gian ước tính và cách đưa kết quả vào báo cáo.

Nguyên tắc chung: **chọn cấu hình bằng DEV**, test split chỉ dùng một lần cho báo cáo (đã chạy ngày 2026-10-04, Macro-F1 72,31%). Không chạy lại test để so sánh các checkpoint mới.

---

## 1. Đọc tay (không dùng AI điền nhãn)

| Mã | Worksheet | Số mục | Thời gian | Chấm điểm |
|---|---|---:|---|---|
| W5-06a | `data/evaluation/train_pair_human_adjudication_v1_worksheet.csv` | 53 | ~1,5 giờ | `--adjudication` |
| W5-06b | `data/evaluation/train_pair_silver_spotcheck_v1_worksheet.csv` | 50 | ~1 giờ | `--spotcheck … --key …` |
| W5-03a | `data/evaluation/citation_faithfulness_audit_v1_worksheet.csv` | 50 | ~1,5 giờ | `--citation … --key …` |
| RT-V3 (mới) | `data/processed/retrieval_finetune_v3_hardneg/hard_negative_spotcheck_v3_worksheet.csv` | 60 | ~1,5 giờ | `--spotcheck … --key …` |

Tiêu chí gán nhãn và lệnh chấm cho ba worksheet đầu: [W5_HUONG_DAN_THUC_HIEN.md](W5_HUONG_DAN_THUC_HIEN.md). Worksheet RT-V3 dùng cùng tiêu chí (SUPPORTED / REFUTED / NOT_ENOUGH_INFO cho cặp claim–đoạn), điền `reviewed_pair_label`, `reviewer`, `review_reason`; **không mở file `_key.csv` trước khi đọc xong**.

```powershell
py -3.13 scripts/score_review_worksheets.py --spotcheck data/processed/retrieval_finetune_v3_hardneg/hard_negative_spotcheck_v3_worksheet.csv --key data/processed/retrieval_finetune_v3_hardneg/hard_negative_spotcheck_v3_key.csv --output outputs/metrics/rt_v3_hardneg_spotcheck.json
```

Cách dùng kết quả RT-V3: nếu đồng thuận người–nhãn sinh < 85% ở loại nào (xem `per_ai_label`), bỏ loại đó khỏi bundle (sửa `--per-kind`/`--nei` hoặc lọc `label_origin`) **trước** khi huấn luyện.

---

## 2. GPU (Kaggle, T4/P100)

### 2.1 W5-04 — đối chứng gold-only (tách đóng góp nhãn silver)

Đã có hướng dẫn chi tiết: [W5_HUONG_DAN_THUC_HIEN.md § W5-04](W5_HUONG_DAN_THUC_HIEN.md). Tóm tắt: chạy `kaggle/finetune_phobert_retrieval_v1.py` với `--train-file gold_train.parquet` trên bundle `retrieval_finetune_v2_balanced.zip`, cùng seed/epoch với RT-V2; chép `best_model` về `models/rt_v1_gold_control/best_model`; đánh giá dev:

```powershell
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v1_gold_control.yaml --use-final-config --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v1_gold_control_e2e_dev.json --predictions outputs/predictions/rt_v1_gold_control_e2e_dev.csv
```

### 2.2 RT-V3 — hard negative (sửa nhóm lỗi lớn nhất: REFUTED→SUPPORTED, NEI→quyết đoán)

Bundle đã dựng sẵn và kiểm hash: `kaggle/retrieval_finetune_v3_hardneg.zip` (6.101 cặp = 5.201 của RT-V2 + 900 cặp tổng hợp trọng số 0,5: 150 đổi số, 150 đổi chiều, 150 phủ định, 450 NEI bài-khác; chỉ từ train split). Dựng lại được bằng `py -3.13 scripts/build_hard_negative_finetune_v3.py`.

Trên Kaggle (GPU bật), upload zip làm dataset và checkpoint RT-V2 (`models/rt_v2_balanced/best_model`) làm dataset thứ hai:

```bash
python finetune_phobert_retrieval_v1.py \
  --data-dir /kaggle/input/retrieval-finetune-v3-hardneg \
  --model-dir /kaggle/input/rt-v2-balanced/best_model \
  --output-dir /kaggle/working/rt_v3_hardneg --experiment RT-V3 --epochs 2
```

Khoảng 25–35 phút trên T4. Tải `best_model/` về `models/rt_v3_hardneg/best_model/`, rồi đánh giá **trên dev** với đúng cấu hình cuối (ensemble + minimal-pair):

```powershell
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v3_hardneg.yaml --use-final-config --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v3_hardneg_e2e_dev.json --predictions outputs/predictions/rt_v3_hardneg_e2e_dev.csv
```

### 2.3 Quy tắc quyết định (viết trước khi xem số, để không chọn theo kết quả)

1. So RT-V3 (và gold-only control) với RT-V2 trên **cùng dev, cùng cấu hình cuối** bằng bootstrap ghép cặp. Lượt RT-V2 tham chiếu trên dev (chạy một lần, ~25 phút):

   ```powershell
   py -3.13 scripts/evaluate_local_end_to_end.py --use-final-config --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v2_final_e2e_dev.json --predictions outputs/predictions/rt_v2_final_e2e_dev.csv
   py -3.13 scripts/compare_final_vs_baselines.py --base outputs/predictions/rt_v2_final_e2e_dev.csv --new outputs/predictions/rt_v3_hardneg_e2e_dev.csv --out outputs/metrics/rt_v3_vs_rt_v2_dev.json
   ```
2. Chỉ thay `configs/config.yaml` sang RT-V3 khi Δ Macro-F1 > 0 **và** khoảng tin cậy 95% không chứa 0 **và** F1 SUPPORTED không giảm quá 2 điểm.
3. Nếu thay: ghi rõ trong báo cáo rằng số test 72,31% thuộc RT-V2; số của RT-V3 chỉ có trên dev (test đã dùng). Không chạy lại test để "xác nhận".

---

## 3. Đưa kết quả vào báo cáo

Sau mỗi việc, điền số vào [BAO_CAO_TONG_KET.md](BAO_CAO_TONG_KET.md) § 7 (bảng "Việc cần người/GPU") và cập nhật trạng thái trong [BACKLOG.md](BACKLOG.md). Toàn bộ kiểm tra máy trước khi demo: `py -3.13 scripts/check_release.py --smoke`.
