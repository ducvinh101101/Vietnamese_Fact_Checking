# Kết quả human check — [điền mã đợt]

> Sao chép file này vào thư mục kết quả bằng lệnh ở Bước 2 của hướng dẫn. Mọi ô bên dưới đều chưa chấm; không có PASS mặc định.

## 1. Thông tin đợt chạy

- Người chấm:
- Ngày giờ chạy, múi giờ:
- Git commit / nhánh:
- Python:
- Ngày tham chiếu dùng trong app và CLI:
- Giao diện / cổng:
- Có key Tavily: Có / Không, không ghi giá trị key
- Runtime: PhoBERT / rule-based fallback / lỗi chưa chạy được
- Corpus/model/config có thay đổi so với commit không:
- Kết quả `check_release.py` và mục còn thiếu:
- Thư mục log/ảnh:

## 2. Bảng tổng hợp

Điểm top 1: `2` trực tiếp xác nhận/bác bỏ; `1` chỉ cùng chủ đề; `0` không liên quan; `U` chưa chấm đủ. Không có kết quả ghi `EMPTY`, lỗi môi trường ghi `BLOCKED`.

| ID | Mode | Claim ngắn | Top1 0/1/2/U/EMPTY/BLOCKED | Nguồn đúng thời điểm? | Verdict app | Nhãn người | Lỗi / ghi chú |
|---|---|---|---|---|---|---|---|
| HC-01 | Kho local | Lula 6 ngày | | N/A | | SUPPORTED theo ví dụ repo | |
| HC-02 | Kho local | Lula 10 ngày | | N/A | | REFUTED theo ví dụ repo | |
| HC-03 | Kho local | Lula không hoãn 6 ngày | | N/A | | REFUTED theo ví dụ repo | |
| HC-04 | Kho local | Đông Nam Á, bóng đá | | N/A | | NEI theo ví dụ repo | |
| HC-05 | Local + web | Xăng RON 95 chiều nay | | | | Chốt trước ở mục 3 | |
| HC-06 | Local + web | Vàng SJC hôm nay | | | | Chốt trước ở mục 3 | |
| HC-07 | Local + web | USD Vietcombank hôm nay | | | | Chốt trước ở mục 3 | |
| HC-08 | Local + web | Mưa lớn Hà Nội hôm nay | | | | Chốt trước ở mục 3 | |
| HC-09 | Local + web | Lãi suất tháng này | | | | Chốt trước ở mục 3 | |
| HC-10 | Local + web | Điện sinh hoạt tháng này | | | | Chốt trước ở mục 3 | |
| HC-11 | CLI đối chứng | Bật/tắt topical rerank | | | | Không tính claim độc lập | |
| HC-12 | CLI đối chứng | Cửa sổ hôm nay 0 ngày | | | | Không tính claim độc lập | |

## 3. Nguồn đối chứng — điền trước khi chạy sáu ca web

| ID | Claim nguyên văn | URL nguồn đã mở | Ngày đăng/cập nhật | Ngày sự kiện/hiệu lực | Câu/số liệu quyết định | Trong allowlist? | Nhãn người hoặc chưa xác định |
|---|---|---|---|---|---|---|---|
| HC-05 | Giá xăng RON 95 tăng chiều nay. | | | | | | |
| HC-06 | Giá vàng SJC hôm nay giảm. | | | | | | |
| HC-07 | Tỷ giá USD tại Vietcombank hôm nay tăng. | | | | | | |
| HC-08 | Hà Nội có mưa lớn hôm nay. | | | | | | |
| HC-09 | Lãi suất tiết kiệm tháng này giảm. | | | | | | |
| HC-10 | Giá điện sinh hoạt tăng tháng này. | | | | | | |

Với “tăng/giảm”, ghi mốc so sánh và loại giá/lãi suất cụ thể. Không tìm được nguồn xác định thì ghi CHƯA XÁC ĐỊNH, không mặc định claim sai.

## 4. Phiếu chi tiết — sao chép block này cho từng HC-01…HC-10

### HC-__ — [tên ca]

- Claim nguyên văn:
- Thời điểm chạy / mode / ngày tham chiếu:
- Có fallback rule-based hoặc cảnh báo mạng/quota không:
- Kỳ vọng và nguồn đối chứng:

| Rank | Passage ID | URL | Nội dung quyết định hoặc vị trí lưu | Điểm 0/1/2/U | Ngày app | Ngày nguồn | Đúng đối tượng/phạm vi/thời điểm? | Được cite? |
|---:|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |

