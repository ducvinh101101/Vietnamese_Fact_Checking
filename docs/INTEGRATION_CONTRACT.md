# Hợp đồng tích hợp Retriever – Verifier (W2-05)

W2-05 chốt ranh giới giữa phần retrieval của Quang và phần verification của Vinh. Pipeline chỉ phụ thuộc vào hai interface tại `src/contracts.py`, do đó có thể thay BM25 bằng dense/hybrid/web retriever hoặc thay PhoBERT bằng verifier khác mà không đổi luồng điều phối.

## Retriever

```python
search(claim: str, top_k: int = 3) -> list[RetrievedEvidence]
```

- `claim` là chuỗi đã được `FactCheckingPipeline` chuẩn hóa và không rỗng.
- `top_k` phải lớn hơn 0.
- Kết quả có tối đa `top_k` phần tử, được xếp theo `score` giảm dần.
- Mỗi `RetrievedEvidence` phải giữ nguyên `Evidence`, đặc biệt là `passage_id`, `content`, `url`, `source` và metadata contract.
- Retriever không được tự gán nhãn fact-check hay làm mất provenance của evidence.

BM25 hiện thực contract này. Benchmark URL-level trên ViFactCheck group test đạt Recall@3 98,14%, Recall@5 98,98%, MRR@5 0,9671 và p95 81,20 ms. Đây là chất lượng retrieval theo URL, không phải verdict end-to-end.

## Verifier

```python
verify(claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult
```

- Nhận nguyên danh sách evidence có thứ tự từ retriever; danh sách rỗng là input hợp lệ.
- Trả đúng một `VerificationResult` với nhãn `SUPPORTED`, `REFUTED` hoặc `NOT_ENOUGH_INFO`.
- `confidence` nằm trong khoảng 0–1.
- `evidence_ids` phải là `passage_id` thuộc input đã dùng để kết luận; nếu không có evidence, trả danh sách rỗng.
- Verifier không gọi retriever và không sửa evidence.

PhoBERT E2 hiện thực contract này; Macro-F1 81,07% là oracle score với gold evidence, không đại diện cho pipeline dùng evidence truy hồi.

## Pipeline và trách nhiệm tích hợp

`FactCheckingPipeline.run(claim)` là chủ sở hữu luồng: chuẩn hóa và chặn claim rỗng, gọi retriever với `top_k`, gửi đúng evidence trả về vào verifier, rồi trả cả verdict lẫn evidence cho UI/citation.

Pipeline có thể nhận `retriever=` và `checker=` qua dependency injection. Đây là đường tích hợp chính cho W3-01; các constructor cũ dùng `evidence_path` và `engine` vẫn tương thích.

## Kiểm tra bàn giao

- `tests/test_integration_contract.py` kiểm tra một retriever và verifier thay thế được pipeline sử dụng đúng contract.
- `tests/test_retriever.py` kiểm tra BM25 giữ thứ hạng evidence.
- `tests/test_pipeline.py` kiểm tra luồng baseline và claim rỗng.
- Chỉ công bố metric end-to-end sau W3-01; không dùng E2 hoặc BM25 URL-level thay thế metric đó.
