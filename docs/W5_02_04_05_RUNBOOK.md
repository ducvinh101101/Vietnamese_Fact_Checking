# Runbook — W4-05 / W5-02 sau khi Quang xong retrieval

Ngày: 2026-09-24. Phần Vinh, các hạng mục đánh giá vừa được mở khóa vì Quang đã hoàn thành corpus v2 có metadata (W3-07) và rerank (W3-08).

Điều còn thiếu: **fusion local+web chưa có** (không có `src/fusion*.py`), nên tầng "hybrid/web end-to-end" của W4-05 **chưa chạy được**. Cái chạy được ngay là tầng **reranked-local** và bảng so sánh nhiều tầng. Khi Quang bổ sung fusion, chỉ cần thêm một dòng `--tier` vào bảng.

## File đã thêm

| File | Vai trò |
|---|---|
| `configs/reranked_end_to_end.yaml` | Cấu hình end-to-end dùng `MetadataRerankedRetriever`; verifier giữ y hệt config đang khóa |
| `scripts/evaluate_reranked_end_to_end.py` | Đo end-to-end với rerank cục bộ, cùng giao thức và schema metrics như `evaluate_local_end_to_end.py` |
| `scripts/build_evaluation_comparison.py` | Dựng bảng Markdown so sánh nhiều tầng từ các file metrics đã có |

Đã test phần không cần model: `run_evaluation` (logic chấm + citation), guard thiếu cột, và bộ dựng bảng chạy đúng trên metrics thật (oracle E2 81,07% vs BM25-local 59,49%).

## Bước 1 — Đo reranked-local end-to-end

Chạy trên **dev** trước (chọn/kiểm tra), rồi mới **test** một lần:

```powershell
py -3.13 scripts/evaluate_reranked_end_to_end.py --config configs/reranked_end_to_end.yaml --split data/processed/vifactcheck_group_split/dev.parquet  --metrics outputs/metrics/reranked_e2e_dev.json  --predictions outputs/predictions/reranked_e2e_dev.csv
py -3.13 scripts/evaluate_reranked_end_to_end.py --config configs/reranked_end_to_end.yaml --split data/processed/vifactcheck_group_split/test.parquet --metrics outputs/metrics/reranked_e2e_test.json --predictions outputs/predictions/reranked_e2e_test.csv
```

Hai lưu ý:

- Nếu corpus v2 đổi tên file (không còn là `data/evidence/vifactcheck_passages.jsonl`), sửa `paths.evidence_path` trong `configs/reranked_end_to_end.yaml`.
- `candidate_k=20`, `authority_weight=0` là mặc định thô. Chỉ chỉnh trên dev; không chỉnh bằng test.

## Bước 2 — Dựng bảng so sánh ba tầng (W5-02)

```powershell
py -3.13 scripts/build_evaluation_comparison.py `
  --tier "Oracle E2 (gold evidence)=outputs/metrics/e2_phobert_metrics.json" `
  --tier "BM25-local E2E=outputs/metrics/w4_02_local_end_to_end_test.json" `
  --tier "Reranked-local E2E=outputs/metrics/reranked_e2e_test.json" `
  --output docs/W5_02_EVALUATION_COMPARISON.md
```

Thêm `--tier "Content-only E9=outputs/metrics/e9_vfnd_content_baseline.json"` nếu muốn có cả tầng content trong bảng (nhớ: E9 là nhị phân REAL/FAKE, không cùng nhãn — ghi rõ trong báo cáo là tầng riêng, không so trực tiếp).

## Cách đọc kết quả

- **Oracle → BM25-local**: khoảng cách này (81,07% → 59,49% Macro-F1) là chi phí của việc tự đi tìm bằng chứng. Đây là câu chuyện trung tâm của báo cáo.
- **BM25-local → Reranked-local**: rerank có cải thiện thật không? Nếu Macro-F1 và F1 REFUTED tăng mà latency vẫn hợp lý demo thì giữ rerank; nếu không, giữ BM25 và ghi rõ (đúng như quyết định giữ BM25 thay dense ở W2-04).
- URL Recall@k và citation-match vẫn là **proxy URL-level**; xem audit passage-level W5-03a để biết citation có thực sự entail không.

## Vẫn chờ Quang

- **Fusion local+web** → mở tầng web/hybrid trong bảng (W4-05 đầy đủ).
- **W5-01** (đo BM25/dense/hybrid/rerank ở cấp retrieval) → khác với bảng end-to-end này; đó là metric retrieval thuần (Recall/MRR/nDCG), do Quang chủ trì.
