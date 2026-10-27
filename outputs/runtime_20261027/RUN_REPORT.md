# Kết quả kiểm tra và chạy thử — 27/10/2026

Ứng dụng Gradio đang chạy local tại **http://127.0.0.1:7860**, dùng PhoBERT thật.
Không bật link chia sẻ công khai. Môi trường chạy: `.venv/py312` (Python 3.12.10).
Danh sách phiên bản thư viện của lần chạy nằm trong `requirements_runtime.txt`.

| Hạng mục | Kết quả |
| --- | --- |
| Kiểm tra phát hành | Các mục bắt buộc đạt sau khi khôi phục LF của corpus v2 và source policy |
| Pytest cuối, sau bản sửa runtime | **327 passed, 2 skipped**, 11 cảnh báo, 224,33 giây |
| Demo CLI với PhoBERT thật | **5/5** đúng kỳ vọng; đây là ví dụ chọn sẵn, không phải benchmark |
| Demo Gradio | Câu nguồn 6 ngày → SUPPORTED; đổi thành 10 ngày → REFUTED, có trích dẫn |
| Chuyển chế độ trong cùng app | Local → hybrid → local chạy được, không lỗi khởi tạo lại JVM |
| Gold 84 ca, PhoBERT verifier | **28/84**, accuracy **33,33%**, macro-F1 **22,50%** |
| Lỗi chạy / cặp bị cắt token trên 84 ca | **0 / 0** |
| Đối chiếu nhãn trước/sau bản sửa runtime | **0/84** nhãn thay đổi |
| Gemini | Đã kiểm tra request/parser bằng mock và dry-run; chưa gọi Gemini thật |
| Bộ gold và giao thức | Hash được kiểm tra; vẫn khớp manifest v1 |

Hai test bỏ qua cần `FC_TEST_CLAIMS` và `FC_HELDOUT` trỏ tới dữ liệu bổ sung;
chúng không được tính là đạt. Cảnh báo hiện tại chủ yếu là thay đổi API dự kiến
của Gradio 6; phiên bản đang dùng là Gradio 5.50.0. Pytest được chạy với
`FC_REQUIRE_PHOBERT=1`, `FC_FALLBACK_RULE_BASED=0`, `-p no:faulthandler`.
Các test dựng giao diện được chạy ngoài sandbox vì sandbox chặn kết nối local.
Chi tiết từng test: `pytest_final.xml`.

## Bản sửa runtime

`py_vncorenlp` thay đổi thư mục làm việc khi khởi tạo và thiết lập JVM toàn cục.
Việc dựng verifier mới có thể gọi lại thiết lập JVM đang chạy. Đã thêm cơ chế
tái sử dụng segmenter theo thư mục, khóa khởi tạo/sử dụng và khôi phục thư mục
làm việc cả khi khởi tạo lỗi. Có 5 test riêng cho vòng đời này.

Đã xác nhận bằng thao tác thực tế trên giao diện: kiểm chứng liên tiếp và đổi
chế độ bằng chứng. Bộ demo sau bản sửa nằm tại `outputs/demo_20261027_fixed/`
tính từ gốc dự án. Ảnh giao diện: `demo_refuted.png`.

## Cách đọc điểm gold

File kết quả hiện tại là
`outputs/comparison_20261027/phobert_verifier_fixed.jsonl` tính từ gốc dự án.
Bản chấm: `outputs/comparison_20261027/phobert_verifier_fixed_report.json`.

Lần chạy này dùng verifier PhoBERT với evidence view và chính sách tổng hợp
theo config, **không bật thêm luật minimal-pair/guard**. Từng đoạn được chấm
riêng rồi tổng hợp. Nó không phải phép đo end-to-end của app và không tương
đương số 72,3% trên ViFactCheck. Gold là dữ liệu giả lập, khác miền dữ liệu của
báo cáo cũ và chưa được người gán nhãn thứ hai rà soát độc lập. Không sửa model,
prompt hay gold dựa vào kết quả này.

## Cắm Gemini

Điền `GEMINI_API_KEY` và `GEMINI_MODEL` trong `.env` ở gốc repo. Mã REST nằm tại
`src/gemini_gold.py`, runner tại `scripts/run_model_gold.py`. Key này hiện dành
cho runner so sánh; chưa có lựa chọn Gemini trong nút kiểm chứng của giao diện.
Xem `docs/HUONG_DAN_GEMINI_COMPARISON.md` từ gốc repo để lấy đầy đủ lệnh chạy.
Không có API key trong báo cáo, metadata hay file dự đoán.
