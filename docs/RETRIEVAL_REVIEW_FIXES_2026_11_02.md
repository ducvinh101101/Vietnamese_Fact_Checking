# Sửa retrieval theo bản nhận xét ngày 02/11/2026

Đã đối chiếu bản nhận xét và sửa các lỗi có thể tái hiện trong code.

| Vấn đề | Thay đổi |
|---|---|
| Topical rerank bỏ điểm gốc | Kết hợp 85% điểm gốc chuẩn hoá và 15% độ phủ từ khoá có giới hạn. |
| Luôn trả top 1 | Thêm ngưỡng độ phủ 0,35 và tối thiểu hai từ nội dung; ứng dụng local cũng có lớp lọc, không đổi thứ tự BM25. BM25 thuần được giữ làm baseline cho benchmark. |
| Sai người cùng họ/tên đệm | Loại ứng viên chứa tiền tố tên trùng nhưng thiếu tên đầy đủ; không buộc đoạn dùng đại từ phải lặp tên. Không loại số khác nhau vì đó có thể là bằng chứng phản bác. |
| Trọng số metadata quá nhỏ theo thang BM25 | Chuẩn hoá BM25, dùng trọng số nhỏ 0,02 overlap và 0,005 authority để tránh đảo thứ hạng quá mạnh. |
| Sidebar thành passage đầu | Ưu tiên article/main/content, bỏ khối sidebar/related/recommend, chọn passage khớp nhất mỗi bài trước. |
| Charset robots sai | Thử codec đầu tiên rồi UTF-8/GBK; vẫn tuân Disallow và vẫn deny nếu không đọc được. |
| Bỏ ngày Tavily | Dùng khi trang báo không có ngày; lưu published_at_source và xuất JSON/CLI. Ngày trên trang được ưu tiên; không dùng retrieved_at làm ngày đăng. |
| Không tìm bổ sung | Tối đa 3 lượt: news có ngày → news bỏ hậu tố ngày → general trên nguồn gốc. Lượt nào cũng lọc ngày thật và độ liên quan; có diagnostics web_attempts. |
| Thiếu nguồn gốc | Thêm apex và www của SJC, Vietcombank, NCHMF và EVN. Nguồn doanh nghiệp mang loại other và authority 0,55. |
| Trang bảng giá không phải bài báo | Không dùng ngày index của Tavily cho nguồn doanh nghiệp/NCHMF thiếu ngày từ trang; HTML/JS không có snapshot có ngày vẫn bị loại. |
| “Tháng này” chấp nhận bài tháng trước | Web search và temporal gate dùng cùng mốc đầu tháng; tương tự cho tuần này và năm nay. Không nới cửa sổ chấp nhận để lấp kết quả rỗng. |

## Kiểm chứng

- Regression tests bao phủ trường hợp sai người, trùng từ chung chung, sidebar, charset robots, fallback 3 bước, ngày provider, ưu tiên ngày trên trang, và lọc từ đầu tháng.
- Benchmark 300 claim dev: BM25 R@1 URL = 95,67%; metadata rerank = 95,33%, R@5 = 98%. Báo cáo tại outputs/web_retrieval/review_quality_after.json. Đây là URL-level, không phải đánh giá ngữ nghĩa passage hay toàn bộ chuỗi hybrid.
- Tavily thật: sau khi áp dụng mốc đầu tháng, claim lãi suất lấy được bài VTC News ngày 02/11/2026: https://vtcnews.vn/khi-lai-suat-ha-nhiet-dong-tien-chay-ve-dau-ar1047593.html . Claim giá xăng RON95 vẫn chưa có bằng chứng đủ điều kiện.

## Giới hạn còn lại

Ngưỡng từ khoá và kiểm tên là heuristic, chưa phải mô hình ngữ nghĩa được hiệu chỉnh bằng passage qrels. Không thể cam kết top 1 luôn đúng. Chưa triển khai cross-encoder mới hoặc thay checkpoint verifier thành retriever: checkpoint NLI không tự động có ngưỡng liên quan đã được kiểm định.

Không có mạng, trang chặn bot hoặc nội dung chỉ nằm trong ảnh/JavaScript có thể vẫn không có bằng chứng. Chuỗi tìm kiếm bổ sung đã có nhưng không đảm bảo tìm được mọi nguồn mới. Trong các trường hợp đó hệ thống giữ NEI, không giả ngày và không vượt robots.

Thay đổi lớp lọc ở ứng dụng local làm thay đổi tập evidence đầu vào verifier; số đo end-to-end cũ không nên được coi là số đo của phiên bản mới nếu chưa đánh giá lại.
