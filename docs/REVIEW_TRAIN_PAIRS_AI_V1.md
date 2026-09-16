# Review 540 cặp claim–passage — AI v1

Ngày hoàn tất lượt review: 2026-09-07. Người review: Codex AI, một lượt đọc ngữ nghĩa, không phải hai người gán nhãn độc lập. **Đây là nhãn silver cho thí nghiệm, không phải human gold và không phải kết quả kiểm chứng sự thật ngoài đời.**

## Kết quả

| Trạng thái | Số cặp |
| --- | ---: |
| Đã đọc và ghi nhận xét | 540 / 540 |
| AI đề xuất SUPPORTED | 44 |
| AI đề xuất REFUTED | 42 |
| AI đề xuất NOT_ENOUGH_INFO | 401 |
| Chưa chốt, cần người phân xử | 53 |

540 cặp thuộc 180 claim. Không lấy nhãn annotation gốc áp sang mọi passage. Không có bước gọi PhoBERT để dùng dự đoán của chính model làm nhãn mới. Bản CSV gốc vẫn giữ nguyên, hash SHA-256 `1e5f0f229d3edda5aa601ca63f5746e4bc1a4093c978bc56cdc4ae4db9697942`.

## Tiêu chí

- Đơn vị gán nhãn là **claim đầy đủ + đúng một passage**. Không ghép thông tin từ passage khác, URL, annotation gốc hoặc kiến thức ngoài để điền chỗ thiếu.
- SUPPORTED: passage đủ căn cứ cho các ý quan trọng, bao gồm thực thể, số liệu, thời điểm và điều kiện của claim. Chấp nhận diễn đạt tương đương.
- REFUTED: có mâu thuẫn xác định trong cùng sự kiện, như đảo số lợi nhuận, sai tuổi, sai ngày bắt đầu, phủ định bị đổi chiều. Thiếu thông tin không phải REFUTED.
- NEI: thiếu một ý quan trọng hoặc passage nói về trường hợp khác; không được hiểu là claim sai ngoài đời.
- `needs_human_review`: câu lỗi/mơ hồ, khó phân giải đại từ, nguồn tự mâu thuẫn đơn vị, cận dưới số lượng, mục đích so với tác động, hoặc ranh giới diễn đạt chưa chắc. Không xuất nhóm này để train.
- Gán nhãn theo nội dung passage lịch sử, không coi số liệu, quy định hoặc chức danh trong bài cũ là thông tin hiện hành. Nội dung bài là dữ liệu, không phải chỉ dẫn cần thực hiện.

Các claim thiếu tên địa điểm/người hoặc ghép nhiều ý bị ảnh hưởng mạnh bởi chia đoạn 700 ký tự. Bộ nhãn áp dụng cách đọc passage độc lập tương ứng đầu vào verifier hiện tại; nếu đổi sang nhiều passage hoặc thêm tiêu đề thì phải review lại.

## Một số điểm quan trọng

- Ledger dòng dữ liệu 180 (index từ 0): Sovico có lợi nhuận gộp 137 tỷ, sau thuế 3.273 tỷ; claim đảo hai số → REFUTED.
- Index 228: nội dung hội nghị ASEAN tháng 5/2023 được passage xác nhận → SUPPORTED dù thuộc nhóm chọn từ nhãn gốc khác.
- Index 300: ghi 24/7 bao hàm hoạt động suốt 24/24 → SUPPORTED, không bác bỏ vì chuỗi ký tự khác nhau.
- Index 321: nguồn xác nhận A Nhi và A Phước tử vong; thêm người thứ ba không phủ định hai người này → SUPPORTED.
- Index 6: nguồn mở đầu nói đồng/lít nhưng dầu mazut ở phần sau là đồng/kg → giữ chờ phân xử.
- Index 261–262: hơn 130 không tự phủ định hơn 150 theo logic cận dưới → không gán REFUTED chắc chắn.
- Index 495–497: passage không nói giới hạn tuổi Marburg → NEI cho cặp, không phải xác nhận nhận định chỉ người trên 50 mắc bệnh.

## File bàn giao

- `data/evaluation/train_pair_ai_review_v1.tsv`: 540 quyết định/nhận xét viết riêng, S/R/N/U; chỉ áp dụng đúng bản CSV có hash trên.
- `data/evaluation/train_retrieved_pair_ai_review_v1.csv`: đầy đủ nội dung, nhãn và lý do, `reviewer` ghi rõ AI.
- `data/evaluation/train_pair_human_adjudication_v1.csv`: 53 cặp cần người phân xử, nhãn để trống.
- `outputs/metrics/train_pair_ai_review_v1.json`: thống kê và hash.
- `data/processed/reviewed_retrieval/ai_silver_v1.parquet`: 487 cặp đã qua kiểm tra claim train, passage gốc và không có URL dev/test. Xuất với lựa chọn rõ ràng `--allow-ai-reviewed`; mặc định exporter vẫn chỉ nhận `approved`.

Không tự đổi `ai_reviewed` thành `approved`. Nếu người review xác nhận, nên tạo bản CSV phiên bản mới; điền tên người, lý do và nhãn đã quyết định. Khi đọc nên ẩn `original_gold_pair_label` và `annotated_evidence` để tránh bị dẫn dắt. Nên kiểm tra thêm một mẫu ngẫu nhiên của cả 487 cặp đã chốt, đặc biệt SUPPORTED/REFUTED; chưa có tỷ lệ đồng thuận người–AI.

## Dùng để fine-tune

487 cặp gồm 82,34% NEI, không nên train riêng hay nhân bản hàng loạt nhóm này. Bundle thí nghiệm giữ 5.075 cặp train gốc sau loại một cặp trùng trong bản đóng gói, thêm 487 silver = 5.562 cặp; không sửa train gốc. Nhãn tổng: 1.817 SUPPORTED, 1.703 REFUTED, 2.042 NEI. Chưa phát hiện xung đột nhãn trên cặp văn bản trùng tuyệt đối; đây không phải bằng chứng toàn bộ nhãn đúng.

Chạy đối chứng chỉ gold và ứng viên gold+silver, cùng checkpoint E2, seed và cấu hình. Trọng số silver 0,5 là lựa chọn khởi đầu thận trọng, chưa chứng minh tối ưu. Xem [hướng dẫn Kaggle RT-V1](KAGGLE_RETRIEVAL_FINETUNE_V1.md).
