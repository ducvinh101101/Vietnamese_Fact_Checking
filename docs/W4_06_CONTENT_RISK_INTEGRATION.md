# W4-06 — Nối content-risk vào output cấp bài

Ngày: 2026-09-24. Phần Vinh. Không đụng retriever/UI của Quang.

## Mục tiêu và ranh giới

Hiển thị điểm rủi ro nội dung (E9) ở cấp bài, **tách biệt hoàn toàn** với verdict. Điểm này là tín hiệu văn phong/nguồn, **không phải bằng chứng**, không tham gia quyết định SUPPORTED/REFUTED/NEI, và không được diễn giải như xác suất một bài là tin giả.

Ràng buộc này được cưỡng chế bằng kiến trúc, không phải bằng lời nhắc:

- `content_risk` là một trường **riêng** trên `ArticleRun`, không nằm trong `ArticleAggregation`.
- Bộ chấm chạy **sau** và **không đọc** kết quả claim.
- Test `test_content_risk_does_not_change_verdict` chứng minh verdict từng claim và tổng hợp cấp bài **y hệt** dù có hay không content-risk.

## File đã thêm

| File | Vai trò |
|---|---|
| `scripts/fit_content_risk_model.py` | Fit E9 trên toàn bộ VFND và lưu model triển khai (E9 gốc chỉ chạy CV, không lưu model) |
| `src/content_risk.py` | `ContentRiskScorer` nạp model, chấm bài → `ContentRiskAssessment` (điểm, dải, cờ OOD, disclaimer) |
| `src/article_pipeline.py` | Thêm tham số `content_risk_scorer` và trường `ArticleRun.content_risk` (mặc định None) |
| `tests/test_content_risk.py` | 5 test: dải điểm, cờ OOD, tắt-trả-None, round-trip, và tách biệt khỏi verdict |

Đã test bằng model sklearn thật (5/5 pass). Không đổi `ArticleAggregator`, không đổi schema verdict, tương thích ngược: pipeline cũ không truyền scorer vẫn chạy y nguyên.

## Bạn cần chạy đúng MỘT lệnh

E9 gốc không lưu model, nên fit lại một lần (CPU, ~30 giây):

```powershell
py -3.13 scripts/fit_content_risk_model.py
```

Kết quả: `models/e9_content_risk/model.joblib` + `metadata.json` (C đã chọn, ngưỡng dải, danh sách domain huấn luyện để cảnh báo OOD).

Kiểm tra:

```powershell
py -3.13 -m pytest tests/test_content_risk.py -q
```

## Nối vào app (khi dựng UI cấp bài — phối hợp Quang, W4-01)

```python
from src.content_risk import ContentRiskScorer
from src.article_pipeline import ArticleFactCheckingPipeline

scorer = ContentRiskScorer.load("models/e9_content_risk")   # hoặc ContentRiskScorer(None) để tắt
article_pipeline = ArticleFactCheckingPipeline(claim_runner, content_risk_scorer=scorer)
run = article_pipeline.run(article)

if run.content_risk is not None:
    risk = run.content_risk
    # Hiển thị RIÊNG, khác vùng khác màu với khối verdict:
    #   "Rủi ro nội dung: {risk.band}"          -> KHÔNG hiện số thập phân
    #   risk.disclaimer                          -> câu cố định "không phải bằng chứng"
    #   if risk.out_of_distribution_source: cảnh báo nguồn ngoài phân bố huấn luyện
```

## Ba quy tắc hiển thị (bắt buộc)

1. **Không hiện số thập phân.** Dùng dải thấp/trung bình/cao. `risk_score` chỉ để log, không để lên UI — 221 bài huấn luyện không cho phép một con số trông chính xác.
2. **Gắn cờ nguồn ngoài phân bố.** Vì mỗi domain VFND chỉ có một nhãn, điểm trên domain lạ gần như vô nghĩa; `out_of_distribution_source=True` phải hiện cảnh báo thay vì một con số tự tin.
3. **Tách hẳn khỏi khối verdict**, khác màu khác vùng, luôn kèm `disclaimer`. Người xem rất dễ tưởng điểm rủi ro là bằng chứng.

## Giới hạn cần ghi trong báo cáo

E9 học tín hiệu văn phong/nguồn trên 221 bài VFND, domain trùng hoàn toàn với nhãn. Đây là baseline cho thấy **vì sao content-only không đủ và vì sao cần RAG**, không phải một bộ phát hiện tin giả. Recall FAKE của E9 chỉ 0,61 (OOF) — bỏ lọt ~4/10 bài giả. Trình bày đúng như vậy sẽ biến 77% thành một phát hiện có ý nghĩa thay vì một con số phải bảo vệ.
