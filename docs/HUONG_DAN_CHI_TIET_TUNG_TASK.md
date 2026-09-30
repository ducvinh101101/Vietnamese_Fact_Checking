# Hướng dẫn chi tiết từng task — phần Vinh

Ngày: 2026-09-30. Mỗi task là một mục tự chứa: mục tiêu, tiền đề, lệnh chính xác, kết quả kỳ vọng, cách kiểm tra, điểm quyết định, lỗi thường gặp, cách đánh dấu hoàn thành. Chạy trên PowerShell trong thư mục gốc repo. Python là `py -3.13`.

Chú thích lặp lại: **luôn truyền `--split .../dev.parquet` hoặc `.../test.parquet`** — nhiều script mặc định test. **Không mở file `_key.csv`** trước khi điền xong worksheet.

---

# TASK W5-04 — Hai lượt fine-tune đối chứng (GPU)

**Mục tiêu.** Trả lời một câu duy nhất: phần cải thiện +8,7 điểm Macro-F1 của RT-V1 đến từ *nhãn silver* hay chỉ từ *huấn luyện thêm 2 epoch*? Và bản cân bằng nhãn (RT-V2) có sửa được lệch NEI không?

**Tiền đề.** Có tài khoản Kaggle + GPU. Hai dataset đã đóng gói: `kaggle/retrieval_finetune_v1.zip` và `kaggle/retrieval_finetune_v2_balanced.zip`. Model E2 gốc để làm điểm xuất phát.

**Vì sao bắt buộc.** Hiện `models/` chỉ có `rt_v1_silver`. Cái đang gọi là "control" là **E2 nguyên bản**, không phải E2 được train tiếp trên gold. Thiếu lượt gold-only thì không tách được nguyên nhân — hội đồng sẽ hỏi đúng chỗ này.

**Các bước.** Mở `docs/KAGGLE_RETRIEVAL_FINETUNE_V1.md`, dùng cell fine-tune. Chạy **hai lượt**, chỉ đổi 5 dòng đầu cell:

Lượt A — gold-only:
```python
DATA_INPUT      = Path("/kaggle/input/<ten-dataset>/retrieval_finetune_v1.zip")
MODEL_DIR       = Path("/kaggle/input/<ten-model>/best_model")   # E2 GỐC
OUTPUT_DIR      = Path("/kaggle/working/rt_v1_gold_control")
TRAIN_FILE      = "gold_train.parquet"       # 5.075 cặp gold, KHÔNG silver
EXPERIMENT_NAME = "RT-V1-GOLD"
```

Lượt B — RT-V2 balanced:
```python
DATA_INPUT      = Path("/kaggle/input/<ten-dataset-v2>/retrieval_finetune_v2_balanced.zip")
MODEL_DIR       = Path("/kaggle/input/<ten-model>/best_model")   # vẫn E2 GỐC
OUTPUT_DIR      = Path("/kaggle/working/rt_v2_balanced")
TRAIN_FILE      = "train.parquet"            # 5.201 cặp: gold + 126 silver cân bằng
EXPERIMENT_NAME = "RT-V2-balanced"
```

Giữ nguyên `EPOCHS`, seed, và toàn bộ thân cell. Bật GPU + Internet (cho lần tải VnCoreNLP đầu).

**Kết quả kỳ vọng.** Hai thư mục checkpoint trong `/kaggle/working/`. Tải về máy, đặt vào `models/rt_v1_gold_control/best_model` và `models/rt_v2_balanced/best_model`.

**Kiểm tra.** Mỗi thư mục có `config.json`, file trọng số, tokenizer. `models/e2_phobert` và `models/rt_v1_silver` **không đổi**.

**Lỗi thường gặp.**
- Lỡ để `MODEL_DIR` trỏ `rt_v1_silver` → thành "train chồng train", sai thí nghiệm. Phải là E2 gốc.
- Quên bật GPU → cell báo lỗi ngay (đã có `raise` kiểm tra).
- `OUTPUT_DIR` trùng thư mục đã có nội dung → cell từ chối (đúng chủ ý, đổi tên).

