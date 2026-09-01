# Pipeline end-to-end: kiểm chứng thông tin tiếng Việt

## 1. Bài toán cần giải quyết

Hệ thống nhận một phát biểu tiếng Việt (*claim*) và trả về:

1. Nhãn `SUPPORTED`, `REFUTED` hoặc `NOT_ENOUGH_INFO`.
2. Độ tin cậy của verifier.
3. ID, nội dung và URL của evidence được dùng để kết luận.

Mục tiêu không phải phát hiện mọi tin giả trên Internet. Hệ thống chỉ kết luận dựa trên evidence mà nó tìm được trong kho tài liệu đã nạp.

```text
Claim người dùng
    │
    ▼
Chuẩn hóa văn bản
    │
    ▼
BM25 lấy top-3 evidence
    │
    ▼
VnCoreNLP tách từ claim và từng evidence
    │
    ▼
PhoBERT E2 chấm từng cặp (claim, evidence)
    │
    ▼
Chọn kết luận + evidence ID + confidence
    │
    ▼
Streamlit hiển thị nhãn, bằng chứng và nguồn
```

## 2. Các thành phần và lý do chọn

| Thành phần | Hiện dùng | Vai trò | Lý do |
|---|---|---|---|
| Kho evidence | JSONL (`document_id`, `passage_id`, `content`, `source`, `url`) | Nguồn thông tin có thể trích dẫn | Đơn giản, minh bạch, dễ thay thế bằng corpus lớn hơn |
| Retriever | BM25, `top_k=3` | Tìm passage liên quan đến claim | Baseline nhanh, chạy cục bộ, không cần GPU |
| Tách từ | VnCoreNLP word segmentation | Đưa văn bản về dạng PhoBERT đã được tiền huấn luyện | Phù hợp đặc thù tiếng Việt/PhoBERT |
| Verifier | PhoBERT-base E2 fine-tune | Phân loại claim–evidence thành 3 nhãn | E2 tốt nhất hiện tại: Macro-F1 test 81,07% với gold evidence |
| Giao diện | Streamlit | Nhập claim và xem evidence | Đủ cho demo cục bộ |

## 3. Luồng xử lý chi tiết

### Bước 1 — Nhập và kiểm tra claim

`FactCheckingPipeline.run()` chuẩn hóa khoảng trắng/ký tự của claim. Claim rỗng bị từ chối ngay với lỗi rõ ràng.

### Bước 2 — Truy hồi evidence

`BM25Retriever.search()` token hóa claim và tất cả passage, xếp hạng theo BM25 rồi trả về ba passage có điểm cao nhất. Mỗi passage vẫn giữ nguyên `passage_id`, nguồn và URL để UI có thể trích dẫn.

### Bước 3 — Kiểm chứng từng cặp

Mỗi cặp `(claim, evidence)` được VnCoreNLP tách từ, sau đó tokenized theo cặp cho PhoBERT, giới hạn 256 token. PhoBERT trả về xác suất cho:

- `SUPPORTED`: evidence ủng hộ claim.
- `REFUTED`: evidence mâu thuẫn claim.
- `NOT_ENOUGH_INFO`: evidence không đủ để kết luận.

### Bước 4 — Tổng hợp kết quả

Pipeline chấm tất cả evidence top-3. Nếu có dự đoán `SUPPORTED` hoặc `REFUTED`, nó chọn cặp có confidence cao nhất trong hai nhãn này; nếu không, chọn kết quả `NOT_ENOUGH_INFO` confidence cao nhất. Kết quả có dạng:

```python
VerificationResult(
    label="SUPPORTED | REFUTED | NOT_ENOUGH_INFO",
    confidence=0.0,          # 0–1
    evidence_ids=["..."],
    explanation="...",
)
```

