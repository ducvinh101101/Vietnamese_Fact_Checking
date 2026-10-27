# Kết quả demo (W4-04) — 2026-10-27T10:26:46

Quan sát định tính trên các ca chọn sẵn (src/demo_cases.py); không phải số đo chất lượng.

| Ca | Chế độ | Claim | Kỳ vọng | Hệ thống | Điểm | Trích dẫn | Ghi chú |
|---|---|---|---|---|---:|---|---|
| D1 | local | Tổng thống Brazil Lula hoãn chuyến thăm 6 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn. | SUPPORTED | **SUPPORTED** | 0.99 | [local](https://vnexpress.net/tong-thong-brazil-hoan-tham-trung-quoc-vi-viem-phoi-4585646.html) | Trùng nguyên văn một câu trong bài VnExpress (vifactcheck_01030_p001). |
| D2 | local | Tổng thống Brazil Lula hoãn chuyến thăm 10 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn. | REFUTED | **REFUTED** | 0.99 | [local](https://vnexpress.net/tong-thong-brazil-hoan-tham-trung-quoc-vi-viem-phoi-4585646.html) | Nguồn nói 6 ngày; claim nói 10 ngày — mâu thuẫn số liệu (luật cặp-tối-thiểu). |
| D3 | local | Tổng thống Brazil Lula không hoãn chuyến thăm 6 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn. | REFUTED | **REFUTED** | 0.85 | [local](https://vnexpress.net/tong-thong-brazil-hoan-tham-trung-quoc-vi-viem-phoi-4585646.html) | contradiction:negation |
| D4 | local | Kể từ năm 2015 đến nay, theo Kyodo Nhật Bản đã bị Trung Quốc bắt vì tình nghi tham gia hoạt động gián điệp ít nhất 20 công dân Nhật. | REFUTED | **REFUTED** | 0.99 | [local](https://vnexpress.net/trung-quoc-bat-mot-nguoi-nhat-voi-cao-buoc-gian-diep-4585952.html) | Nhãn người REFUTED (test row 177); verifier phải đọc hiểu, không chỉ khớp từ. |
| D5 | local | Đông Nam Á được xem là vùng trũng của bóng đá thế giới, đặc biệt là sau sự thành công của đội tuyển U23 Việt Nam. | NOT_ENOUGH_INFO | **NOT_ENOUGH_INFO** | 0.99 | — | Nhãn người NEI (test row 806): bài liên quan có trong kho nhưng không xác nhận nhận định này. |

Verifier: phobert. Đúng kỳ vọng: 5/5 ca có nhãn kỳ vọng.