**Đánh dấu hoàn thành:** sau khi cả hai checkpoint về máy. (Đo dev là TASK tiếp theo.)

---

# TASK W5-04-eval — Đo 3 checkpoint trên dev và chọn (CPU)

**Mục tiêu.** Chọn checkpoint tốt nhất bằng số dev, cùng một policy cố định.

**Tiền đề.** Đã có `models/rt_v1_gold_control`, `models/rt_v2_balanced`. Hai config đã tạo sẵn: `configs/rt_v1_gold_control.yaml`, `configs/rt_v2_balanced.yaml` (trỏ đúng model, dùng rank policy bias=1, ngưỡng 0,5, không AGG).

**Các bước.**
```powershell
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v1_gold_control.yaml --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v1_gold_control_e2e_dev.json --predictions outputs/predictions/rt_v1_gold_control_e2e_dev.csv
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v2_balanced.yaml      --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v2_balanced_e2e_dev.json      --predictions outputs/predictions/rt_v2_balanced_e2e_dev.csv
```
Mỗi lệnh ~13 phút CPU (1.080 claim). In ra `{"macro_f1": ..., "queries": 1080}` khi xong.

**Kết quả kỳ vọng.** 4 file: 2 JSON metrics + 2 CSV predictions.

**Điểm quyết định — điền bảng, chọn checkpoint:**

| Ứng viên | Acc dev | Macro-F1 | F1 REFUTED | Tỷ lệ NEI |
|---|---|---|---|---|
| E2 nguyên bản | 64,35% | 62,66% | 52,50% | 30,28% |
| RT-V1 silver | 72,31% | 71,35% | 61,40% | 40,93% |
| RT-V1 gold-only | ___ | ___ | ___ | ___ |
| RT-V2 balanced | ___ | ___ | ___ | ___ |

Luật chọn:
- **gold-only ≈ RT-V1 silver** (chênh < ~1 điểm) → nhãn silver không đóng góp. Chọn gold-only, báo cáo sạch hơn (không phải bảo vệ nhãn AI).
- **RT-V2 F1 REFUTED cao hơn + NEI thấp hơn** RT-V1 → chọn RT-V2 (đã sửa lệch NEI).
- Không chọn theo accuracy tổng: ưu tiên **F1 REFUTED** rồi **NEI không phình**.

**Lỗi thường gặp.** Quên `--split dev` → chạy nhầm test (cấm, test chỉ dùng một lần cuối). Trùng tên file output → script cũ có thể ghi đè, đặt tên mới mỗi lượt.

**Đánh dấu hoàn thành W5-04** sau khi có bảng và đã chọn checkpoint.

---

# TASK W5-05 — Khóa checkpoint vào config (CPU)

**Mục tiêu.** Đưa checkpoint được chọn thành runtime chính thức.

**Tiền đề.** Đã chọn ở TASK trên. Giả sử chọn `rt_v1_silver` (nếu chọn khác, thay tên tương ứng và đảm bảo đã có `configs/<tên>.yaml`).

**Bước 1 — kiểm policy trên dev cho checkpoint được chọn:**
```powershell
py -3.13 scripts/tune_local_end_to_end_policy.py --config configs/rt_v1_silver.yaml --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v1_silver_policy_dev.json --predictions outputs/predictions/rt_v1_silver_policy_dev.csv
```
Script chọn `rank_bias` và `decisive_min_confidence` trên dev. Đọc `selected` trong JSON in ra.

**Bước 2 — khóa vào `configs/config.yaml`:** mở `configs/config.yaml`, sửa khối `verification` cho khớp checkpoint + policy đã chọn. Với `rt_v1_silver` là:
```yaml
verification:
  engine: phobert
  model_path: models/rt_v1_silver/best_model
  vncorenlp_dir: models/vncorenlp
  max_length: 256
  temperature: 1.0
  decisive_min_confidence: 0.5     # hoặc giá trị script vừa chọn
  retrieval_rank_bias: 1.0
  aggregation_model_path: null     # RT-V1 dùng rank policy, KHÔNG dùng AGG-V1 cũ
  support_threshold: 0.45
  refute_markers: [ "không", "chưa", "sai", "bác bỏ", "trái ngược" ]
```

