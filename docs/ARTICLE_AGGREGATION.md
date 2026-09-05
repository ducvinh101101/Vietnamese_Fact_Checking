# Chính sách tổng hợp verdict cấp bài

`ArticleAggregator` nhận danh sách `Claim` cùng `article_id` và các `VerificationResult` tương ứng. Nó là logic thuần, không gọi retriever, không dùng content-risk và không thay đổi interface của Quang.

## Nhận định được phép trả về

| Assessment | Ý nghĩa |
|---|---|
| `HAS_REFUTED_CLAIMS` | Có ít nhất một claim bị evidence bác bỏ; **không** đồng nghĩa toàn bài là giả. |
| `ALL_CLAIMS_SUPPORTED` | Evidence hiện có ủng hộ toàn bộ claim đã tách, không khẳng định mọi nội dung ngầm trong bài. |
| `INSUFFICIENT_EVIDENCE` | Tất cả claim đã chấm là `NOT_ENOUGH_INFO`. |
| `MIXED_EVIDENCE` | Chỉ có `SUPPORTED` và `NOT_ENOUGH_INFO`. |
| `PARTIALLY_EVALUATED` | Một hay nhiều claim chưa có verdict; số claim bị bác bỏ vẫn được hiển thị. |
| `NO_CLAIMS` | Không có claim để kiểm chứng. |

Mỗi claim trong output giữ text, label, confidence và `evidence_ids`. Nếu output `results` chứa `claim_id` của article khác, component dừng với lỗi thay vì trộn kết quả giữa bài viết.

Phần Vinh đã sẵn sàng để tích hợp sau khi Quang bàn giao luồng retrieval → verifier có evidence thật. Khi đó cần chạy E11 để so sánh có/không tách claim trên cùng protocol end-to-end; không dùng unit test của component thay metric này.
