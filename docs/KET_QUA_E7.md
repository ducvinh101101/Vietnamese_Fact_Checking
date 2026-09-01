# Kết quả E7 — biến thể batch ở max_length 256

## Cấu hình thực tế

Kaggle chỉ chạy được `max_length=256`, vì vậy E7 **không phải** thí nghiệm ngữ cảnh 384 token. E7 dùng cùng PhoBERT, group split, seed và word segmentation với E2; thay đổi thực tế là train batch 8 và gradient accumulation 2 (effective batch vẫn là 16).

## So sánh trực tiếp

| Metric | E2 | E7 | Chênh lệch E7 − E2 |
|---|---:|---:|---:|
| Dev Macro-F1 | 85,01% | 84,18% | -0,83 điểm % |
| Test Macro-F1 | 81,07% | 80,25% | -0,82 điểm % |
| Test accuracy | 81,13% | 80,30% | -0,84 điểm % |
| REFUTED → SUPPORTED | 57 | 38 | -19 lỗi |

E7 giảm 19 lỗi `REFUTED → SUPPORTED`, nhưng phần lớn sự thay đổi trở thành `REFUTED → NOT_ENOUGH_INFO` (33 → 50). Đồng thời lỗi `SUPPORTED → REFUTED` tăng 27 → 47. Vì thế chất lượng tổng thể giảm.

## Quyết định

**Giữ E2 làm model tốt nhất hiện tại.** E7 không đạt tiêu chí chọn model là Dev Macro-F1 cao hơn E2.

Ràng buộc 256 token cũng có nghĩa chưa thể kết luận liệu ngữ cảnh dài hơn có cải thiện lỗi phủ định/mâu thuẫn hay không. Không cần chạy lại E7 nếu không thay đổi được giới hạn này; thí nghiệm tiếp theo nên nhắm trực tiếp vào calibration/NEI hoặc hard negatives về phủ định, thời gian và đảo thực thể.
