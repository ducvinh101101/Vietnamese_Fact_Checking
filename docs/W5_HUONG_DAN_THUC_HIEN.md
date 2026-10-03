# Hướng dẫn thực hiện tuần 5 — phần Vinh

Ngày lập: 2026-09-14. Bao gồm W5-04 (hai lượt GPU), W5-06 và W5-03a (đọc tay). Không đụng phần Quang.

Thứ tự bắt buộc: **W5-04 → W5-05**. W5-06 và W5-03a chạy xen kẽ được vì chỉ cần đọc.

---

## W5-04 — Hai lượt fine-tune đối chứng

Mục tiêu không phải "làm model tốt hơn". Mục tiêu là **trả lời được câu hỏi: phần cải thiện +8,7 điểm của RT-V1 đến từ nhãn silver hay chỉ từ việc huấn luyện thêm?** Hiện chưa trả lời được vì lượt control đang dùng là E2 nguyên bản, không phải E2 được train tiếp.

Cả hai lượt dùng **cùng một cell** trong [KAGGLE_RETRIEVAL_FINETUNE_V1.md](KAGGLE_RETRIEVAL_FINETUNE_V1.md), chỉ đổi ba dòng đầu.

### Lượt 1 — đối chứng gold-only (E15)

```python
DATA_INPUT      = Path("/kaggle/input/TEN_DATASET/retrieval_finetune_v1.zip")
MODEL_DIR       = Path("/kaggle/input/TEN_DATASET_MODEL/best_model")   # E2 goc
OUTPUT_DIR      = Path("/kaggle/working/rt_v1_gold_control")
TRAIN_FILE      = "gold_train.parquet"      # 5.075 cap gold, KHONG co silver
EXPERIMENT_NAME = "RT-V1-GOLD"
EPOCHS          = 2
MAX_STEPS       = -1
```

### Lượt 2 — RT-V2 balanced (E16)

```python
DATA_INPUT      = Path("/kaggle/input/TEN_DATASET_V2/retrieval_finetune_v2_balanced.zip")
MODEL_DIR       = Path("/kaggle/input/TEN_DATASET_MODEL/best_model")   # van la E2 goc
OUTPUT_DIR      = Path("/kaggle/working/rt_v2_balanced")
TRAIN_FILE      = "train.parquet"           # 5.201 cap: 5.075 gold + 126 silver can bang
EXPERIMENT_NAME = "RT-V2-balanced"
EPOCHS          = 2
MAX_STEPS       = -1
```

Bundle V2 đã đóng gói sẵn: 126 cặp silver thay vì 487, lấy tối đa 42 cặp mỗi nhãn, nên phân bố nhãn còn 1.815 / 1.703 / 1.683 thay vì lệch 82,3% NEI.

### Bốn điều phải giữ nguyên giữa hai lượt

1. `MODEL_DIR` luôn là **E2 gốc**, không phải `rt_v1_silver`. Train tiếp từ RT-V1 là thí nghiệm khác.
2. Cùng `EPOCHS`, cùng seed, không sửa gì trong thân cell.
3. `OUTPUT_DIR` mới mỗi lượt — cell sẽ báo lỗi nếu thư mục đã có nội dung, đó là chủ ý.
4. Bật GPU, bật Internet cho lần tải VnCoreNLP đầu tiên.

### Sau khi tải checkpoint về máy

Đặt vào `models/rt_v1_gold_control/best_model` và `models/rt_v2_balanced/best_model`. **Không ghi đè** `models/e2_phobert` hay `models/rt_v1_silver`.

Tạo hai config sao chép từ `configs/rt_v1_silver.yaml`, chỉ đổi `model_path`, rồi đo trên dev với **cùng một policy cố định** cho cả ba ứng viên:

```powershell
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v1_gold_control.yaml --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v1_gold_control_e2e_dev.json --predictions outputs/predictions/rt_v1_gold_control_e2e_dev.csv
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v2_balanced.yaml      --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v2_balanced_e2e_dev.json      --predictions outputs/predictions/rt_v2_balanced_e2e_dev.csv
```

**Luôn truyền `--split .../dev.parquet`** — mặc định của script là test.

### Bảng cần điền để kết luận

| Ứng viên | Accuracy dev | Macro-F1 | F1 REFUTED | Tỷ lệ NEI |
|---|---:|---:|---:|---:|
| E2 nguyên bản | 64,35% | 62,66% | 52,50% | 30,28% |
| RT-V1 silver (ngưỡng 0,5) | 72,31% | 71,35% | 61,40% | 40,93% |
| RT-V1 gold-only | | | | |
| RT-V2 balanced | | | | |

Cách đọc kết quả:

- **Nếu gold-only ≈ RT-V1 silver** → nhãn silver không đóng góp gì; cải thiện đến từ việc huấn luyện thêm trên passage truy xuất. Kết luận này vẫn có giá trị khoa học, và còn sạch hơn vì không phải bảo vệ nhãn AI.
- **Nếu gold-only < RT-V1 silver rõ rệt** → nhãn silver có đóng góp thật, khi đó W5-06 trở thành bắt buộc để chứng minh chất lượng nhãn.
- **Nếu RT-V2 có F1 REFUTED cao hơn và tỷ lệ NEI thấp hơn RT-V1** → xác nhận giả thuyết lệch NEI, chọn RT-V2.

