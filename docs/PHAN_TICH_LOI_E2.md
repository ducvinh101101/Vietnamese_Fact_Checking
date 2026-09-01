# Phân tích lỗi E2 — PhoBERT-base

## Kết quả đã xác nhận

- Test group split: Accuracy **81,13%**, Macro-F1 **81,07%** (1.076 mẫu).
- Baseline E1: Macro-F1 40,15%; E2 cải thiện **40,92 điểm phần trăm**.
- F1 theo lớp: SUPPORTED 82,29%; REFUTED 77,89%; NOT_ENOUGH_INFO 83,02%.

| Nhãn thật → nhãn dự đoán | Số mẫu |
|---|---:|
| SUPPORTED → REFUTED | 27 |
| SUPPORTED → NOT_ENOUGH_INFO | 25 |
| REFUTED → SUPPORTED | 57 |
| REFUTED → NOT_ENOUGH_INFO | 33 |
| NOT_ENOUGH_INFO → SUPPORTED | 27 |
| NOT_ENOUGH_INFO → REFUTED | 34 |

Ưu tiên lớn nhất là 57 lỗi **REFUTED → SUPPORTED**: mô hình dễ bị ảnh hưởng bởi sự giống nhau về chủ đề/từ vựng nhưng chưa nắm chắc phủ định hay quan hệ mâu thuẫn.

## Mười mẫu cần Vinh đọc thủ công

Mở `outputs/predictions/e2_phobert_test_predictions.csv`, lọc các hàng `labels != prediction`, rồi chọn theo thứ tự dưới đây. Ghi kết luận vào bảng để phân biệt lỗi dữ liệu với lỗi mô hình.

| Mẫu | Lọc | Cần kiểm tra | Nhóm nguyên nhân dự kiến |
|---|---|---|---|
| 1–4 | REFUTED → SUPPORTED | Có phủ định/đảo chiều khẳng định không? | Negation / contradiction |
| 5–6 | REFUTED → NOT_ENOUGH_INFO | Evidence có phản bác trực tiếp không? | Evidence chưa rõ hoặc mô hình bỏ sót |
| 7–8 | NOT_ENOUGH_INFO → REFUTED | Claim có thêm chi tiết ngoài evidence không? | Hallucinated contradiction |
| 9 | NOT_ENOUGH_INFO → SUPPORTED | Mô hình suy diễn quá mức từ cùng chủ đề? | Lexical overlap |
| 10 | SUPPORTED → REFUTED hoặc NEI | Paraphrase có bị mất khi tách từ/truncation? | Paraphrase / truncation |

## Quy tắc ghi nhận

- Không chỉnh nhãn gold chỉ vì mô hình dự đoán khác; nếu gold nghi ngờ, đánh dấu `possible_annotation_issue`.
- Ghi rõ claim, evidence, nhãn gold, dự đoán, nhận xét tối đa 2 câu và một nhóm nguyên nhân.
- Không dùng các lỗi này để thay đổi retrieval hay kho evidence; đó là phạm vi của Quang.

## Giả thuyết và E3

E7 đã chạy ở giới hạn 256 token của Kaggle nên chỉ là biến thể batch, không kiểm tra giả thuyết ngữ cảnh dài. E7 có Macro-F1 thấp hơn E2 0,82 điểm phần trăm; giữ E2 làm model tốt nhất.
