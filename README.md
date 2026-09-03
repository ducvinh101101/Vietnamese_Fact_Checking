# Vietnamese Fact-Checking — MVP hiện tại và roadmap 6 tuần

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

Sau khi lưu ba split ViFactCheck vào `data/raw/vifactcheck/` (dạng Hugging Face Arrow hoặc Parquet), tạo corpus cục bộ bằng:

```powershell
python scripts/build_vifactcheck_evidence.py
```

Tệp `data/evidence/vifactcheck_passages.jsonl` và dữ liệu đầu vào đều bị `.gitignore`; script chỉ đọc `Context`, `Author` và `Url`, khử trùng theo URL rồi chia bài báo thành các passage tối đa 700 ký tự.

Kế hoạch triển khai hiện hành nằm trong [workbook phân công Vinh–Quang](KE_HOACH_TRIEN_KHAI_2_NGUOI.xlsx), kèm [quy trình nghiên cứu](docs/QUY_TRINH_NGHIEN_CUU.md) và [backlog](docs/BACKLOG.md).

## Web retrieval (kế hoạch)

Hệ thống hiện chỉ dùng kho evidence cục bộ. Web retrieval uy tín đang ở trạng thái **chưa triển khai**; xem [kế hoạch web retrieval](docs/WEB_RETRIEVAL_PLAN.md) để biết phạm vi, allowlist, metadata nguồn và tiêu chí đánh giá.

## Kế hoạch phạm vi đầy đủ

Để bao phủ cả phân tích nội dung, claim decomposition, retrieval/RAG và tổng hợp cấp bài, xem [kế hoạch 6 tuần](docs/KE_HOACH_DAY_DU_DE_TAI.md).

## Theo dõi phạm vi đề tài

[Ma trận yêu cầu đề tài](docs/MA_TRAN_YEU_CAU_DE_TAI.md) liên kết từng yêu cầu với task và thí nghiệm. Các hạng mục ghi `Planned` chưa được xem là chức năng đã hoàn thành.
