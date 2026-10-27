# Báo cáo đánh giá challenge set

- Engine: **phobert** · Số claim: 380 · Lỗi chạy: 0
- Độ trễ: p50 0.316s · p95 0.522s
- Lưu ý: claim lấy từ chính kho (in-distribution), REF_* là biến đổi tổng hợp, NEI theo giả định kho đóng.
  Kết quả là CHẨN ĐOÁN điểm yếu, không thay cho đánh giá trên test split có nhãn người.

## Tổng quan

| | Accuracy | Macro-F1 | F1 SUP | F1 REF | F1 NEI |
|---|---|---|---|---|---|
| Pipeline (thô) | 91.6% | 90.6% | 92.8% | 93.1% | 85.9% |
| + GuardedVerifier | 92.1% | 91.7% | 95.0% | 92.3% | 87.9% |
| + Guard + MinimalPair (safety_layers) | 98.9% | 98.7% | 98.7% | 99.7% | 97.6% |

Evidence view: **focus_only**. Cột 'final' là cấu hình `safety_layers: true`.
Guard chặn **19** verdict sai, nhưng hạ nhầm **14** verdict đúng.

## Ma trận nhầm lẫn (thô) — hàng: nhãn đúng, cột: dự đoán

| | SUP | REF | NEI |
|---|---|---|---|
| **SUP** | 116 | 1 | 3 |
| **REF** | 10 | 168 | 2 |
| **NEI** | 4 | 12 | 64 |

## Theo từng loại hiện tượng

| Loại | n | Acc | Acc+guard | Acc+safety | SUP sai (safety) | Hit@k nguồn | Acc khi lấy được nguồn | Acc khi trượt nguồn | SUP sai | Phân bố dự đoán |
|---|---|---|---|---|---|---|---|---|---|---|
| SUP_VERBATIM | 60 | 96.7% | 96.7% | 98.3% | — | 100.0% | 96.7% | — | — | {'SUP': 58, 'NEI': 1, 'REF': 1} |
| SUP_FORMAT | 60 | 96.7% | 95.0% | 96.7% | — | 100.0% | 96.7% | — | — | {'SUP': 58, 'NEI': 2} |
| REF_NUMBER | 60 | 98.3% | 95.0% | 100.0% | 0.0% | 100.0% | 98.3% | — | 0.0% | {'REF': 59, 'NEI': 1} |
| REF_DIRECTION | 60 | 93.3% | 78.3% | 98.3% | 0.0% | 100.0% | 93.3% | — | 5.0% | {'REF': 56, 'NEI': 1, 'SUP': 3} |
| REF_NEGATION | 60 | 88.3% | 85.0% | 100.0% | 0.0% | 100.0% | 88.3% | — | 11.7% | {'SUP': 7, 'REF': 53} |
| NEI_PARTIAL | 60 | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | — | 0.0% | {'NEI': 60} |
| NEI_FICTIONAL | 20 | 20.0% | 100.0% | 100.0% | 0.0% | — | — | — | 20.0% | {'REF': 12, 'NEI': 4, 'SUP': 4} |

## Cách đọc & ví dụ lỗi

### SUP_VERBATIM

Câu nguyên văn trong kho -> phải SUPPORTED. Sai = verifier/retrieval yếu cả ở ca dễ nhất.

2 lỗi. Ví dụ:

- `SUP_VERBATIM-029` vàng **SUP** → dự đoán **NEI** (conf 0.9933, lấy được nguồn: có)
  - Claim: Tại TPHCM: Số 2A Nguyễn Thị Minh Khai, phường Đa Kao, Quận 1. 2.
- `SUP_VERBATIM-057` vàng **SUP** → dự đoán **REF** (conf 0.9608, lấy được nguồn: có)
  - Claim: Sự kiện rước đuốc tại Hà Nội có sự tham dự của VĐV điền kinh Nguyễn Thị Huyền - chủ nhân 10 HCV SEA Games và 200 VĐV tiêu biểu cả nước.
  - Trích dẫn: Sáng 24-3, ngọn đuốc SEA Games 32 đã chính thức được rước tại Hà Nội nhằm chào hưởng ứng đại hội thể thao lớn nhất khu vực. VĐV điền kinh Nguyễn Thị Huyền vinh dự cầm đuốc SEA Games 32 tại chặng đầu tiên trong hành trình

### SUP_FORMAT

Chỉ khác khoảng trắng/dấu câu cuối -> phải giống SUP_VERBATIM. Thấp hơn = nhạy định dạng.

2 lỗi. Ví dụ:

- `SUP_FORMAT-002` vàng **SUP** → dự đoán **NEI** (conf 0.9575, lấy được nguồn: có)
  - Claim: Cuối  cùng,  ca  mổ  được  tiến  hành  và  thành  công  sau  hai  tiếng  nỗ  lực  của  các  BS
