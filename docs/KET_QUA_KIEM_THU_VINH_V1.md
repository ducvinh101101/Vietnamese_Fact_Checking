# Kết quả kiểm thử thủ công Vinh V1

## Mục đích

`vinh_manual_claims_v1.csv` gồm 18 claim có nhãn kỳ vọng do Vinh thiết kế: 6 SUPPORTED, 6 REFUTED và 6 NOT_ENOUGH_INFO. Đây là bộ smoke test để lặp lại khi thay đổi **verifier**.

## Lần chạy đầu

- Ngày chạy: 2026-08-31.
- Engine: PhoBERT E2 + BM25 trên `data/evidence/sample_evidence.jsonl`.
- Kết quả: **8/18 đúng (44,44%)**.
- Các tệp chi tiết: `outputs/manual_evaluation/` (được tạo lại bằng script, không dùng làm benchmark chính thức).

## Diễn giải đúng

Con số này **không phải** Macro-F1 của E2 và không dùng để so sánh model. E2 đạt Macro-F1 81,07% khi dùng gold evidence trong group split ViFactCheck. Lần chạy V1 trước tiên phụ thuộc việc BM25 lấy được passage phù hợp từ chỉ ba evidence mẫu; các truy vấn ngoài phạm vi dễ bị PhoBERT gán REFUTED dù nhãn đúng phải là NOT_ENOUGH_INFO.

Vì vậy V1 có hai giá trị:

1. Xác nhận ứng dụng cục bộ chạy trọn luồng claim → retrieve → verify.
2. Là danh sách kiểm tra thủ công sau mỗi lần cập nhật model, đồng thời phơi bày rõ giới hạn retrieval hiện tại.

Không thay đổi retriever, evidence store hay tham số BM25 dựa trên kết quả này; các phần đó thuộc phạm vi Quang.
