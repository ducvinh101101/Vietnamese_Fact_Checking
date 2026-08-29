# Phân công hai người

## Nguyên tắc

- Người A chịu trách nhiệm dữ liệu và đánh giá; Người B chịu trách nhiệm retrieval, pipeline và giao diện.
- Không sửa cùng một tệp lõi trong một thời điểm. Trao đổi qua issue hoặc mục trong backlog trước khi chạm vào `configs/` và `src/pipeline.py`.
- Mọi thí nghiệm phải lưu cấu hình, seed, commit Git, metric và ghi chú kết luận.

## Phân công chính

| Hạng mục | Người A — Dữ liệu & mô hình | Người B — Retrieval & sản phẩm | Điểm bàn giao |
|---|---|---|---|
| Tuần 1 | Tải/audit ViFactCheck, split chống rò rỉ, TF-IDF baseline | Chuẩn hóa JSONL, BM25, app dữ liệu mẫu | Schema evidence và baseline metrics |
| Tuần 2 | PhoBERT/XLM-R thử nghiệm, calibration | Chunking, Recall@k, dense/hybrid nếu đủ thời gian | Interface `Retriever.search()` ổn định |
| Tuần 3 | Verifier cặp claim–evidence, phân tích lỗi | Nối verifier vào pipeline, citation, test | Pipeline end-to-end |
| Tuần 4 | Bảng kết quả, báo cáo phương pháp | Streamlit, cache, demo, README | Bản release demo |

## Hợp đồng tích hợp

Người A bàn giao verifier với interface:

```python
verify(claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult
```

Người B bàn giao retriever với interface:

```python
search(claim: str, top_k: int) -> list[RetrievedEvidence]
```

Không thay đổi `Evidence`, `RetrievedEvidence`, `VerificationResult` trong `src/schemas.py` nếu chưa thống nhất.

## Git tối thiểu

```powershell
git init
git checkout -b feature/data-baseline     # Người A
git checkout -b feature/retrieval-ui      # Người B
```

- Commit nhỏ, một mục đích; ví dụ `feat: add BM25 retrieval evaluation`.
- Trước khi merge, chạy `pytest -q`.
- Không commit dữ liệu gốc, model checkpoint, index hoặc API key.