**Rất quan trọng — KHÔNG làm:**
- **Không** đặt lại `aggregation_model_path: models/aggregation/dev_logistic_v1.json`. AGG-V1 fit trên logits E2 cũ, dùng cho checkpoint mới sẽ sai.
- **Không** chạy `audit_accuracy_gap.py` hay `calibrate_aggregation_guard.py` để đánh giá checkpoint mới — chúng đọc cache E2 cũ và có thể ghi đè AGG đang dùng.

**Kiểm tra.** Chạy app hoặc một smoke: verdict + citation ra bình thường, không lỗi. Test cũ không dùng để chọn lại.

**Đánh dấu hoàn thành W5-05** sau khi `config.yaml` khóa và smoke chạy.

---

# TASK W4-06 — Fit và nối content-risk (CPU)

**Mục tiêu.** Sinh model content-risk E9 triển khai được, để hiển thị điểm rủi ro cấp bài (tách khỏi verdict).

**Tiền đề.** `data/processed/vfnd_content/articles.parquet` có sẵn. Code + test đã ghi trong repo (`src/content_risk.py`, `scripts/fit_content_risk_model.py`, `tests/test_content_risk.py`).

**Các bước.**
```powershell
py -3.13 scripts/fit_content_risk_model.py
py -3.13 -m pytest tests/test_content_risk.py -q
```
Lệnh 1 (~30 giây CPU) in ra `Đã lưu model content-risk vào models/e9_content_risk (C=..., 221 bài).` Lệnh 2 phải báo 5 passed.

**Kết quả kỳ vọng.** `models/e9_content_risk/model.joblib` + `metadata.json`.

**Nối vào UI (khi dựng cùng W4-01 của Quang):**
```python
from src.content_risk import ContentRiskScorer
scorer = ContentRiskScorer.load("models/e9_content_risk")
article_pipeline = ArticleFactCheckingPipeline(claim_runner, content_risk_scorer=scorer)
```

**Ba quy tắc hiển thị bắt buộc** (chi tiết `docs/W4_06_CONTENT_RISK_INTEGRATION.md`):
1. Không hiện số thập phân — chỉ dải thấp/trung bình/cao.
2. Gắn cờ `out_of_distribution_source` cho nguồn ngoài 29 domain huấn luyện.
3. Tách hẳn khỏi khối verdict, khác màu, kèm câu disclaimer cố định.

**Lỗi thường gặp.** Thiếu `joblib`/`scikit-learn` → `pip install scikit-learn joblib`. Nếu parquet lỗi engine → `pip install pyarrow`.

**Đánh dấu hoàn thành** sau khi có model + test pass. (Nối UI hoàn tất chung với W4-01.)

---

# TASK W4-05 / W5-02 — Đo reranked-local + bảng 3 tầng (CPU)

**Mục tiêu.** Trả lời: rerank của Quang có nâng verdict end-to-end không? Và dựng bảng so sánh oracle / BM25-local / reranked-local.

**Tiền đề.** Corpus v2 (Quang, đã xong). Script + config đã ghi: `scripts/evaluate_reranked_end_to_end.py`, `configs/reranked_end_to_end.yaml`, `scripts/build_evaluation_comparison.py`.

**Bước 1 — đo reranked-local trên test (một lần):**
```powershell
py -3.13 scripts/evaluate_reranked_end_to_end.py --config configs/reranked_end_to_end.yaml --split data/processed/vifactcheck_group_split/test.parquet --metrics outputs/metrics/reranked_e2e_test.json --predictions outputs/predictions/reranked_e2e_test.csv
```
Nếu file corpus v2 tên khác `data/evidence/vifactcheck_passages.jsonl`, sửa `paths.evidence_path` trong `configs/reranked_end_to_end.yaml` trước.