## 4. Những gì đã hoàn thành

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| ViFactCheck audit và group split theo URL | Hoàn thành | 7.232 mẫu; kiểm tra rò rỉ URL = 0 ở split mới |
| E1 TF-IDF + Linear SVM | Hoàn thành | Macro-F1 test 40,15% |
| E2 PhoBERT-base claim + gold evidence | Hoàn thành, model tốt nhất | Macro-F1 test 81,07%; accuracy 81,13% |
| E7 biến thể batch, vẫn 256 token | Hoàn thành, không thay E2 | Macro-F1 test 80,25% |
| Pipeline kỹ thuật claim → evidence → label | Hoàn thành | Smoke test cục bộ thành công |
| Đánh giá retrieval/evidence corpus thật | Chưa hoàn thành | Chờ corpus passage và Recall@k |
| Đánh giá end-to-end chuẩn trên ViFactCheck | Chưa hoàn thành | Chỉ thực hiện sau khi retrieval ổn định |

## 5. Cách chạy cục bộ

Điều kiện cần: checkpoint E2 trong `models/e2_phobert/best_model/`, VnCoreNLP trong `models/vncorenlp/` và Java portable trong `tools/java17/`. Các thư mục lớn này được `.gitignore` bỏ qua.

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Hoặc smoke test không qua giao diện:

```powershell
python -c "from src.pipeline import FactCheckingPipeline; p=FactCheckingPipeline('data/evidence/sample_evidence.jsonl', engine='phobert', model_path='models/e2_phobert/best_model', vncorenlp_dir='models/vncorenlp'); print(p.run('Chưa có thông báo chính thức về việc thay đổi lịch học trên phạm vi toàn quốc.')[0])"
```

## 6. Đánh giá đúng kết quả

Không được gộp hai loại metric sau thành một:

| Loại đánh giá | Kết quả hiện có | Ý nghĩa |
|---|---:|---|
| Verifier với **gold evidence** | E2 Macro-F1 81,07% | Đo chất lượng PhoBERT khi evidence đúng đã được cung cấp |
| Smoke test với BM25 + 3 passage mẫu | 8/18 đúng (44,44%) | Xác nhận luồng kỹ thuật; **không** là benchmark model hay end-to-end chính thức |

Kết quả 44,44% thấp vì kho mẫu cực nhỏ và BM25 có thể đưa evidence không liên quan. Nó không mâu thuẫn với 81,07%; hai phép đo có đầu vào khác nhau.

## 7. Giới hạn hiện tại và hướng giải quyết

1. **Retriever chưa được đánh giá trên corpus thật.** Giải pháp: tạo passage từ ViFactCheck, đo Recall@3/5, MRR và latency trước khi dùng metric end-to-end.
2. **Verifier được train với gold evidence.** Giải pháp: sau khi retrieval ổn định, đánh giá verifier trên retrieved evidence và bổ sung hard negatives nếu cần.
3. **Chọn nhãn quyết đoán có thể thiên về REFUTED/SUPPORTED khi evidence không liên quan.** Giải pháp: calibration và ngưỡng NEI trên dev set; không chỉnh từ các case demo đơn lẻ.
4. **Giới hạn 256 token trên Kaggle.** E7 cho thấy chỉ đổi batch không tốt hơn E2. Giải pháp ưu tiên tiếp theo là hard negatives cho phủ định, thời gian và đảo thực thể thay vì lặp lại E7.

## 8. Điểm bàn giao giữa hai phần

Verifier giữ hợp đồng sau, nên có thể thay retriever mà không đổi mô hình:

```python
verify(claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult
```

Retriever chỉ cần trả về danh sách `RetrievedEvidence` có passage ID và URL. Khi kho evidence/retriever tốt hơn được bàn giao, pipeline và Streamlit sẽ dùng lại được ngay; sau đó cần chạy đánh giá end-to-end để xác nhận chất lượng thực tế.

## 9. Web retrieval: trạng thái kế hoạch

Pipeline hiện **chưa gọi Internet**. Bản mở rộng dự kiến lấy passage web chỉ từ allowlist uy tín, lưu URL/domain/title/thời điểm truy cập, rồi hợp nhất với evidence cục bộ trước khi gửi PhoBERT. Xem [kế hoạch chi tiết](WEB_RETRIEVAL_PLAN.md). Không được dùng metric E2 để khẳng định chất lượng web end-to-end trước khi đo Recall@k và Macro-F1 trên evidence thực truy hồi.
