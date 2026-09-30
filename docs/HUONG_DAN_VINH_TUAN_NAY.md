# Hướng dẫn Vinh làm nốt — theo thứ tự

Ngày: 2026-09-29. Toàn bộ file cần đã có sẵn trong repo. Làm theo đúng thứ tự dưới đây. Ước lượng: 1 buổi GPU + ~4 giờ CPU/đọc tay.

Trước khi bắt đầu: **xóa thư mục "Claude outputs" trong repo** (chứa bản .xlsx cũ hay bị lưu đè nhầm). Bản workbook đúng duy nhất là file ở gốc repo.

---

## NGÀY 1 — Buổi GPU (Kaggle)

### Bước 1: W5-04 — hai lượt fine-tune đối chứng

Cùng một cell trong `docs/KAGGLE_RETRIEVAL_FINETUNE_V1.md`, chạy hai lượt, chỉ đổi 3 dòng đầu.

**Lượt A — gold-only (E15):**
```python
DATA_INPUT = Path("/kaggle/input/<ten>/retrieval_finetune_v1.zip")
MODEL_DIR  = Path("/kaggle/input/<ten-model>/best_model")   # E2 GỐC, không phải rt_v1_silver
OUTPUT_DIR = Path("/kaggle/working/rt_v1_gold_control")
TRAIN_FILE = "gold_train.parquet"        # 5.075 cặp gold, KHÔNG silver
```

**Lượt B — RT-V2 balanced (E16):**
```python
DATA_INPUT = Path("/kaggle/input/<ten-v2>/retrieval_finetune_v2_balanced.zip")
MODEL_DIR  = Path("/kaggle/input/<ten-model>/best_model")   # vẫn E2 GỐC
OUTPUT_DIR = Path("/kaggle/working/rt_v2_balanced")
TRAIN_FILE = "train.parquet"             # 5.201 cặp: gold + 126 silver cân bằng
```

Giữ nguyên seed, epochs, thân cell. Bật GPU + Internet.

**Tải checkpoint về máy:** đặt vào `models/rt_v1_gold_control/best_model` và `models/rt_v2_balanced/best_model`. KHÔNG đè `models/e2_phobert` hay `models/rt_v1_silver`.

---

## NGÀY 2 — CPU (~1 giờ), không cần GPU

### Bước 2: Đo end-to-end 3 checkpoint trên dev, cùng policy

Tạo 2 config sao từ `configs/rt_v1_silver.yaml`, chỉ đổi `model_path` thành `rt_v1_gold_control` và `rt_v2_balanced`. Rồi:

```powershell
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v1_gold_control.yaml --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v1_gold_control_e2e_dev.json --predictions outputs/predictions/rt_v1_gold_control_e2e_dev.csv
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v2_balanced.yaml      --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v2_balanced_e2e_dev.json      --predictions outputs/predictions/rt_v2_balanced_e2e_dev.csv
```

**Luôn truyền `--split .../dev.parquet`** (mặc định script là test). **Không** chạy `audit_accuracy_gap.py`/`calibrate_aggregation_guard.py` cho các checkpoint mới — chúng đọc cache E2 cũ.

### Điểm quyết định — điền bảng này rồi chọn:

| Ứng viên | Acc dev | Macro-F1 | F1 REFUTED | Tỷ lệ NEI |
|---|---|---|---|---|
| E2 nguyên bản | 64,35% | 62,66% | 52,50% | 30,28% |
| RT-V1 silver | 72,31% | 71,35% | 61,40% | 40,93% |
| RT-V1 gold-only | ? | ? | ? | ? |
| RT-V2 balanced | ? | ? | ? | ? |

- gold-only ≈ RT-V1 silver → **nhãn silver không đóng góp**; báo cáo dùng gold-only (sạch hơn, không phải bảo vệ nhãn AI).
- RT-V2 có **F1 REFUTED cao hơn + NEI thấp hơn** → chọn RT-V2.
- Đừng chọn theo accuracy tổng: ưu tiên **F1 REFUTED** và **NEI không phình**.

### Bước 3: W5-05 — khóa checkpoint được chọn vào config

Sau khi chọn, tạo cache dev mới cho checkpoint đó, hiệu chỉnh lại temperature/ngưỡng, fit lại aggregator, rồi sửa `configs/config.yaml`. Chi tiết trong `docs/VIEC_CON_LAI_VINH.md` (Runbook W5-05). Chỉ đổi `config.yaml` sau khi đã khóa cả verifier lẫn policy.

---

## NGÀY 2 (tiếp) — W4-06 + eval reranked, ~30 phút CPU

### Bước 4: W4-06 — fit content-risk

```powershell
py -3.13 scripts/fit_content_risk_model.py
py -3.13 -m pytest tests/test_content_risk.py -q
```
Ra `models/e9_content_risk/`. (Chi tiết + 3 quy tắc hiển thị: `docs/W4_06_CONTENT_RISK_INTEGRATION.md`)

### Bước 5: W4-05/W5-02 — đo reranked-local + dựng bảng 3 tầng

