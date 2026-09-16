# W5-01 — Benchmark retrieval trên query frozen

Đo trên 1.080 query **dev** frozen và corpus W3-07 v2 (5.844 passage). Relevance
là URL-level, không phải passage-qrels. Không dùng test để chọn cấu hình.

> **Trạng thái: Đang thực hiện.** Benchmark bốn nhánh và quyết định giữ BM25 đã
> hoàn tất. W5-01 chỉ được đóng sau khi có passage-qrels do reviewer độc lập
> xác nhận để đo `nDCG@5`/passage-level metrics.

| Nhánh | Recall@3 | Recall@5 | MRR@5 | p95 ms/query |
|---|---:|---:|---:|---:|
| BM25 | 98,15% | 98,52% | 0,96585 | 160,39 |
| Dense E5-small + FAISS | 94,35% | 95,65% | 0,91253 | 49,33 |
| Hybrid RRF | 97,69% | 98,43% | 0,95469 | 209,31 |
| W3-08 reranker | 98,15% | 98,52% | 0,96585 | 167,88 |

Theo rule đã khóa, chỉ thay BM25 nếu cả Recall@5 và MRR@5 cùng tăng trên dev.
Không nhánh nào đạt; reranker bằng BM25 nhưng chậm hơn. Quyết định: **giữ BM25**.

`nDCG@5` và passage-level Recall/MRR là `pending`: W2-10 chưa có qrels do hai
reviewer độc lập. Artefact `outputs/retrieval/w5_01/dev_metrics.json` và
`dev_predictions.jsonl` lưu hash corpus/model/split, prediction và latency.
