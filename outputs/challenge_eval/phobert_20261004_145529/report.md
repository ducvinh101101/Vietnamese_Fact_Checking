# Báo cáo đánh giá challenge set

- Engine: **phobert** · Số claim: 380 · Lỗi chạy: 0
- Độ trễ: p50 0.569s · p95 0.723s
- Lưu ý: claim lấy từ chính kho (in-distribution), REF_* là biến đổi tổng hợp, NEI theo giả định kho đóng.
  Kết quả là CHẨN ĐOÁN điểm yếu, không thay cho đánh giá trên test split có nhãn người.

## Tổng quan

| | Accuracy | Macro-F1 | F1 SUP | F1 REF | F1 NEI |
|---|---|---|---|---|---|
| Pipeline (thô) | 78.9% | 79.8% | 77.0% | 78.5% | 83.8% |
| + GuardedVerifier | 81.8% | 81.9% | 87.9% | 78.1% | 79.6% |

Guard chặn **46** verdict sai, nhưng hạ nhầm **7** verdict đúng.

## Ma trận nhầm lẫn (thô) — hàng: nhãn đúng, cột: dự đoán

| | SUP | REF | NEI |
|---|---|---|---|
| **SUP** | 114 | 4 | 2 |
| **REF** | 52 | 124 | 4 |
| **NEI** | 10 | 8 | 62 |

## Theo từng loại hiện tượng

| Loại | n | Acc | Acc+guard | Hit@k nguồn | Acc khi lấy được nguồn | Acc khi trượt nguồn | SUP sai | Phân bố dự đoán |
|---|---|---|---|---|---|---|---|---|
| SUP_VERBATIM | 60 | 93.3% | 93.3% | 100.0% | 93.3% | — | — | {'SUP': 56, 'REF': 4} |
| SUP_FORMAT | 60 | 96.7% | 95.0% | 100.0% | 96.7% | — | — | {'SUP': 58, 'NEI': 2} |
| REF_NUMBER | 60 | 95.0% | 91.7% | 100.0% | 95.0% | — | 3.3% | {'REF': 57, 'SUP': 2, 'NEI': 1} |
| REF_DIRECTION | 60 | 48.3% | 45.0% | 100.0% | 48.3% | — | 46.7% | {'REF': 29, 'NEI': 3, 'SUP': 28} |
| REF_NEGATION | 60 | 63.3% | 60.0% | 100.0% | 63.3% | — | 36.7% | {'SUP': 22, 'REF': 38} |
| NEI_PARTIAL | 60 | 100.0% | 100.0% | 100.0% | 100.0% | — | 0.0% | {'NEI': 60} |
| NEI_FICTIONAL | 20 | 10.0% | 100.0% | — | — | — | 50.0% | {'REF': 8, 'SUP': 10, 'NEI': 2} |

## Cách đọc & ví dụ lỗi

### SUP_VERBATIM

Câu nguyên văn trong kho -> phải SUPPORTED. Sai = verifier/retrieval yếu cả ở ca dễ nhất.

4 lỗi. Ví dụ:

- `SUP_VERBATIM-006` vàng **SUP** → dự đoán **REF** (conf 0.5915, lấy được nguồn: có)
  - Claim: Với phương án trên, Bộ Giáo dục và Đào tạo chỉ đạo chung, ban hành quy chế, hướng dẫn tổ chức kỳ thi.
  - Trích dẫn: Thời gian tổ chức thi theo lịch chung trên toàn quốc phù hợp với kế hoạch thời gian năm học nhưng sẽ có linh hoạt, ứng phó với các tình huống chịu ảnh hưởng nặng nề của thiên tai, dịch bệnh trên phạm vi toàn quốc và từng
- `SUP_VERBATIM-019` vàng **SUP** → dự đoán **REF** (conf 0.9633, lấy được nguồn: có)
  - Claim: Trong quá trình tổ chức, các cơ sở giáo dục phải đảm bảo an toàn cho học sinh tham gia.
  - Trích dẫn: Đối với các hoạt động giáo dục thuộc chương trình, kế hoạch do các cơ quan có thẩm quyền đã phê duyệt, Sở GD&ĐT yêu cầu các cơ sở giáo dục thực hiện hoạt động giáo dục trải nghiệm ngoài nhà trường theo đúng các bản quy đ
