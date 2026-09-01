# Review 10 lỗi E2 — verifier PhoBERT

## Phạm vi và cách chọn

Chọn 10 trong 203 lỗi của test group split, gồm mọi hướng nhầm nhãn và ưu tiên lỗi `REFUTED → SUPPORTED`. Đây là review claim–gold-evidence của **verifier**; không đánh giá retrieval.

| # | Nhãn gold → dự đoán | Nhận định từ claim–evidence | Nhóm lỗi | Kết luận cho E7 |
|---:|---|---|---|---|
| 1 | SUPPORTED → REFUTED | Claim và evidence gần như cùng nội dung về quy định đất đai gây khó khăn. | Paraphrase/robustness | Ngữ cảnh dài khó giúp; cần kiểm tra seed hoặc dữ liệu. |
| 2 | SUPPORTED → NEI | Claim và evidence cùng nói NHNN lấy ý kiến sửa quy định trái phiếu. | Paraphrase/robustness | Không phải lỗi do cắt ngữ cảnh rõ ràng. |
| 3 | REFUTED → SUPPORTED | Claim nói Thùy Tiên đăng ký hiến tạng **sau**, evidence nói **trước** khi đăng quang. | Quan hệ thời gian | Đo riêng trong E7; cần model nhận biết "trước/sau". |
| 4 | REFUTED → SUPPORTED | Claim khẳng định nhà đầu tư đã bàn giao, evidence chỉ nêu điều kiện lương tăng khi bàn giao và hợp đồng chưa ký. | Điều kiện/quan hệ logic | E7 có thể giúp nếu đoạn bị cắt, nhưng cần kiểm tra hard negative. |
| 5 | REFUTED → SUPPORTED | Claim đổi loại vi phạm thành tuyển sinh; evidence chỉ nêu tài chính và chuyên môn. | Chi tiết không được chứng minh | Không nên suy diễn support từ cùng chủ đề. |
| 6 | REFUTED → SUPPORTED | Claim đảo người thắng/thua và phần thưởng giữa Nguyễn Thị Tâm với Nikhat Zareen. | Đảo thực thể–vai trò | E7 cần đo; có thể hưởng lợi nếu evidence dài. |
| 7 | REFUTED → NEI | Claim thêm tam sinh, hai năm; evidence mô tả đồ cúng khác và không có giỗ hằng năm. | Mâu thuẫn một phần / phủ định | Cần tăng khả năng bắt cụm phủ định và chi tiết số lượng. |
| 8 | REFUTED → NEI | Claim nói cha Shakira qua đời, evidence chỉ nói bị ngã và sức khỏe suy yếu. | Claim mạnh hơn evidence | Nhãn gold có thể cần rà lại: evidence không phủ định trực tiếp việc qua đời. |
| 9 | NEI → SUPPORTED | Evidence trùng phần “4 con hà mã ... Colombia”, claim thêm mục đích nuôi thú cưng. | Khả năng lỗi nhãn hoặc entailment một phần | Rà lại annotation trước khi dùng làm hard negative. |
| 10 | NEI → REFUTED | Evidence nói nhân vật là mẹ của ba con; claim suy ra đã lập gia đình. | Suy diễn ngoài evidence | Model gán REFUTED thay vì NEI dù evidence không phủ định. |

## Tổng hợp nguyên nhân

- **4/10** liên quan quan hệ ngữ nghĩa tinh: thời gian, điều kiện, vai trò thực thể hoặc suy diễn.
- **3/10** là claim thêm chi tiết mà evidence không đủ xác nhận; mô hình cần ưu tiên NEI hơn nhãn quyết đoán.
- **2/10** là paraphrase/evidence gần trùng, cho thấy lỗi không chỉ đến từ độ dài.
- **Ít nhất 2/10** có khả năng nhãn gold hoặc ranh giới REFUTED–NEI cần được rà lại trước khi kết luận model sai hoàn toàn.

## Kết quả E7 và hướng tiếp theo

E7 thực tế phải giữ `max_length=256`, nên không kiểm tra ngữ cảnh dài. Kết quả Test Macro-F1 80,25%, thấp hơn E2 81,07%; giữ E2. Khi có thể thử cấu hình mới, dùng các điều kiện sau:

1. Dev Macro-F1 cao hơn E2 (tiêu chí chọn model chính).
2. Test Macro-F1 không thấp hơn E2 quá 0,5 điểm phần trăm.
3. Lỗi `REFUTED → SUPPORTED` giảm nhưng không chỉ bằng cách chuyển hàng loạt sang NOT_ENOUGH_INFO.
4. Review lại các mẫu #3, #4, #6, #7; không kỳ vọng cấu hình batch đơn thuần sửa các mẫu #1, #2, #9, #10.

Không thay E2 chỉ vì một vài ví dụ đẹp; quyết định dựa trên dev Macro-F1 rồi mới báo cáo test một lần.
