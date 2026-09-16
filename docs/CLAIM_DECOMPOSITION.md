# W3-06 — Tách claim từ bài viết

`ClaimDecomposer` nhận một `Article` và trả về các `Claim` liên kết bằng cùng `article_id`. Đây là component độc lập của Vinh: không gọi retriever, không sửa `src/pipeline.py` và không cần corpus/evidence của Quang.

## Quy tắc hiện tại

- Giữ nguyên văn bản: tách theo kết thúc câu và dấu chấm phẩy; không dịch, không tóm tắt, không thêm chủ thể/quan hệ/thời gian.
- Bỏ câu hỏi và đoạn quá ngắn; bỏ title nếu title đã xuất hiện nguyên văn trong body.
- Khử trùng theo văn bản chuẩn hóa, không phân biệt hoa/thường.
- `claim_id` là SHA-256 rút gọn của text chuẩn hóa, tiền tố bởi `article_id`; vì thế ổn định khi cùng claim xuất hiện lại.
- Claim kế thừa `published_at` của article, nếu có.

## Giới hạn có chủ đích

Một câu ghép với liên từ vẫn có thể chứa nhiều mệnh đề. Component không tự tách tiếp bằng luật ngữ pháp hay LLM vì việc đó có thể làm đổi nghĩa và sinh claim không có trong nguồn. Những case này phải được review trước khi dùng làm gold set; E11 sau này sẽ đo ablation có/không decomposition trên protocol retrieval/end-to-end đã chốt.

## Cách dùng

```python
from src.claim_decomposer import ClaimDecomposer

claims = ClaimDecomposer().decompose(article)
# Mỗi claim có claim_id, article_id, text và published_at.
```

Kết quả decomposition không phải verdict cấp bài và không được trộn với content-risk E9/E10. Verdict chỉ được sinh sau khi từng claim nhận evidence và được verifier chấm.