- `SUP_VERBATIM-029` vàng **SUP** → dự đoán **REF** (conf 0.5431, lấy được nguồn: có)
  - Claim: Tại TPHCM: Số 2A Nguyễn Thị Minh Khai, phường Đa Kao, Quận 1. 2.
  - Trích dẫn: Các chứng chỉ này cũng được một số địa phương dùng để cộng điểm ưu tiên hoặc tuyển thẳng học sinh vào lớp 10, xét giải học sinh giỏi cấp sở hoặc đưa vào chính sách ưu đãi, trợ cấp cho cán bộ, công chức, viên chức. 5 địa 
- `SUP_VERBATIM-039` vàng **SUP** → dự đoán **REF** (conf 0.5616, lấy được nguồn: có)
  - Claim: "Cái thứ rác rưởi này sẽ phát biểu trước các bạn lúc 13h.
  - Trích dẫn: Khiếu nại tập trung vào một bài đăng trên trang Facebook của bà vào ngày 21-3, tức một ngày trước khi Tổng thống Pháp Emmanuel Macron trả lời phỏng vấn vào giờ ăn trưa trên Đài truyền hình TF1 để bảo vệ kế hoạch cải cách

### SUP_FORMAT

Chỉ khác khoảng trắng/dấu câu cuối -> phải giống SUP_VERBATIM. Thấp hơn = nhạy định dạng.

2 lỗi. Ví dụ:

- `SUP_FORMAT-002` vàng **SUP** → dự đoán **NEI** (conf 0.061, lấy được nguồn: có)
  - Claim: Cuối  cùng,  ca  mổ  được  tiến  hành  và  thành  công  sau  hai  tiếng  nỗ  lực  của  các  BS
- `SUP_FORMAT-016` vàng **SUP** → dự đoán **NEI** (conf 0.9353, lấy được nguồn: có)
  - Claim: Sự  kiện  tắt  đèn  hưởng  ứng  Chiến  dịch  Giờ  Trái  đất  sẽ  diễn  ra  từ  20h30  đến  21h30  thứ  Bảy  ngày  25/3

### REF_NUMBER

Đổi một con số -> phải REFUTED. SUPPORTED = verifier mù số liệu (false positive nguy hiểm).

3 lỗi. Ví dụ:

- `REF_NUMBER-007` vàng **REF** → dự đoán **SUP** (conf 0.9353, lấy được nguồn: có) — 2 -> 5
  - Claim: Tin tức TV triển khai 5 thể loại trong truyền hình là phóng sự và Talk show.
  - Trích dẫn: Tin tức TV triển khai 2 thể loại trong truyền hình là phóng sự và Talk show. Nhận thức được đây là hai thể loại khó, công phu, nhưng phù hợp với đặc thù của đơn vị, nên chúng tôi đã đầu tư thời gian để tự học, tự tìm hiể
- `REF_NUMBER-020` vàng **REF** → dự đoán **SUP** (conf 0.9811, lấy được nguồn: có) — 5 -> 8
  - Claim: Tripzilla, chuyên trang du lịch trực tuyến hàng đầu Đông Nam Á, gợi ý 8 điểm đến an toàn nhất khu vực dành cho phụ nữ đi du lịch một mình.
  - Trích dẫn: (Chinhphu.vn) - Tripzilla, chuyên trang du lịch trực tuyến hàng đầu Đông Nam Á, gợi ý 5 điểm đến an toàn nhất khu vực dành cho phụ nữ đi du lịch một mình. Thủ đô Hà Nội, đại diện duy nhất của Việt Nam, được nhắc đến đầu 
- `REF_NUMBER-022` vàng **REF** → dự đoán **NEI** (conf 0.8207, lấy được nguồn: có) — 27 -> 37
  - Claim: Diện tích này bằng 37% diện tích trồng sầu riêng của Việt Nam.

### REF_DIRECTION

Đổi tăng<->giảm -> phải REFUTED. SUPPORTED = verifier không hiểu chiều biến động.

31 lỗi. Ví dụ:

