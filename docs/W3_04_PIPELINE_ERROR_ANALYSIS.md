# W3-04 — Phân tích lỗi pipeline local

## Phạm vi và phương pháp

Audit chọn cố định 10 trong 415 dự đoán sai của W4-02. Các nhãn phân loại là triage quan sát được, không khẳng định nguyên nhân gốc: URL evidence vàng có mặt trong BM25 top-k chỉ là proxy URL-level, không chứng minh passage được trích dẫn đủ ngữ nghĩa.

| Nhóm triage | Số lỗi toàn bộ | Ý nghĩa quan sát được |
| --- | ---: | --- |
| retrieval_url_miss | 14 | URL evidence vàng không trong top-k. |
| nei_decision | 249 | Sai verdict có liên quan NEI dù URL vàng có trong top-k. |
| verifier_with_gold_url | 152 | URL vàng có trong top-k, không phải NEI, nhưng verdict vẫn sai. |

## 10 mẫu audit

| ID | Nhóm | Gold → dự đoán | Conf. | Hạng URL vàng | Claim (rút gọn) |
| --- | --- | --- | ---: | ---: | --- |
| 478 | retrieval_url_miss | REFUTED → SUPPORTED | 0.8711 | – | Cậu bé bị tổn hại do sử dụng ma túy hay liệu cậu có liên quan đến những người lớn trong video |
| 600 | retrieval_url_miss | REFUTED → SUPPORTED | 0.7542 | – | Hệ thống giáo dục của TP.HCM được trang bị tốt và có đội ngũ giáo viên được đào tạo đầy đủ về chương trình giảng dạy mới. |
| 67 | retrieval_url_miss | REFUTED → SUPPORTED | 0.8208 | – | Bệnh nhân có thể tự đến bệnh viện trước khi phẫu thuật. |
| 346 | retrieval_url_miss | NOT_ENOUGH_INFO → SUPPORTED | 0.6850 | – | Tình trạng của bệnh nhân xấu đi trong quá trình phẫu thuật nhưng bệnh nhân đã hồi phục sức khoẻ sau 3 tuần điều trị. |
| 1039 | nei_decision | REFUTED → NOT_ENOUGH_INFO | 0.8203 | 1 | Trong khi TikTok cần 6 tháng để đạt 100 triệu người dùng thì ChatGPT chỉ mất 2 tháng để thực hiện điều đó, theo Similar Web. |
| 1064 | nei_decision | REFUTED → NOT_ENOUGH_INFO | 0.8257 | 1 | Ông Nguyễn Hồng Sơn, Đại biện lâm thời Đại sứ quán Việt Nam tại Nhật Bản đánh giá việc ra đời Liên hiệp Hội có ý nghĩa hết sức to lớn góp phần giữ vai trò kết nối các hội, tổ chức… |
| 178 | nei_decision | NOT_ENOUGH_INFO → SUPPORTED | 0.7712 | 1 | Quần thể di tích quốc gia này bao gồm: thư viện tại Viện Pasteur Nha Trang lưu giữ nhiều kỷ vật liên quan đến việc nghiên cứu và cuộc đời ông tại căn nhà. |
| 245 | verifier_with_gold_url | REFUTED → SUPPORTED | 0.8671 | 1 | Quyết định công nhận Bảo vật Quốc gia đối với 7 hiện vật của Bắc Ninh vừa được trao bởi Phó Thủ tướng Trần Hồng Hà. |
| 719 | verifier_with_gold_url | REFUTED → SUPPORTED | 0.6233 | 1 | Mặc dù ông Châu cam kết sàng lọc nghiêm ngặt nội dung dành cho trẻ em nhưng Hạ viện Mỹ vẫn lo ngại về quyền lực của TikTok nắm giữ trẻ em Trung Quốc. |
| 1055 | verifier_with_gold_url | REFUTED → SUPPORTED | 0.5699 | 1 | Sau khi không còn hạn chế về Covid-19 thì kinh tế du lịch vẫn còn gặp khó khăn và chậm hồi phục, các đô thị lớn vẫn tích cực phục hồi du lịch. |

## Hành động rút ra

- `retrieval_url_miss`: ưu tiên cải thiện retrieval trước khi quy kết lỗi cho verifier; đánh giá URL-level hiện không thay thế qrels passage-level.
- `nei_decision`: rà soát threshold/hiệu chuẩn trên dev và evidence được trích dẫn; không tune lại bằng test này.
- `verifier_with_gold_url`: cần kiểm tra passage cụ thể, phủ định, thời gian và thực thể trước khi thay đổi model; URL đúng không đồng nghĩa passage đủ chứng cứ.

Artifact máy đọc: `outputs\metrics\w3_04_local_pipeline_error_audit.json`; bảng đầy đủ: `outputs\predictions\w3_04_local_pipeline_error_audit.csv`.