- Passage top 1 có thật trong bài chính không:
- Tổng số web / local:
- Verdict app / citation IDs:
- Người chấm đồng ý verdict không, vì sao:
- YC1 không lạc chủ đề: PASS / FAIL / EMPTY / UNJUDGED / BLOCKED
- YC1 đủ trực tiếp: PASS / FAIL / EMPTY / UNJUDGED / BLOCKED
- YC2 nguồn đúng thời điểm: PASS / FAIL / EMPTY / N/A / UNJUDGED / BLOCKED
- Nếu rỗng: trả rỗng hợp lý / bỏ sót nguồn đã chốt / chưa xác định / lỗi runtime
- Log / ảnh:
- Kết quả lần thử lại nếu có, giữ cả lần đầu:

## 5. HC-11 — log và đối chứng rerank

- Claim được chọn:
- Ngày tham chiếu:
- Log default / rerank-off:
- Cảnh báo runtime:
- Các bước web đã chạy và kết quả từng bước:
- Cutoff / số bài cũ / không ngày / tương lai bị loại:
- Top 1 default và điểm người:
- Top 1 rerank-off và điểm người:
- Tập ứng viên có thay đổi không:
- Kết luận: cải thiện / xấu đi / không đổi / không cô lập được tác động
- Nếu thiếu nguồn, người chấm có URL phù hợp trong allowlist không:
- Nguyên nhân đã xác minh và phần còn suy đoán:

## 6. HC-12 — cửa sổ hôm nay 0 ngày

- Claim / ngày tham chiếu:
- Log:
- Bằng chứng còn lại / bị loại so với mặc định:
- Nguồn còn lại có đúng ngày đăng không:
- Nội dung có đúng sự kiện ngày cần kiểm tra không:
- Có bỏ bài hôm qua thông báo hiệu lực hôm nay không:
- Kết luận và giới hạn:

## 7. Báo lỗi — sao chép cho mỗi FAIL

### [P1/P2/P3] [Tên lỗi]

- Case ID / commit:
- Câu nhập hoặc lệnh tái hiện:
- Mode / ngày tham chiếu / cấu hình đối chứng:
- Kỳ vọng + URL/câu đối chứng:
- Kết quả thực tế + passage ID/rank/URL/ngày:
- Lỗi ở: discovery / extraction / rerank / thời gian / verdict / citation / UI / runtime
- Tác động tới kết luận:
- Đã thử lại chưa, kết quả:
- Log/ảnh:
- Chi tiết đã xác minh; phần nào mới là giả thuyết:

P1: nguồn/citation sai dẫn tới kết luận quyết định sai. P2: bỏ sót nguồn, rerank/date/extraction sai. P3: hiển thị/chẩn đoán chưa rõ, chưa chứng minh ảnh hưởng nội dung.

## 8. Tổng kết đợt chạy

Tính các case chính HC-01…HC-10 riêng với đối chứng HC-11/HC-12.

- Số case chính đã chạy / tổng 10:
- Số case có kết quả đã chấm top 1:
- Điểm 2 / điểm 1 / điểm 0:
- EMPTY / BLOCKED / U / NOT RUN:
- Tỷ lệ top 1 liên quan trên ca có kết quả đã chấm = (điểm 1 + điểm 2) / (điểm 0 + điểm 1 + điểm 2):
- Coverage = số ca có kết quả / số ca đã chạy không bị BLOCKED:
- Số ca web đã chấm đủ / tổng 6:
- Số ca web có nguồn đúng thời điểm:
- Số ca có nguồn phù hợp chốt trước trong allowlist / số bị bỏ sót:
- Fallback được kích hoạt / cứu được passage phù hợp / không cứu được / bị chặn:
- Verdict đúng / sai / chưa chấm / BLOCKED bởi runtime:
- Các lỗi P1 / P2 / P3:

Mẫu số bằng 0 ghi N/A. Không dùng ca trả rỗng để tự nâng tỷ lệ top 1; không gộp ca chưa xác minh thành PASS.

### Kết luận

- YC1 top 1 liên quan: CHƯA ĐẠT / CHƯA PHÁT HIỆN LỖI TRONG ... CA / CHƯA ĐỦ ĐIỀU KIỆN CHẤM
- Dẫn chứng:
- YC2 nguồn đúng thời điểm và tìm bổ sung: CHƯA ĐẠT / CHƯA PHÁT HIỆN LỖI TRONG ... CA / CHƯA ĐỦ ĐIỀU KIỆN CHẤM
- Dẫn chứng:
- Verdict/citation:
- Các phần bị chặn bởi môi trường hoặc thiếu đáp án người:
- Việc cần sửa trước, kèm Case ID:
- Người chấm / ngày chốt:
