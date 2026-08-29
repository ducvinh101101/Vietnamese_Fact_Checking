# Vietnamese Fact-Checking MVP

Nền tảng cộng tác cho dự án đánh giá độ tin cậy và kiểm chứng thông tin tiếng Việt. Phiên bản này ưu tiên một luồng chạy được ngay:

`claim → truy xuất evidence → kết luận có trích dẫn`

Nhánh phân loại nội dung được giữ tách biệt để phát triển sau; nó không quyết định nhãn đúng/sai cuối cùng.

## Bắt đầu nhanh

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Ứng dụng khởi chạy bằng dữ liệu mẫu tại `data/evidence/sample_evidence.jsonl`.

## Cấu trúc

- `src/`: pipeline và các thành phần NLP.
- `data/`: dữ liệu thô, đã xử lý, kho bằng chứng.
- `configs/config.yaml`: cấu hình tập trung.
- `tests/`: kiểm thử tự động cơ bản.
- `docs/`: phân công hai người, quy trình nghiên cứu và backlog.
- `outputs/`: metrics, hình và dự đoán; không đưa artefact lớn lên Git.

## Luồng làm việc hai người

Đọc [phân công](docs/PHAN_CONG_2_NGUOI.md) và [quy trình nghiên cứu](docs/QUY_TRINH_NGHIEN_CUU.md) trước khi bắt đầu. Mỗi thay đổi nên có một nhánh Git riêng và một mục trong `docs/BACKLOG.md`.

## Dữ liệu ViFactCheck

Không commit dữ liệu lớn. Sau khi tải, đặt dữ liệu gốc vào `data/raw/`, tạo các passage vào `data/evidence/`, và giữ các trường tối thiểu:

```json
{"document_id":"...","passage_id":"...","content":"...","source":"...","url":"..."}
```

Xem [kế hoạch triển khai](KE_HOACH_TRIEN_KHAI.md) để biết phạm vi, thí nghiệm và tiêu chí đánh giá.
