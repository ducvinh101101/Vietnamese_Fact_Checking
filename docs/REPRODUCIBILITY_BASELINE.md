# Reproducibility baseline — W1-07

W1-07 khóa môi trường local đã kiểm chứng cho MVP, không thay đổi dữ liệu,
checkpoint hoặc pipeline.

## Artefact

- `requirements.lock`: 80 dependency chính xác từ môi trường đã chạy test.
- `outputs/metrics/reproducibility_baseline.json`: commit Git, phiên bản Python,
  nền tảng và SHA-256 của config, corpus, checkpoint PhoBERT và VnCoreNLP.

## Tái lập

Trên Windows với Python 3.11 và Java 17:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python scripts\create_reproducibility_baseline.py --run-tests
```

Lệnh cuối tạo lại lockfile/manifest và chạy `pytest -q`. Chỉ sử dụng artefact
có hash khớp với manifest. Checkpoint cần ở `models/e2_phobert/best_model/` và
VnCoreNLP ở `models/vncorenlp/` như cấu hình hiện tại.

## Kết quả baseline

- `pytest -q`: 102 passed.
- Smoke test PhoBERT với kho evidence mẫu: trả về nhãn và ba evidence.
- W1-07 không cài thêm dependency; mọi package dùng cho baseline đã được ghi
  vào `requirements.lock`.
