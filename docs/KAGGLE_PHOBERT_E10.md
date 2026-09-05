# E10 — PhoBERT content-risk trên VFND article-only

E10 tiếp tục E9 bằng PhoBERT-base. Đây là phân loại article-level `REAL`/`FAKE` trên VFND article-only, không phải verifier ViFactCheck và không sinh evidence/citation.

## Chuẩn bị

```powershell
python scripts/package_vfnd_content_for_kaggle.py
```

Upload `kaggle/vfnd_content.zip` thành Kaggle Dataset riêng tư, đính kèm dataset đó vào notebook GPU và đặt `INPUT_DIR` trong `kaggle/train_phobert_content_risk.py` đúng slug nếu cần.

Kaggle cần GPU và Internet ở lần đầu để tải PhoBERT/VnCoreNLP:

```powershell
pip install -q "transformers>=4.41,<4.47" datasets accelerate py_vncorenlp scikit-learn
python train_phobert_content_risk.py
```

Script chạy nested source-domain CV, calibration temperature trên inner-dev, rồi xuất `e10_phobert_content_metrics.json` và OOF prediction. CSV OOF có cột `fold`; JSON ghi số mẫu và SHA-256 danh sách `article_id` của test set từng fold. Giữ nguyên hai trường này khi tải kết quả về để có thể tái kiểm tra phép chia theo `source_domain`.

Chỉ ghi W2-09 hoàn thành sau khi đưa hai file đã xác minh về `outputs/` và xác nhận Macro-F1/AUC ngoài mẫu.

## Kết quả đã xác minh

E10 chạy trên 221 bài VFND, OOF theo 5 fold tách `source_domain`: Macro-F1 **48,59%**, ROC-AUC **70,20%**. Hai artifact khớp metric, 29 domain không rò rỉ giữa các fold và SHA-256 test set trong JSON khớp CSV. Kết quả thấp hơn E9 (Macro-F1 77,27%; ROC-AUC 88,21%), vì vậy E9 vẫn là baseline content-risk được chọn. E10 chỉ là kết quả so sánh, không phải evidence cho claim.
