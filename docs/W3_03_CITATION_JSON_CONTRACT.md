# W3-03 — Citation ID/URL, JSON output và no-evidence

## Bàn giao

`FactCheckingPipeline.run_json(claim)` chạy cùng pipeline hiện có rồi xuất một
payload JSON theo schema `w3-03/v1`. Payload tách `verdict`, toàn bộ evidence
đã retrieve và `citations` được verifier dùng để kết luận. Việc xuất này không
thay đổi BM25 ranking, PhoBERT hay policy chọn nhãn/citation.

Contract bắt buộc:

- Mỗi citation ID phải thuộc chính danh sách evidence của lượt chạy đó và không
  được lặp.
- Citation phải trỏ tới evidence có score dương và URL HTTP(S) tuyệt đối hợp lệ.
- `NOT_ENOUGH_INFO` không mang citation.
- `passage_id` trong retrieval phải duy nhất; score phải hữu hạn để JSON không
  chứa NaN/Infinity.

## Kiểm tra tái lập

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\run_w3_03_quality_smoke.py
```

Smoke dùng một chuỗi không có lexical hit trong corpus ViFactCheck hiện dùng,
xác nhận pipeline PhoBERT trả `NOT_ENOUGH_INFO`, không citation và không có
evidence điểm dương. Artifact chỉ lưu hash, verdict và count, không lưu claim
hay nội dung evidence: `outputs/metrics/w3_03_json_output_smoke.json`.

## Giới hạn

Contract xác nhận ID/URL/provenance có cấu trúc hợp lệ. URL hợp lệ hoặc khớp
bài báo không chứng minh passage đủ để entail/refute claim; việc audit
faithfulness thủ công vẫn là W5-03 của Vinh.
