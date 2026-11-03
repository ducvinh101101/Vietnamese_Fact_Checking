# Truy xuất tin mới: thay đổi và cách kiểm tra

Chế độ Local + web dùng chung một cửa sổ ngày cho tìm kiếm và lọc bằng chứng:

- `Ngày 3/11` dùng năm của ngày tham chiếu. Ngày đầy đủ dùng đúng năm trong câu.
- Chọn ngày tham chiếu sẽ bật lọc cho cả câu chưa có dấu hiệu thời gian được nhận diện.
- Câu chỉ rõ năm/tháng lịch sử không bị ép sang hiện tại.
- Ngày đăng gần ngày sự kiện là điều kiện chọn nguồn, không tự chứng minh sự kiện đúng ngày đó.
- Bài không rõ ngày hoặc ngoài cửa sổ bị loại. Ngày đăng từ trang được ưu tiên hơn ngày từ chỉ mục.

Tavily thử tối đa ba lượt trong quota sẵn có: phát biểu đầy đủ, câu dẫn ngắn,
rồi câu dẫn ở chỉ mục general. Nhánh cuối vẫn nhận các nguồn báo chí trong
allowlist. Các lượt được hợp nhất; kết quả khớp yếu không chặn lượt tiếp theo.
Toàn bộ nội dung trang được xét trước khi chọn tối đa ba đoạn; đoạn liền kề có
thể được giữ chung để cung cấp ngữ cảnh, trong giới hạn độ dài cũ.

Ô **URL nguồn** nhận tối đa ba URL, mỗi dòng một URL. Dùng ô này khi bài mới
đăng chưa xuất hiện trong chỉ mục tìm kiếm. Không cần Tavily API key cho URL
trực tiếp; vẫn áp dụng allowlist, HTTPS, DNS, redirect, robots.txt và lọc ngày.
Công lý (`congly.vn`, `www.congly.vn`) đã được thêm vào allowlist.

Trong **Chi tiết kỹ thuật**:

- `web_attempts`: truy vấn, số kết quả, số đoạn hợp lệ từng lượt.
- `web_candidates`: URL được nhận hoặc bị loại và lý do.
- `web_search_status`, `web_search_error`: trạng thái provider/quota.
- `temporal_gate`: ngày neo, cửa sổ, các nguồn local/web bị loại.

Không thấy URL trong `web_candidates` nghĩa là lượt tìm kiếm chưa trả URL đó,
không thể suy ra trang không tồn tại hoặc phát biểu sai. Kết quả NEI vẫn hợp lệ
khi chưa có bằng chứng đủ mạnh; bản sửa không ép mô hình trả SUPPORTED.

Khởi động lại Gradio sau khi cập nhật:

```powershell
.\.venv312\Scripts\python.exe app_gradio.py --no-browser
```

CLI cũng nhận `--source-url` (lặp tối đa ba lần). Ví dụ:

```powershell
.\.venv312\Scripts\python.exe scripts/run_web_fact_check.py --claim "Ngày 3/11, Quốc hội thảo luận 4 dự án luật" --as-of 2026-11-03 --source-url https://congly.vn/hom-nay-quoc-hoi-thao-luan-4-du-an-luat-quan-trong-545920.html
```

Kiểm thử hồi quy không cần API key/mạng:

```powershell
.\.venv312\Scripts\python.exe -m pytest tests/test_news_retrieval_regressions.py tests/test_query_enrichment.py tests/test_temporal_gate.py tests/test_web_retriever.py tests/test_topical_rerank.py tests/test_retrieval_review_regressions.py tests/test_retrieval_web_suite.py tests/test_system_builder.py tests/test_web_retrieval_config.py -q --basetemp=.pytest_tmp/news-regression-new-run
```
