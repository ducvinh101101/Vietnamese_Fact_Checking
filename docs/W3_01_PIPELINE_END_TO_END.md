# W3-01 — pipeline retrieval → verifier → verdict

## Bàn giao

W3-01 dùng contract W2-05: pipeline chuẩn hóa claim, gọi retriever với `top_k`,
chuyển nguyên danh sách `RetrievedEvidence` theo thứ tự đó cho verifier và trả
`VerificationResult` cùng evidence để UI trích dẫn. App default nay dùng corpus
ViFactCheck 5.845 passages thay vì corpus mẫu 3 passage.

Pipeline kiểm tra ở runtime các ranh giới hợp đồng: `top_k > 0`, retriever không
vượt top-k và giữ score giảm dần, verdict thuộc `SUPPORTED`/`REFUTED`/
`NOT_ENOUGH_INFO`, confidence trong [0,1], và mọi `evidence_id` của verifier phải
thuộc đúng evidence vừa truy xuất. Pipeline không thay nhãn PhoBERT, không chấm
lại score và không biến citation thành evidence mới.

## Smoke tái lập

```powershell
.\.venv\Scripts\python.exe scripts\run_w3_01_pipeline_smoke.py
.\.venv\Scripts\python.exe -m pytest -q
```

Smoke chọn một claim frozen có mỗi nhãn dataset từ group-test, chạy BM25 corpus
thật → PhoBERT E2 → citation. Nó chỉ xác nhận đường đi kỹ thuật và provenance;
không tính accuracy, Macro-F1, Recall hay không dùng nhãn dataset để sửa verdict.
Output lưu hash config/corpus/test split, verdict quan sát và top-k citation tại
`outputs/metrics/w3_01_end_to_end_smoke.json`.

## Giới hạn

Macro-F1 E2 81,07% vẫn là oracle với gold evidence. W3-01 không được dùng smoke
này để kết luận chất lượng end-to-end; W3-04/W4-02/R5 mới phân tích retrieval,
verifier và NEI có phân tách. Passage-qrels/nDCG của W2-10 vẫn pending review.