- `SUP_FORMAT-057` vàng **SUP** → dự đoán **NEI** (conf 0.9758, lấy được nguồn: có)
  - Claim: Hội  nghị  COP27  do  Ai  Cập  đăng  cai  diễn  ra  từ  ngày  7-18/11  tại  TP

### REF_NUMBER

Đổi một con số -> phải REFUTED. SUPPORTED = verifier mù số liệu (false positive nguy hiểm).

1 lỗi. Ví dụ:

- `REF_NUMBER-022` vàng **REF** → dự đoán **NEI** (conf 0.9354, lấy được nguồn: có) — 27 -> 37
  - Claim: Diện tích này bằng 37% diện tích trồng sầu riêng của Việt Nam.

### REF_DIRECTION

Đổi tăng<->giảm -> phải REFUTED. SUPPORTED = verifier không hiểu chiều biến động.

4 lỗi. Ví dụ:

- `REF_DIRECTION-012` vàng **REF** → dự đoán **NEI** (conf 0.9592, lấy được nguồn: có)
  - Claim: Khi không có tiền vệ đánh chặn này trong đội hình, số bàn thua của MU giảm xuống đáng kể.
- `REF_DIRECTION-023` vàng **REF** → dự đoán **SUP** (conf 0.9264, lấy được nguồn: có)
  - Claim: Với tốc độ bắn 600 phát/phút, loại súng này phải được làm mát bằng nước, khiến khối lượng giảm thêm đáng kể.
  - Trích dẫn: Ukraine dùng vũ khí cổ để bảo vệ Bakhmut? Theo tờ The Telegraph, quân đội Ukraine đang sử dụng một loại súng máy được triển khai lần đầu tiên vào thế kỷ 19 trong nỗ lực chặn đứng các cuộc tấn công trực diện của quân đội 
- `REF_DIRECTION-031` vàng **REF** → dự đoán **SUP** (conf 0.9897, lấy được nguồn: có)
  - Claim: Phóng viên TTXVN tại Trung Đông dẫn số liệu do Cơ quan Thống kê Trung ương Liban công bố cho thấy nguyên nhân khiến lạm phát phi mã là do giá cả dịch vụ và hàng hóa gia giảm mạnh.
  - Trích dẫn: Liban vừa tiếp tục ghi nhận siêu lạm phát trong tháng thứ 32 liên tiếp khi tỷ lệ trượt giá ở nước này trong tháng 2 vừa qua đã lên tới con số 190%. Phóng viên TTXVN tại Trung Đông dẫn số liệu do Cơ quan Thống kê Trung ươ
- `REF_DIRECTION-032` vàng **REF** → dự đoán **SUP** (conf 0.9836, lấy được nguồn: có)
  - Claim: Cổ phiếu của Tập đoàn Đầu tư địa ốc No Va (Novaland) tăng nhẹ khi mở cửa phiên giao dịch cuối tuần, nhưng càng về cuối phiên càng thể hiện sự hưng phấn.
  - Trích dẫn: NVL tăng hết biên độ lên 11.900 đồng và khớp lệnh hơn 30 triệu cổ phiếu sau thông tin cổ đông đã thông qua tờ trình tăng vốn tối thiểu 29.000 tỷ đồng. Cổ phiếu của Tập đoàn Đầu tư địa ốc No Va (Novaland) giảm nhẹ khi mở 

### REF_NEGATION

Đổi 'đã'->'chưa' -> phải REFUTED. SUPPORTED = verifier bỏ qua phủ định.

7 lỗi. Ví dụ:

- `REF_NEGATION-000` vàng **REF** → dự đoán **SUP** (conf 0.9607, lấy được nguồn: có)
  - Claim: Chiều 28/3, tại Trụ sở Trung ương Đảng, Tổng Bí thư Nguyễn Phú Trọng chưa tiếp ông Vương Ninh, Ủy viên Trung ương Đảng, Bí thư Tỉnh ủy Vân Nam, Trung Quốc đang có chuyến thăm Việt Nam.
  - Trích dẫn: Chiều 28/3, tại Trụ sở Trung ương Đảng, Tổng Bí thư Nguyễn Phú Trọng đã tiếp ông Vương Ninh, Ủy viên Trung ương Đảng, Bí thư Tỉnh ủy Vân Nam, Trung Quốc đang có chuyến thăm Việt Nam. Ông Vương Ninh, Ủy viên Trung ương Đả