```powershell
py -3.13 scripts/evaluate_reranked_end_to_end.py --config configs/reranked_end_to_end.yaml --split data/processed/vifactcheck_group_split/test.parquet --metrics outputs/metrics/reranked_e2e_test.json --predictions outputs/predictions/reranked_e2e_test.csv

py -3.13 scripts/build_evaluation_comparison.py --tier "Oracle E2=outputs/metrics/e2_phobert_metrics.json" --tier "BM25-local=outputs/metrics/w4_02_local_end_to_end_test.json" --tier "Reranked-local=outputs/metrics/reranked_e2e_test.json" --output docs/W5_02_EVALUATION_COMPARISON.md
```
Trả lời: rerank của Quang có nâng verdict không, hay chỉ đẹp ở tầng retrieval. (Chi tiết: `docs/W5_02_04_05_RUNBOOK.md`)

---

## NGÀY 3 — Đọc tay (~3 giờ), không cần máy mạnh

Làm được cả trên laptop thường. **Quan trọng: đừng mở file `_key.csv` trước khi điền xong.**

### Bước 6: W5-06 — phân xử + spot-check nhãn silver

Điền hai file trong `data/evaluation/`:
- `train_pair_human_adjudication_v1_worksheet.csv` (53 dòng) — điền `reviewed_pair_label`, `reviewer`, `review_reason`
- `train_pair_silver_spotcheck_v1_worksheet.csv` (50 dòng) — điền `reviewed_pair_label`

Chấm:
```powershell
py -3.13 scripts/score_review_worksheets.py --adjudication data/evaluation/train_pair_human_adjudication_v1_worksheet.csv --output outputs/metrics/w5_06_adjudication.json
py -3.13 scripts/score_review_worksheets.py --spotcheck data/evaluation/train_pair_silver_spotcheck_v1_worksheet.csv --key data/evaluation/train_pair_silver_spotcheck_v1_key.csv --output outputs/metrics/w5_06_spotcheck.json
```
Ra **Cohen's kappa** người–AI. Kappa < 0,40 ở nhóm SUP/REF → nhãn silver không đủ tin, chuyển sang trình bày RT-V2/gold-only làm chính.

### Bước 7: W5-03a — audit citation 50 mẫu

Điền `data/evaluation/citation_faithfulness_audit_v1_worksheet.csv`: mỗi dòng có claim + đoạn được trích, điền `doan_co_du_de_ket_luan` (CO/KHONG/KHONG_CHAC), `nhan_dung_theo_doan_nay`, `ly_do`.
```powershell
py -3.13 scripts/score_review_worksheets.py --citation data/evaluation/citation_faithfulness_audit_v1_worksheet.csv --key data/evaluation/citation_faithfulness_audit_v1_key.csv --output outputs/metrics/w5_03a_citation_audit.json
```
Đây là phép đo passage-level đầu tiên — cho biết proxy URL-level đáng tin đến đâu.

### Tiêu chí gán nhãn (áp cho cả bước 6 và 7)
- **SUPPORTED**: passage đủ căn cứ cho mọi ý quan trọng (thực thể, số, thời điểm).
- **REFUTED**: có mâu thuẫn xác định (đảo số, sai ngày, phủ định đổi chiều). Thiếu thông tin ≠ REFUTED.
- **NEI**: thiếu một ý quan trọng, hoặc nói về trường hợp khác.

---

## NGÀY 4 — Khép báo cáo

### Bước 8: Điền số thật vào `docs/BAO_CAO_KET_QUA_GIOI_HAN.md`
Các bảng đã chừa chỗ cho: gold-only/RT-V2 (bước 2), reranked-local (bước 5), kappa nhãn silver (bước 6), citation faithfulness (bước 7).

### Bước 9: Cập nhật workbook
Sau mỗi bước, đánh dấu dòng tương ứng "Hoàn thành" trong `KE_HOACH_TRIEN_KHAI_2_NGUOI.xlsx`: W5-04, W5-05, W5-06, W5-03, W4-05, W5-02, W4-06.

---

## Việc CHỜ Quang (không tự làm được)
- **Fusion local+web** → mở tầng web/hybrid trong W4-05. Hỏi Quang có làm tuần này không.
- **W5-01** (retrieval metrics: Recall/MRR/nDCG cho rerank).
- **W4-04** demo, **W6-01** release, **W6-03** đóng gói.

## Việc CẦN HAI NGƯỜI
- **Bộ gold thực tế ≥300 claim** (C6/E13) — cần 2 reviewer độc lập. Một mình chỉ chuẩn bị được tiêu chí chọn claim + template. Đây là thứ duy nhất cho phép tuyên bố mốc 80%.

---

## Thứ tự ưu tiên nếu thiếu thời gian
1. **Bước 1 (GPU)** — chặn nhiều nhất, người khác không làm thay.
2. **Bước 4 + 5** — 30 phút, đóng W4-06 và mở bảng 3 tầng.
3. **Bước 6–7** — ra con số kappa và citation faithfulness mà hội đồng chắc chắn hỏi.
4. Bước 8–9 — khép báo cáo.
