# Phân công hai người

## Nguyên tắc

- Vinh chịu trách nhiệm dữ liệu và đánh giá; Quang chịu trách nhiệm retrieval, pipeline và giao diện.
- Không sửa cùng một tệp lõi trong một thời điểm. Trao đổi qua issue hoặc mục trong backlog trước khi chạm vào `configs/` và `src/pipeline.py`.
- Mọi thí nghiệm phải lưu cấu hình, seed, commit Git, metric và ghi chú kết luận.

## Phân công chính

| Hạng mục | Vinh — Dữ liệu & mô hình | Quang — Retrieval & sản phẩm | Điểm bàn giao |
|---|---|---|---|
| Tuần 1 | Audit, split, schema article/claim/evidence | Môi trường tái lập, metadata contract | Manifest dữ liệu và schema chung |
| Tuần 2 | Verifier E2; content-only baseline/transformer | Protocol corpus/query, provider/allowlist web | Metric oracle và protocol retrieval |
| Tuần 3 | Claim decomposition | Corpus passage, BM25/dense/reranker, web retriever | Top-k evidence có metadata |
| Tuần 4 | Calibration, article aggregation/fusion policy | Nối retrieval→verifier, citation và UI | Demo claim và article-level |
| Tuần 5 | Content/RAG evaluation, temporal/source test, citation audit | Retrieval benchmark và latency | Báo cáo oracle/retrieval/end-to-end |
| Tuần 6 | Ablation, giới hạn và báo cáo | Reproducible release, demo/slide | Bản release tái lập được |

## Hợp đồng tích hợp

Vinh bàn giao verifier với interface:

```python
verify(claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult
```

Quang bàn giao retriever với interface:

```python
search(claim: str, top_k: int) -> list[RetrievedEvidence]
```

Không thay đổi `Evidence`, `RetrievedEvidence`, `VerificationResult` trong `src/schemas.py` nếu chưa thống nhất.

## Git tối thiểu

```powershell
git init
git checkout -b feature/data-baseline     # Vinh
git checkout -b feature/retrieval-ui      # Quang
```

- Commit nhỏ, một mục đích; ví dụ `feat: add BM25 retrieval evaluation`.
- Trước khi merge, chạy `pytest -q`.
- Không commit dữ liệu gốc, model checkpoint, index hoặc API key.

## Mở rộng phạm vi đề tài

- **Vinh:** content-risk baseline, claim decomposition, calibration, article aggregation policy, dataset/evaluation protocol, temporal/source test và báo cáo ablation.
- **Quang:** corpus ingestion, metadata nguồn/thời gian, BM25/dense/rerank, web retrieval allowlist, cache, citation rendering và reproducible release.
- **Cả hai:** chốt claim schema, source policy, fusion rule, end-to-end audit và demo.