- `REF_DIRECTION-002` vàng **REF** → dự đoán **NEI** (conf 0.853, lấy được nguồn: có)
  - Claim: Với giá xăng dầu tăng mạnh trong kỳ điều hành này, liên Bộ không chi Quỹ Bình ổn giá xăng dầu.
- `REF_DIRECTION-003` vàng **REF** → dự đoán **SUP** (conf 0.9632, lấy được nguồn: có)
  - Claim: Đại hội thông qua kế hoạch tổng doanh thu hợp nhất đạt 10.875 tỷ đồng, lợi nhuận sau thuế đạt 3.000 tỷ đồng, lần lượt tăng 25% và 50% so với năm 2022.
  - Trích dẫn: (Dân trí) - Tại phiên họp cổ đông, khi được đề xuất mua thêm cổ phiếu, ông Đào Hữu Huyền, Chủ tịch HĐQT Hóa chất Đức Giang, cho biết không có chủ trương mua vào cổ phiếu vì không muốn gia đình chi phối cổ phần. Công ty c
- `REF_DIRECTION-005` vàng **REF** → dự đoán **SUP** (conf 0.9627, lấy được nguồn: có)
  - Claim: Khép lại năm 2022, LPB đạt 5.690 tỷ đồng tổng lợi nhuận kế toán trước thuế và 4.510 tỷ đồng lãi sau thuế, lần lượt giảm 56% và 57% so với năm trước.
  - Trích dẫn: Việc kiểm soát tốt chi phí hoạt động và sự hiệu quả của mảng dịch vụ là điểm đáng chú ý trong báo cáo kết quả kinh doanh của LPB quý IV vừa qua. Cụ thể, thu nhập từ hoạt động dịch vụ trong kỳ của ngân hàng đạt 1.106 tỷ đ
- `REF_DIRECTION-006` vàng **REF** → dự đoán **SUP** (conf 0.9506, lấy được nguồn: có)
  - Claim: Thanh Hóa đề xuất trung ương cho cơ chế đặc thù giảm 10 phó giám đốc sở vì tỉnh có diện tích lớn, dân số đông, khối lượng công việc nhiều.
  - Trích dẫn: Thanh Hóa đề xuất trung ương cho cơ chế đặc thù tăng 10 phó giám đốc sở vì tỉnh có diện tích lớn, dân số đông, khối lượng công việc nhiều. Chủ tịch UBND tỉnh Đỗ Minh Tuấn vừa đề xuất Bộ Nội vụ xem xét, báo cáo Chính phủ 
- `REF_DIRECTION-007` vàng **REF** → dự đoán **SUP** (conf 0.9259, lấy được nguồn: có)
  - Claim: Năm 2021, con số này tăng lên còn... 2,2 triệu bảng.
  - Trích dẫn: Trong cuộc chơi thể hiện sức mạnh "trường vốn", sau cùng, vợ chồng cựu danh thủ David Beckham đã chứng tỏ được tiềm lực tài chính, năng lực kinh doanh và tầm nhìn chiến lược. Trong cuộc phỏng vấn mới thực hiện với tạp ch
- `REF_DIRECTION-008` vàng **REF** → dự đoán **SUP** (conf 0.969, lấy được nguồn: có)
  - Claim: Bà Kristalina Georgieva, giám đốc điều hành của Quỹ Tiền tệ quốc tế (IMF), hôm 26-3 cho biết “rủi ro đối với sự ổn định tài chính đã giảm xuống” và các nhà hoạch định chính sách phải luôn cảnh giác.
  - Trích dẫn: Nỗ lực của các ngân hàng trung ương nhằm kiềm chế lạm phát bằng cách tăng lãi suất đã gây ra tình trạng hỗn loạn trong lĩnh vực ngân hàng, dẫn đến sự sụp đổ của Ngân hàng Valley Silicon và Ngân hàng Signature ở Mỹ trong 