**Bước 2 — dựng bảng 3 tầng:**
```powershell
py -3.13 scripts/build_evaluation_comparison.py --tier "Oracle E2=outputs/metrics/e2_phobert_metrics.json" --tier "BM25-local=outputs/metrics/w4_02_local_end_to_end_test.json" --tier "Reranked-local=outputs/metrics/reranked_e2e_test.json" --output docs/W5_02_EVALUATION_COMPARISON.md
```

**Điểm quyết định.** So Reranked-local với BM25-local: nếu Macro-F1 và F1 REFUTED tăng, latency vẫn hợp demo → giữ rerank. Nếu không đổi → giữ BM25, ghi rõ (như đã làm với dense ở W2-04).

**Giới hạn.** Đây **không** phải web/hybrid — chưa có fusion. Bảng chỉ gồm tầng local. (Chi tiết `docs/W5_02_04_05_RUNBOOK.md`.)

**Đánh dấu hoàn thành W4-05 (phần reranked) và W5-02** sau khi có bảng.

---

# TASK W5-06 — Phân xử + spot-check nhãn silver (đọc tay)

**Mục tiêu.** Ra con số **đồng thuận người–AI** (Cohen's kappa) — hiện chưa hề tồn tại, mà hội đồng chắc chắn hỏi khi nghe "nhãn AI".

**Tiền đề.** Không cần máy mạnh, làm được trên laptop. Hai worksheet trong `data/evaluation/`.

**Bước 1 — điền 53 cặp phân xử:** mở `train_pair_human_adjudication_v1_worksheet.csv`, mỗi dòng đọc `claim` + `passage`, điền:
- `reviewed_pair_label`: SUPPORTED / REFUTED / NOT_ENOUGH_INFO
- `reviewer`: tên bạn
- `review_reason`: một câu lý do

**Bước 2 — điền 50 cặp spot-check:** mở `train_pair_silver_spotcheck_v1_worksheet.csv`, chỉ điền `reviewed_pair_label`. **Tuyệt đối không mở** `train_pair_silver_spotcheck_v1_key.csv` cho tới khi điền xong.

**Tiêu chí gán nhãn:**
- **SUPPORTED**: passage đủ căn cứ cho MỌI ý quan trọng (thực thể, số liệu, thời điểm, điều kiện). Chấp nhận diễn đạt tương đương.
- **REFUTED**: có mâu thuẫn xác định trong cùng sự việc (đảo số, sai ngày, sai tuổi, phủ định đổi chiều). **Thiếu thông tin KHÔNG phải REFUTED.**
- **NEI**: thiếu một ý quan trọng, hoặc passage nói về trường hợp khác.

**Bước 3 — chấm:**
```powershell
py -3.13 scripts/score_review_worksheets.py --adjudication data/evaluation/train_pair_human_adjudication_v1_worksheet.csv --output outputs/metrics/w5_06_adjudication.json
py -3.13 scripts/score_review_worksheets.py --spotcheck data/evaluation/train_pair_silver_spotcheck_v1_worksheet.csv --key data/evaluation/train_pair_silver_spotcheck_v1_key.csv --output outputs/metrics/w5_06_spotcheck.json
```

**Đọc kết quả.** `cohen_kappa`: <0,40 yếu, 0,40–0,60 trung bình, 0,60–0,80 khá, >0,80 tốt. **Nếu kappa nhóm SUP/REF < 0,40** → nhãn silver không đủ tin, chuyển sang trình bày RT-V2/gold-only làm kết quả chính.

**Ghi trong báo cáo.** Đây là *một người đọc một lượt*, không phải hai reviewer độc lập — ghi đúng như vậy, không gọi là gold.

**Đánh dấu hoàn thành W5-06** sau khi có 2 file JSON.

---

# TASK W5-03a — Audit citation faithfulness (đọc tay)

**Mục tiêu.** Phép đo **passage-level đầu tiên**: đoạn được trích có thực sự đủ để kết luận không (khác với chỉ khớp URL).

**Tiền đề.** `data/evaluation/citation_faithfulness_audit_v1_worksheet.csv` (50 mẫu). Không mở `_key.csv`.

**Bước 1 — điền:** mỗi dòng có `claim`, `du_doan_cua_he_thong`, và `doan_duoc_trich_dan` (nguyên văn). Điền:
- `doan_co_du_de_ket_luan`: **CO** / **KHONG** / **KHONG_CHAC** — chỉ đọc đoạn này, nó có đủ để đưa ra kết luận hệ thống đã đưa không?
- `nhan_dung_theo_doan_nay`: theo bạn đoạn này thực sự nói gì về claim (3 nhãn)
- `ly_do`: một câu

Tự nhắc: *"Nếu chỉ đưa người đọc đúng đoạn này, họ có kết luận như hệ thống không?"* Phải mở URL đọc thêm mới hiểu → `KHONG`.

**Bước 2 — chấm:**
```powershell
py -3.13 scripts/score_review_worksheets.py --citation data/evaluation/citation_faithfulness_audit_v1_worksheet.csv --key data/evaluation/citation_faithfulness_audit_v1_key.csv --output outputs/metrics/w5_03a_citation_audit.json
```

**Kết quả.** Tỷ lệ faithful + Wilson 95%, tách theo nhãn, và **đối chiếu URL-match với faithfulness** — cho biết proxy URL-level đáng tin đến đâu. Là phát hiện có giá trị bất kể kết quả.

**Đánh dấu hoàn thành W5-03a** sau khi có JSON.

---

# TASK W5-03b — Temporal / source held-out (CPU, tùy chọn nâng cao)

**Mục tiêu.** Kiểm external validity: model có tổng quát sang nguồn/thời điểm chưa thấy không.

**Tiền đề.** Corpus v2 có `published_at`/`source_type`/`domain`. Cần một script chia test theo domain nguồn và theo mốc thời gian rồi chạy lại pipeline từng nhóm. **Script này chưa viết** — nếu cần, nhắn tôi viết (đọc-code được, không cần model để viết). Không bắt buộc cho bản nộp nếu thời gian hẹp.

---

# TASK W6-02 / W4-03 — Khép báo cáo

**Mục tiêu.** Điền số thật vào báo cáo đã soạn.

**Tiền đề.** `docs/BAO_CAO_KET_QUA_GIOI_HAN.md` đã có, các bảng đã chừa chỗ.

**Các bước.** Điền:
- Bảng 2.2/3.3: gold-only, RT-V2 (từ W5-04-eval)
- Bảng 2.2: reranked-local (từ W4-05)
- Mục 3.3: kappa nhãn silver (từ W5-06)
- Mục 4.3: citation faithfulness (từ W5-03a)

Sau đó ghép vào README (W4-03): phần phương pháp + kết quả lấy từ báo cáo này; phần cài đặt/demo phối hợp Quang.

**Gửi tôi các file JSON trong `outputs/metrics/`** (gold_control, rt_v2, reranked, w5_06_*, w5_03a) — tôi khép báo cáo bằng số thật và cập nhật workbook giúp.

---

# Bảng đánh dấu tiến độ (điền dần trong workbook)

| Task | Mã workbook | Xong khi |
|---|---|---|
| Fine-tune 2 lượt | W5-04 | 2 checkpoint về máy + bảng dev đã chọn |
| Khóa config | W5-05 | config.yaml khóa + smoke chạy |
| Content-risk | W4-06 | model E9 + test pass |
| Reranked eval + bảng | W4-05, W5-02 | có W5_02_EVALUATION_COMPARISON.md |
| Nhãn silver | W5-06 | 2 JSON + kappa |
| Citation audit | W5-03a (thuộc W5-03) | JSON faithfulness |
| Báo cáo | W6-02, W4-03 | số thật đã điền |
