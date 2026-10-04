# Giới thiệu dự án Vietnamese Fact-Checking

## Dự án này làm gì?

**Vietnamese Fact-Checking** là một dự án xây dựng hệ thống hỗ trợ kiểm chứng các phát biểu bằng tiếng Việt. Người dùng nhập một câu cần kiểm tra, chẳng hạn một thông tin đang lan truyền trên mạng; hệ thống sẽ tìm các đoạn tư liệu liên quan trong kho bằng chứng, đối chiếu phát biểu với các đoạn đó và trả về kết luận kèm nguồn trích dẫn.

Mục tiêu của dự án không phải là tự động khẳng định một thông tin là “đúng” hoặc “sai” tuyệt đối. Thay vào đó, hệ thống minh bạch hóa quá trình kiểm chứng: kết luận nào cũng cần dựa trên bằng chứng có thể mở và đọc lại.

## Hệ thống hoạt động như thế nào?

Luồng xử lý chính có thể hình dung đơn giản như sau:

```text
Phát biểu tiếng Việt
        ↓
Chuẩn hóa câu chữ và truy xuất các đoạn tư liệu liên quan
        ↓
Đánh giá quan hệ giữa phát biểu và từng đoạn bằng chứng
        ↓
Tổng hợp kết quả → nhãn kết luận + các đoạn được trích dẫn
```

Hệ thống trả về một trong ba nhãn:

- **SUPPORTED**: bằng chứng tìm được ủng hộ phát biểu.
- **REFUTED**: bằng chứng tìm được mâu thuẫn hoặc bác bỏ phát biểu.
- **NOT_ENOUGH_INFO**: chưa tìm được đủ bằng chứng đáng tin cậy để kết luận.

Kết quả cũng hiển thị điểm mô hình và các đường dẫn đến nguồn. Điểm mô hình chỉ thể hiện mức tin cậy của mô hình trong tác vụ này, không phải xác suất thông tin đúng trong thực tế.

## Các thành phần chính

- **Kho bằng chứng cục bộ:** Các bài viết được chia thành những passage ngắn, kèm URL, nguồn, loại nguồn và một số metadata thời gian.
- **Truy xuất thông tin:** Hệ thống dùng BM25 để tìm những passage liên quan nhất với phát biểu; các hướng thử nghiệm còn có lọc nguồn/thời gian và reranking để nâng chất lượng ứng viên.
- **Bộ kiểm chứng ngữ nghĩa:** PhoBERT được fine-tune để phân loại quan hệ giữa phát biểu và bằng chứng, thay vì chỉ dựa vào độ giống nhau của từ ngữ.
- **Chính sách ra quyết định và trích dẫn:** Chỉ những passage đã được truy xuất mới được phép dùng làm bằng chứng cho kết luận; nhờ vậy người dùng có thể kiểm tra lại đường đi từ phát biểu đến verdict.
- **Giao diện Streamlit:** Cung cấp màn hình nhập phát biểu, xem kết luận, các citation được dùng và danh sách các passage mà hệ thống đã tìm thấy.

## Dữ liệu và đánh giá

Dự án sử dụng dữ liệu ViFactCheck để tái lập và đánh giá. Việc đánh giá được tách thành hai phần: năng lực của mô hình khi đã có bằng chứng đúng (*oracle evidence*) và năng lực toàn hệ thống khi phải tự tìm bằng chứng (*end-to-end*). Sự tách biệt này giúp tránh nhầm lẫn giữa “mô hình đọc hiểu tốt” và “hệ thống kiểm chứng hoạt động tốt ngoài thực tế”.

Trên tập test ViFactCheck, cấu hình rerank cục bộ đã đạt Macro-F1 69,92% trong đánh giá end-to-end; đây là kết quả nghiên cứu trên dữ liệu nội bộ đã được sử dụng trong quá trình phát triển, không phải cam kết độ chính xác cho tin tức thực tế.

## Phạm vi và giới hạn

Phiên bản hiện tại là một MVP phục vụ nghiên cứu và trình diễn. Kho bằng chứng chủ yếu là dữ liệu cục bộ, nên hệ thống có thể không có thông tin mới nhất hoặc không tìm được nguồn phù hợp cho mọi phát biểu. Web retrieval, hợp nhất nguồn web với kho cục bộ, kiểm chứng theo thời gian và đánh giá độc lập trên dữ liệu thực tế vẫn là các hạng mục đang được tiếp tục hoàn thiện.

Vì vậy, kết quả từ hệ thống nên được xem là **hỗ trợ tham khảo**. Khi phát biểu liên quan đến sức khỏe, pháp luật, tài chính, an toàn hoặc các vấn đề quan trọng, người dùng cần mở nguồn trích dẫn và đối chiếu với nguồn chính thức trước khi đưa ra quyết định.

## Cách chạy bản demo

Sau khi chuẩn bị môi trường Python, các model cần thiết và Java/VnCoreNLP theo hướng dẫn tái lập, chạy:

```powershell
streamlit run app.py
```

Mở giao diện trên trình duyệt, nhập một phát biểu tiếng Việt và chọn **Kiểm chứng** để xem kết quả. Hướng dẫn cài đặt chi tiết nằm trong [README](../README.md) và [tài liệu tái lập](REPRODUCIBILITY_BASELINE.md).