- `REF_NEGATION-007` vàng **REF** → dự đoán **SUP** (conf 0.8493, lấy được nguồn: có)
  - Claim: Sau khi sát hại nữ chủ tiệm Spa để cướp tài sản, hung thủ chưa bỏ trốn lên vùng Tây Nguyên để lẩn trốn.
  - Trích dẫn: (PLO)- Sau khi sát hại nữ chủ tiệm Spa để cướp tài sản, hung thủ đã bỏ trốn lên vùng Tây Nguyên để lẩn trốn. Tối ngày 24-3, Công an tỉnh Đồng Nai phối hợp Công an tỉnh Gia Lai bắt giữ Lê Minh Long (26 tuổi, ngụ huyện Địn
- `REF_NEGATION-008` vàng **REF** → dự đoán **SUP** (conf 0.8498, lấy được nguồn: có)
  - Claim: Gia đình, bạn bè của người mẫu Hồng Kông (Trung Quốc) Abby Choi (Thái Thiên Phượng) bị giết, phân xác chưa đến bên ngoài hiện trường vụ án ở Tai Po để cúng viếng cô.
  - Trích dẫn: (NLĐO) - Gia đình, bạn bè của người mẫu Hồng Kông (Trung Quốc) Abby Choi (Thái Thiên Phượng) bị giết, phân xác đã đến bên ngoài hiện trường vụ án ở Tai Po để cúng viếng cô. Cha mẹ, chồng, họ hàng cùng bạn bè thân thiết c
- `REF_NEGATION-015` vàng **REF** → dự đoán **SUP** (conf 0.9651, lấy được nguồn: có)
  - Claim: Tổng tư lệnh Ukraine công bố video bắn tên lửa đánh chìm tàu đổ bộ Nga Theo ông Putin, việc xây dựng kho tàng ở Belarus sẽ hoàn tất trước ngày 1.7, nhưng một số chuyên gia chưa bày tỏ hoài nghi về mốc thời gian này.
  - Trích dẫn: Tổng tư lệnh Ukraine công bố video bắn tên lửa đánh chìm tàu đổ bộ Nga Theo ông Putin, việc xây dựng kho tàng ở Belarus sẽ hoàn tất trước ngày 1.7, nhưng một số chuyên gia đã bày tỏ hoài nghi về mốc thời gian này. Trả lờ
- `REF_NEGATION-021` vàng **REF** → dự đoán **SUP** (conf 0.5245, lấy được nguồn: có)
  - Claim: Thị trường chứng khoán chưa tốt hơn và tâm lý tiêu cực giảm khá nhiều trước động thái các ngân hàng trung ương thế giới "giải cứu" những ngân hàng gặp khó khăn.
  - Trích dẫn: Thị trường chứng khoán đã tốt hơn và tâm lý tiêu cực giảm khá nhiều trước động thái các ngân hàng trung ương thế giới "giải cứu" những ngân hàng gặp khó khăn. Thị trường cũng kỳ vọng Cục Dự trữ Liên bang Mỹ (FED) có thể 
- `REF_NEGATION-047` vàng **REF** → dự đoán **SUP** (conf 0.5158, lấy được nguồn: có)
  - Claim: Công an TP HCM chưa có giấy triệu tập ca sĩ Vy Oanh do liên quan đến đơn tố giác của con trai bà Nguyễn Phương Hằng.
  - Trích dẫn: (NLĐO) – Công an TP HCM đã có giấy triệu tập ca sĩ Vy Oanh do liên quan đến đơn tố giác của con trai bà Nguyễn Phương Hằng. Ngày 24-3, một nguồn tin xác nhận Phòng Cảnh sát Hình sự Công an TP HCM đã triệu tập bà Nguyễn T
- `REF_NEGATION-049` vàng **REF** → dự đoán **SUP** (conf 0.9711, lấy được nguồn: có)
  - Claim: USD tự do giảm mạnh Chỉ số USD-Index đóng cửa tuần dừng ở mức 102,7 điểm, đây vẫn là vùng giá thấp nhất trong 2 tháng trở lại đây dù chưa tăng nhẹ 0,5% so với phiên liền trước.
  - Trích dẫn: Theo dữ liệu của Bloomberg, các quỹ này vừa mua 300.000 ounce vàng (hơn 360.000 lượng vàng) trong một phiên - mức giao dịch lớn nhất trong một ngày, kể từ tháng 6/2022. USD tự do giảm mạnh Chỉ số USD-Index đóng cửa tuần 

### NEI_PARTIAL

Câu thật + chi tiết bịa -> phải NEI. SUPPORTED = 'ủng hộ một phần' bị coi là ủng hộ toàn phần.

Không có lỗi.

### NEI_FICTIONAL

Sự kiện bịa -> phải NEI. SUPPORTED/REFUTED = suy diễn từ bài không liên quan.

16 lỗi. Ví dụ:

- `NEI_FICTIONAL-000` vàng **NEI** → dự đoán **REF** (conf 0.9236, lấy được nguồn: —)
  - Claim: Việt Nam phóng thành công tàu thăm dò lên sao Hỏa từ bãi phóng ở Quảng Ngãi
  - Trích dẫn: Quỹ đạo của Trái Đất và sao Kim trở nên kỳ cục hoặc bay theo hình bầu dục dài đến mức có thể lao qua rất gần nhau. Thay đổi ở quỹ đạo sau đó giải phóng năng lượng tác động tới sao Thủy, khiến hành tinh này nhanh chóng ba
- `NEI_FICTIONAL-001` vàng **NEI** → dự đoán **REF** (conf 0.9142, lấy được nguồn: —)
  - Claim: Nhà khoa học Việt Nam tìm ra vắc xin phòng chống tất cả các loại cúm vĩnh viễn
  - Trích dẫn: Đặc biệt, trạm y tế hỗ trợ nhân viên y tế trường học khám, khai thác triệu chứng, tiền sử ăn uống, sinh hoạt của học sinh và phối hợp với trung tâm y tế giám sát theo dõi tình hình dịch bệnh tại trường, báo cáo về Trung 
- `NEI_FICTIONAL-002` vàng **NEI** → dự đoán **REF** (conf 0.8585, lấy được nguồn: —)
  - Claim: Hà Nội khai trương tuyến tàu điện ngầm dưới đáy Hồ Gươm dài 12 km
  - Trích dẫn: Sau 6 năm dừng hoạt động dịch vụ văn hóa, thể thao ở Hồ Tây, Hà Nội dự kiến cho phép nhiều loại hình kinh doanh mở lại, trong đó có tàu du lịch. Dự thảo quy định quản lý Hồ Tây được UBND TP Hà Nội bắt đầu lấy ý kiến từ 2
- `NEI_FICTIONAL-004` vàng **NEI** → dự đoán **REF** (conf 0.981, lấy được nguồn: —)
  - Claim: Thành phố Đà Lạt ghi nhận tuyết rơi dày 2 mét suốt ba ngày liên tiếp
  - Trích dẫn: Để phong phú các sản phẩm tem chơi phục vụ khách hàng và người sưu tập tem, Bưu điện Việt Nam thiết kế 5 con dấu có hình ảnh phù hợp với loài hoa (trong đó có 1 con dấu mang địa danh Đà Lạt). Trước đó, Bộ Thông tin và Tr
- `NEI_FICTIONAL-005` vàng **NEI** → dự đoán **REF** (conf 0.9656, lấy được nguồn: —)
  - Claim: Làng gốm Bát Tràng nung thành công chiếc bình gốm cao 80 mét trong một lò
  - Trích dẫn: Giả thiết khác hợp kim đúc tượng thuộc giai đoạn 1658-1720, với kỹ nghệ trích kẽm từ quặng lẫn than, nung khử trong bình gốm. Kẽm thoát ra khỏi quặng, nhỏ vào nồi đồng - chì - thiếc nấu đỏ, để kẽm kết lắng tạo thành hợp 
- `NEI_FICTIONAL-006` vàng **NEI** → dự đoán **REF** (conf 0.9851, lấy được nguồn: —)
  - Claim: Vịnh Hạ Long được công nhận là kỳ quan thứ tám của hệ Mặt Trời
  - Trích dẫn: Nhà vật lý này cũng nhấn mạnh rằng kính viễn vọng Không gian Spitzer đã không thể giúp nhận định về bầu khí quyển trên Trappist-1b mặc dù đã có 28 lần quan sát nhật thực thứ cấp, trong khi James Webb làm được điều này ch
- `NEI_FICTIONAL-008` vàng **NEI** → dự đoán **SUP** (conf 0.6222, lấy được nguồn: —)
  - Claim: Học sinh Kon Tum được nghỉ học để quan sát nhật thực toàn phần kéo dài 3 tuần
  - Trích dẫn: Gần 11.400 máy tính bảng được trao tặng học sinh vùng sâu, vùng xa trong tỉnh Kon Tum vào chiều 7/3. Đây là hoạt động ý nghĩa của Ngân hàng Thương mại cổ phần Ngoại thương Kon Tum (Vietcombank Kon Tum) tài trợ cho học si
- `NEI_FICTIONAL-009` vàng **NEI** → dự đoán **SUP** (conf 0.7345, lấy được nguồn: —)
  - Claim: Cá voi xanh dài 40 mét bơi ngược dòng sông Hồng lên tới Lào Cai
  - Trích dẫn: Tối ngày 28/3 tại Hà Nội, Sở Du lịch Hà Nội phối hợp với Sở Du lịch các địa phương: Lào Cai, Quảng Ninh, Hải Phòng, cùng với chính quyền châu Hồng Hà (tỉnh Vân Nam, Trung Quốc) tổ chức Hội nghị xúc tiến khởi động tuyến d