- `REF_DIRECTION-009` vàng **REF** → dự đoán **SUP** (conf 0.6361, lấy được nguồn: có)
  - Claim: Mỗi lít dầu diesel 0.05S giảm 250 đồng/lít, lên 20.500 đồng/lít.
  - Trích dẫn: (Chinhphu.vn) - Mỗi lít xăng RON 95-III và E5 RON 92 giảm 780 đồng, các mặt hàng dầu cũng giảm 800-1.250 đồng từ 15h hôm nay. Giá xăng, dầu đồng loạt giảm mạnh. Ảnh minh họa Cụ thể, giá xăng RON 95-III (loại phổ biến trê
- `REF_DIRECTION-012` vàng **REF** → dự đoán **SUP** (conf 0.9262, lấy được nguồn: có)
  - Claim: Khi không có tiền vệ đánh chặn này trong đội hình, số bàn thua của MU giảm xuống đáng kể.
  - Trích dẫn: Trong đó, sự vắng mặt của tiền vệ người Brazil Casemiro là đáng chú ý nhất. Trong 7 trận cầu thủ này không ra sân, Quỷ đỏ chỉ thắng 3 trận, thua 3 trận và hòa 1 trận. Thiếu vắng Casemiro, hiệu quả hàng công của MU là giả

### REF_NEGATION

Đổi 'đã'->'chưa' -> phải REFUTED. SUPPORTED = verifier bỏ qua phủ định.

22 lỗi. Ví dụ:

- `REF_NEGATION-000` vàng **REF** → dự đoán **SUP** (conf 0.9898, lấy được nguồn: có)
  - Claim: Chiều 28/3, tại Trụ sở Trung ương Đảng, Tổng Bí thư Nguyễn Phú Trọng chưa tiếp ông Vương Ninh, Ủy viên Trung ương Đảng, Bí thư Tỉnh ủy Vân Nam, Trung Quốc đang có chuyến thăm Việt Nam.
  - Trích dẫn: Chiều 28/3, tại Trụ sở Trung ương Đảng, Tổng Bí thư Nguyễn Phú Trọng đã tiếp ông Vương Ninh, Ủy viên Trung ương Đảng, Bí thư Tỉnh ủy Vân Nam, Trung Quốc đang có chuyến thăm Việt Nam. Ông Vương Ninh, Ủy viên Trung ương Đả
- `REF_NEGATION-002` vàng **REF** → dự đoán **SUP** (conf 0.6807, lấy được nguồn: có)
  - Claim: Bộ Giáo dục và Đào tạo (GD&ĐT) cho biết chưa nhận được ý kiến cử tri kiến nghị ban hành thống nhất, đồng bộ sách giáo khoa trên toàn quốc.
  - Trích dẫn: (Chinhphu.vn) - Bộ Giáo dục và Đào tạo (GD&ĐT) cho biết đã nhận được ý kiến cử tri kiến nghị ban hành thống nhất, đồng bộ sách giáo khoa trên toàn quốc. Thực hiện xã hội hóa biên soạn sách giáo khoa; có một số sách giáo 
- `REF_NEGATION-003` vàng **REF** → dự đoán **SUP** (conf 0.9793, lấy được nguồn: có)
  - Claim: Korea Herald dẫn một số thông tin từ truyền thông Hàn Quốc cho rằng dường như chưa có sai sót trong vấn đề tiếp tân trước cuộc họp thượng đỉnh Mỹ - Hàn.
  - Trích dẫn: Bất chấp Văn phòng tổng thống cho biết hai vụ từ chức trên đều vì lý do cá nhân, việc các nhân vật quan trọng bộ phận tiếp tân từ chức liên tiếp là điều hiếm thấy, đặc biệt trong bối cảnh tổng thống sắp tham dự các sự ki
- `REF_NEGATION-007` vàng **REF** → dự đoán **SUP** (conf 0.9865, lấy được nguồn: có)
  - Claim: Sau khi sát hại nữ chủ tiệm Spa để cướp tài sản, hung thủ chưa bỏ trốn lên vùng Tây Nguyên để lẩn trốn.
  - Trích dẫn: (PLO)- Sau khi sát hại nữ chủ tiệm Spa để cướp tài sản, hung thủ đã bỏ trốn lên vùng Tây Nguyên để lẩn trốn. Tối ngày 24-3, Công an tỉnh Đồng Nai phối hợp Công an tỉnh Gia Lai bắt giữ Lê Minh Long (26 tuổi, ngụ huyện Địn
- `REF_NEGATION-008` vàng **REF** → dự đoán **SUP** (conf 0.9867, lấy được nguồn: có)
  - Claim: Gia đình, bạn bè của người mẫu Hồng Kông (Trung Quốc) Abby Choi (Thái Thiên Phượng) bị giết, phân xác chưa đến bên ngoài hiện trường vụ án ở Tai Po để cúng viếng cô.
  - Trích dẫn: (NLĐO) - Gia đình, bạn bè của người mẫu Hồng Kông (Trung Quốc) Abby Choi (Thái Thiên Phượng) bị giết, phân xác đã đến bên ngoài hiện trường vụ án ở Tai Po để cúng viếng cô. Cha mẹ, chồng, họ hàng cùng bạn bè thân thiết c
- `REF_NEGATION-015` vàng **REF** → dự đoán **SUP** (conf 0.9889, lấy được nguồn: có)
  - Claim: Tổng tư lệnh Ukraine công bố video bắn tên lửa đánh chìm tàu đổ bộ Nga Theo ông Putin, việc xây dựng kho tàng ở Belarus sẽ hoàn tất trước ngày 1.7, nhưng một số chuyên gia chưa bày tỏ hoài nghi về mốc thời gian này.
  - Trích dẫn: Tổng tư lệnh Ukraine công bố video bắn tên lửa đánh chìm tàu đổ bộ Nga Theo ông Putin, việc xây dựng kho tàng ở Belarus sẽ hoàn tất trước ngày 1.7, nhưng một số chuyên gia đã bày tỏ hoài nghi về mốc thời gian này. Trả lờ
- `REF_NEGATION-018` vàng **REF** → dự đoán **SUP** (conf 0.9905, lấy được nguồn: có)
  - Claim: Chiều 25-2, ông Sengphet Houngboungnuang - Đại sứ đặc mệnh toàn quyền nước của Lào tại Việt Nam - dẫn đầu đoàn công tác chưa đến thăm và làm việc tại Trường ĐH Cửu Long.
  - Trích dẫn: (NLĐO) - Chiều 25-2, ông Sengphet Houngboungnuang - Đại sứ đặc mệnh toàn quyền nước của Lào tại Việt Nam - dẫn đầu đoàn công tác đã đến thăm và làm việc tại Trường ĐH Cửu Long. Tiếp và làm việc với đoàn có Nhà giáo ưu tú
- `REF_NEGATION-020` vàng **REF** → dự đoán **SUP** (conf 0.968, lấy được nguồn: có)
  - Claim: Sau 11 lần phẫu thuật, Bệnh viện Chợ Rẫy, TP.HCM chưa cứu sống thành công bệnh nhân bị container cán qua người, đa chấn thương nặng.
  - Trích dẫn: (PLO)- Sau 11 lần phẫu thuật, Bệnh viện Chợ Rẫy, TP.HCM đã cứu sống thành công bệnh nhân bị container cán qua người, đa chấn thương nặng. Chiều 14-3, Bệnh viện (BV) Chợ Rẫy cho biết nơi đây vừa cứu sống bệnh nhân VMH (na

### NEI_PARTIAL

Câu thật + chi tiết bịa -> phải NEI. SUPPORTED = 'ủng hộ một phần' bị coi là ủng hộ toàn phần.

Không có lỗi.

### NEI_FICTIONAL

Sự kiện bịa -> phải NEI. SUPPORTED/REFUTED = suy diễn từ bài không liên quan.

18 lỗi. Ví dụ:

- `NEI_FICTIONAL-000` vàng **NEI** → dự đoán **REF** (conf 0.9014, lấy được nguồn: —)
  - Claim: Việt Nam phóng thành công tàu thăm dò lên sao Hỏa từ bãi phóng ở Quảng Ngãi
  - Trích dẫn: Quỹ đạo của Trái Đất và sao Kim trở nên kỳ cục hoặc bay theo hình bầu dục dài đến mức có thể lao qua rất gần nhau. Thay đổi ở quỹ đạo sau đó giải phóng năng lượng tác động tới sao Thủy, khiến hành tinh này nhanh chóng ba
- `NEI_FICTIONAL-001` vàng **NEI** → dự đoán **SUP** (conf 0.8519, lấy được nguồn: —)
  - Claim: Nhà khoa học Việt Nam tìm ra vắc xin phòng chống tất cả các loại cúm vĩnh viễn
  - Trích dẫn: Theo Bộ Y tế, tình hình dịch bệnh truyền nhiễm trên toàn cầu hiện nay được dự báo vẫn diễn biến khó lường. Dịch COVID-19 hiện vẫn là tình trạng khẩn cấp về sức khỏe cộng đồng quốc tế, tiềm ẩn nguy cơ bùng phát với các bi
- `NEI_FICTIONAL-002` vàng **NEI** → dự đoán **SUP** (conf 0.9572, lấy được nguồn: —)
  - Claim: Hà Nội khai trương tuyến tàu điện ngầm dưới đáy Hồ Gươm dài 12 km
  - Trích dẫn: Sau 6 năm dừng hoạt động dịch vụ văn hóa, thể thao ở Hồ Tây, Hà Nội dự kiến cho phép nhiều loại hình kinh doanh mở lại, trong đó có tàu du lịch. Dự thảo quy định quản lý Hồ Tây được UBND TP Hà Nội bắt đầu lấy ý kiến từ 2
- `NEI_FICTIONAL-004` vàng **NEI** → dự đoán **REF** (conf 0.7902, lấy được nguồn: —)
  - Claim: Thành phố Đà Lạt ghi nhận tuyết rơi dày 2 mét suốt ba ngày liên tiếp
  - Trích dẫn: Để phong phú các sản phẩm tem chơi phục vụ khách hàng và người sưu tập tem, Bưu điện Việt Nam thiết kế 5 con dấu có hình ảnh phù hợp với loài hoa (trong đó có 1 con dấu mang địa danh Đà Lạt). Trước đó, Bộ Thông tin và Tr
- `NEI_FICTIONAL-005` vàng **NEI** → dự đoán **REF** (conf 0.8246, lấy được nguồn: —)
  - Claim: Làng gốm Bát Tràng nung thành công chiếc bình gốm cao 80 mét trong một lò
  - Trích dẫn: Giả thiết khác hợp kim đúc tượng thuộc giai đoạn 1658-1720, với kỹ nghệ trích kẽm từ quặng lẫn than, nung khử trong bình gốm. Kẽm thoát ra khỏi quặng, nhỏ vào nồi đồng - chì - thiếc nấu đỏ, để kẽm kết lắng tạo thành hợp 
- `NEI_FICTIONAL-006` vàng **NEI** → dự đoán **REF** (conf 0.6943, lấy được nguồn: —)
  - Claim: Vịnh Hạ Long được công nhận là kỳ quan thứ tám của hệ Mặt Trời
  - Trích dẫn: Nhà vật lý này cũng nhấn mạnh rằng kính viễn vọng Không gian Spitzer đã không thể giúp nhận định về bầu khí quyển trên Trappist-1b mặc dù đã có 28 lần quan sát nhật thực thứ cấp, trong khi James Webb làm được điều này ch
- `NEI_FICTIONAL-007` vàng **NEI** → dự đoán **SUP** (conf 0.8914, lấy được nguồn: —)
  - Claim: Việt Nam xây dựng thang máy vũ trụ đầu tiên của châu Á tại Cần Thơ
  - Trích dẫn: HK Express đang khai thác toàn bộ máy bay Airbus, với đội bay hiện tại gồm 27 máy bay thuộc dòng A320 gồm 11 chiếc A321ceo, 10 chiếc A320neo, 5 chiếc A320ceo và chiếc A321neo đầu tiên này. HK Express có các điểm đến chủ 
- `NEI_FICTIONAL-008` vàng **NEI** → dự đoán **SUP** (conf 0.948, lấy được nguồn: —)
  - Claim: Học sinh Kon Tum được nghỉ học để quan sát nhật thực toàn phần kéo dài 3 tuần
  - Trích dẫn: Gần 11.400 máy tính bảng được trao tặng học sinh vùng sâu, vùng xa trong tỉnh Kon Tum vào chiều 7/3. Đây là hoạt động ý nghĩa của Ngân hàng Thương mại cổ phần Ngoại thương Kon Tum (Vietcombank Kon Tum) tài trợ cho học si
