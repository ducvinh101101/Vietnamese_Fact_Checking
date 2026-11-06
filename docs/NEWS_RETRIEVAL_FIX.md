# Truy xuất tin mới: thay đổi và cách kiểm tra

Chế độ Local + web dùng chung một cửa sổ ngày cho tìm kiếm và lọc bằng chứng:

- `Ngày 3/11` dùng năm của ngày tham chiếu. Ngày đầy đủ dùng đúng năm trong câu.
- Chọn ngày tham chiếu sẽ bật lọc cho cả câu chưa có dấu hiệu thời gian được nhận diện.
- Câu chỉ rõ năm/tháng lịch sử không bị ép sang hiện tại.
- Ngày đăng gần ngày sự kiện là điều kiện chọn nguồn, không tự chứng minh sự kiện đúng ngày đó.
- Bài không rõ ngày hoặc ngoài cửa sổ bị loại. Ngày đăng từ trang được ưu tiên hơn ngày từ chỉ mục.

Hệ thống tìm URL ứng viên qua RSS của VnExpress, Công lý, Dân Trí, Tuổi Trẻ,
VOV và sitemap theo ngày của Công lý. Khi chưa đủ khớp, Tavily thử tối đa ba
lượt trong quota sẵn có: phát biểu đầy đủ, cụm dẫn nguyên văn, rồi từ khóa.
Các lượt general mở phạm vi khám phá URL; bước tải trang vẫn chỉ nhận nguồn
trong allowlist. Các lượt được hợp nhất; kết quả khớp yếu không chặn lượt tiếp theo.
Toàn bộ nội dung trang được xét trước khi chọn tối đa ba đoạn; đoạn liền kề có
thể được giữ chung để cung cấp ngữ cảnh, trong giới hạn độ dài cũ.

Giao diện chỉ nhận phát biểu và các tùy chọn kiểm chứng; đã bỏ ô URL nguồn theo
yêu cầu người dùng. URL đáp án chỉ được dùng để chấm kiểm thử hoặc chẩn đoán
nội bộ, không được đưa vào lượt đo khả năng tự tìm nguồn.

Các trang được tải song song có giới hạn (5 luồng, tối đa 8 trang/lượt và 24
trang/phát biểu), robots.txt được cache ngắn theo hostname. Lỗi kết nối ngắt
giữa chừng của một trang không làm mất toàn bộ kết quả. Tiêu đề và ngày từ RSS
chỉ dùng để khám phá URL; đoạn bằng chứng vẫn phải được đọc từ bài gốc.

Câu trùng nguyên văn ngắn hơn 120 ký tự được giữ lại. Tiêu đề nằm ngoài vùng
article và phần tóm tắt từ metadata cũng được xét. Đoạn trùng đầy đủ được ưu
tiên trước các đoạn chỉ trùng từ khóa. Nhánh hybrid giữ đủ ứng viên của cả hai
nguồn trước khi lọc ngày, tránh việc local chiếm hết chỗ của web.

Luật đối chiếu nguyên văn ở hybrid nhận cả các câu liên tiếp, giữ nguyên số,
đơn vị, phủ định và thứ tự. Không nâng NEI chỉ vì một cụm từ nằm trong câu dài
hơn có thêm điều kiện hoặc ngữ cảnh phủ định. Tìm được đúng bài nhưng thiếu
đoạn chứng minh đầy đủ vẫn có thể dẫn đến NEI.

Ca người dùng: “Nạn nhân tử vong trong vụ cháy trường Kim Liên là học sinh lớp 6”.
Bộ lọc yêu cầu đúng tên cơ sở, nên tin tử vong khác ở Củ Chi không đủ điều kiện.
Các cụm sự kiện như “vụ cháy” kích hoạt neo thời gian kể cả khi chưa chọn ngày.

Trong **Chi tiết kỹ thuật**:

- `web_attempts`: truy vấn, số kết quả, số đoạn hợp lệ từng lượt.
- `web_candidates`: URL được nhận hoặc bị loại và lý do.
- `web_search_status`, `web_search_error`: trạng thái provider/quota.
- `temporal_gate`: ngày neo, cửa sổ, các nguồn local/web bị loại.
- `model_verdict`: kết quả mô hình trước guard; `verdict_before_text_rules`: kết quả trước luật nguyên văn.
- `outcome_stage`: phân biệt không có đoạn, mô hình NEI, guard hạ kết luận và kết luận quyết đoán.

Không thấy URL trong `web_candidates` nghĩa là lượt tìm kiếm chưa trả URL đó,
không thể suy ra trang không tồn tại hoặc phát biểu sai. Kết quả NEI vẫn hợp lệ
khi chưa có bằng chứng đủ mạnh; bản sửa không ép mô hình trả SUPPORTED.

Khởi động lại Gradio sau khi cập nhật:

```powershell
.\.venv312\Scripts\python.exe app_gradio.py --no-browser
```

API/CLI vẫn hỗ trợ URL cố định để phân tích riêng bước đọc và verifier. Không
trộn phép đo này với chất lượng tự tìm nguồn.

Đo tự tìm nguồn bằng `scripts/evaluate_web_discovery.py`; script chỉ gửi claim,
đối chiếu expected_url sau khi nhận kết quả. Mẫu sáu câu là mẫu chẩn đoán nhỏ,
có thiên lệch về các báo được cấu hình RSS, không phải benchmark đại diện.
RSS và chỉ mục thay đổi theo thời gian: các lượt trước/sau chạy khác ngày không
chứng minh một mức cải thiện tổng quát. Cần tập giữ riêng có nhãn đoạn bằng chứng
và nhiều chủ đề trước khi công bố Recall@k hoặc chất lượng kết luận ngoài thực tế.

Kiểm thử hồi quy không cần API key/mạng:

```powershell
.\.venv312\Scripts\python.exe -m pytest tests/test_news_retrieval_regressions.py tests/test_query_enrichment.py tests/test_temporal_gate.py tests/test_web_retriever.py tests/test_topical_rerank.py tests/test_retrieval_review_regressions.py tests/test_retrieval_web_suite.py tests/test_system_builder.py tests/test_web_retrieval_config.py -q --basetemp=.pytest_tmp/news-regression-new-run
```
