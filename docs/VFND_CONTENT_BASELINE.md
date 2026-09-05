# E9 — Baseline content-risk với VFND article-only

E9 là nhánh phân loại rủi ro ở cấp bài viết, tách hoàn toàn với ViFactCheck verifier. Nó không đưa evidence, không kết luận một claim đúng/sai và không được dùng để gọi một bài viết là “tin giả” trong giao diện fact-checking.

## Dữ liệu và phạm vi

Nguồn là VFND v1.1.1, chỉ lấy `Fake_Real_Dataset/{Fake,Real}/Article_Contents`; social posts bị loại. Dataset được tải bằng:

```powershell
git clone --depth 1 --branch v1.1.1 https://github.com/VFND/VFND-vietnamese-fake-news-datasets.git data/external/vfnd
python scripts/prepare_vfnd_content.py
```

VFND lưu `title`, `text`, `url` và `source_domain`, cùng nhãn article-level `REAL`/`FAKE`. Dataset và output parquet không được commit lại; script, revision, audit và metric được lưu để tái lập. Phải trích dẫn VFND/Zenodo DOI `10.5281/zenodo.6590948` và tuân thủ GPL-3.0 của nguồn.

## Protocol E9

```powershell
python scripts/train_content_baseline.py
```

Input là `[TITLE] title [BODY] body`. Model là TF-IDF word `(1,2)` + character `(3,5)` và calibrated LinearSVC. Do mỗi domain VFND chỉ mang một nhãn, random split sẽ rò tín hiệu source. E9 vì thế dùng nested `StratifiedGroupKFold` theo `source_domain`: 5 outer folds để lấy OOF metric, 3 inner folds để chọn `C`.

Metric chính là OOF Macro-F1; ROC-AUC và score `fake_risk_score` chỉ là supplementary. Dataset nhỏ và lệch domain nên không dùng metric E9 để chọn verifier E2 hay khẳng định hiệu năng trên news web hiện nay.