Đừng chọn ứng viên chỉ vì accuracy tổng cao hơn. Ưu tiên **F1 REFUTED** và **tỷ lệ NEI không phình**, vì accuracy có thể tăng nhờ abstain nhiều hơn mà không hiểu hơn.

---

## W5-06 — Đọc tay 103 cặp

Hai worksheet, đều đã ẩn nhãn gốc và `annotated_evidence` để không bị dẫn dắt.

### a) Phân xử 53 cặp chưa chắc

`data/evaluation/train_pair_human_adjudication_v1_worksheet.csv`

Điền ba cột: `reviewed_pair_label` (SUPPORTED / REFUTED / NOT_ENOUGH_INFO), `reviewer`, `review_reason`. Cột `ai_note` ghi sẵn lý do AI thấy khó — đọc sau khi tự quyết, không đọc trước.

### b) Spot-check 50 cặp silver

`data/evaluation/train_pair_silver_spotcheck_v1_worksheet.csv`

Chỉ điền `reviewed_pair_label`. Nhãn AI nằm ở file `_key.csv` riêng — **không mở cho tới khi điền xong**. Mẫu lấy 20 SUPPORTED / 20 REFUTED / 10 NEI và đã xáo thứ tự, nên đừng suy đoán nhãn từ vị trí dòng.

### Tiêu chí gán nhãn — giữ đúng như lượt AI-review

- Đơn vị là **claim đầy đủ + đúng một passage**. Không ghép thông tin từ passage khác, không dùng kiến thức ngoài.
- **SUPPORTED**: passage đủ căn cứ cho mọi ý quan trọng — thực thể, số liệu, thời điểm, điều kiện. Chấp nhận diễn đạt tương đương.
- **REFUTED**: có mâu thuẫn xác định trong cùng sự việc (đảo số, sai ngày, sai tuổi, phủ định đổi chiều). **Thiếu thông tin không phải REFUTED.**
- **NEI**: thiếu một ý quan trọng, hoặc passage nói về trường hợp khác. Không có nghĩa claim sai ngoài đời.

### Chấm điểm

```powershell
py -3.13 scripts/score_review_worksheets.py --adjudication data/evaluation/train_pair_human_adjudication_v1_worksheet.csv --output outputs/metrics/w5_06_adjudication.json
py -3.13 scripts/score_review_worksheets.py --spotcheck data/evaluation/train_pair_silver_spotcheck_v1_worksheet.csv --key data/evaluation/train_pair_silver_spotcheck_v1_key.csv --output outputs/metrics/w5_06_spotcheck.json
```

Script trả tỷ lệ đồng thuận, Cohen's kappa, đồng thuận theo từng nhãn và ma trận AI–người. Dòng chưa điền được báo riêng, không tính vào.

Ngưỡng tham khảo khi đọc kappa: dưới 0,40 là yếu, 0,40–0,60 trung bình, 0,60–0,80 khá, trên 0,80 tốt. Nếu kappa thấp trên nhóm SUPPORTED/REFUTED thì nhãn silver **không** đủ tin cậy để bảo vệ trong báo cáo, và nên chuyển sang trình bày RT-V2 hoặc gold-only làm kết quả chính.

---

## W5-03a — Audit citation 50 mẫu

`data/evaluation/citation_faithfulness_audit_v1_worksheet.csv`

Đây là **phép đo passage-level đầu tiên** của dự án. Mọi con số citation từ trước tới nay đều là URL-level: đúng bài báo, chưa biết đúng đoạn.

Mẫu gồm 50 kết luận quyết đoán của RT-V1 tuned — 26 REFUTED, 24 SUPPORTED — trong đó **16 mẫu có citation không khớp URL annotation**, cố ý giữ lại vì đó là nhóm nhiều thông tin nhất.

Mỗi dòng có: claim, dự đoán của hệ thống, và **nguyên văn đoạn được trích dẫn**. Điền ba cột:

| Cột | Giá trị | Nghĩa |
|---|---|---|
| `doan_co_du_de_ket_luan` | `CO` / `KHONG` / `KHONG_CHAC` | Chỉ đọc đoạn này, nó có đủ để đưa ra kết luận mà hệ thống đã đưa không? |
| `nhan_dung_theo_doan_nay` | SUPPORTED / REFUTED / NOT_ENOUGH_INFO | Theo bạn, đoạn này thực sự nói gì về claim? |
| `ly_do` | văn bản | Một câu |

Câu hỏi cần tự nhắc: *"Nếu chỉ đưa người đọc đúng đoạn này, họ có kết luận như hệ thống không?"* Nếu phải mở URL ra đọc thêm mới hiểu thì đó là `KHONG`.

```powershell
py -3.13 scripts/score_review_worksheets.py --citation data/evaluation/citation_faithfulness_audit_v1_worksheet.csv --key data/evaluation/citation_faithfulness_audit_v1_key.csv --output outputs/metrics/w5_03a_citation_audit.json
```

Kết quả trả tỷ lệ faithful kèm Wilson 95%, tách theo nhãn dự đoán, và **đối chiếu URL-match với faithfulness** — chính là con số cho phép nói URL-level proxy đáng tin đến mức nào. Đó là một phát hiện có giá trị báo cáo bất kể kết quả ra sao.

---

## Ghi chú chung

Cả ba việc đọc tay đều là **một người đọc một lượt**, không phải hai reviewer độc lập. Trong báo cáo phải ghi đúng như vậy; nó khác với bộ gold thực tế (C6) vốn yêu cầu hai người. Đừng gọi kết quả của W5-06 và W5-03a là gold.
