# Chạy dự án và so sánh PhoBERT với Gemini

## API key cắm ở đâu?

Đặt trong file **`.env` ngay thư mục gốc `D:\Vietnamese_Fact_Checking`**:

```dotenv
GEMINI_API_KEY=thay_bang_key_cua_ban
GEMINI_MODEL=gemini-3.8-flash
```

Đây là ví dụ model ID từ tài liệu Google được kiểm tra ngày 27/10/2026;
dùng ID mà tài khoản của bạn có quyền truy cập tại lúc chạy. Key lấy tại
[Google AI Studio](https://aistudio.google.com/apikey). Không đặt key vào Python,
`config.yaml`, `inputs.jsonl`, `gold.jsonl` hay `.env.example`.
`.env` đã được `.gitignore` loại trừ. Biến môi trường đã đặt được ưu tiên hơn `.env`.

Nếu chưa có `.env`, tạo một lần bằng:

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
```

Không chạy lệnh copy này khi `.env` đã có key khác; chỉ bổ sung hai dòng Gemini.
Tavily là dịch vụ tìm bằng chứng web, Gemini là model xác minh: hai key dùng cho
hai chức năng khác nhau. So sánh trên 84 ca cố định không cần key Tavily.

## Môi trường chạy đã chuẩn bị trên máy này

Môi trường dành riêng cho lần kiểm tra đặt tại `.venv\py312`, sử dụng Python 3.12.
Nó tách khỏi môi trường `.venv` Python 3.14 có sẵn. Java 17 portable đặt tại
`tools/java17`; code PhoBERT tự tìm runtime này. Không đổi checkpoint/model đã huấn luyện.

Lần chạy này cũng sửa vòng đời VnCoreNLP: tái sử dụng bộ tách từ giữa các lần dựng
verifier và khôi phục thư mục làm việc sau khi thư viện khởi tạo. Các ca kiểm thử
riêng kiểm tra dùng lại JVM, khởi tạo đồng thời và khôi phục thư mục cả khi có lỗi.

Các lệnh bên dưới chạy trong thư mục gốc dự án:

```powershell
# Kiểm tra thư viện, checkpoint, Java và corpus; chạy một claim thật
.\.venv\py312\Scripts\python.exe scripts/check_release.py --smoke

# Giao diện local
.\.venv\py312\Scripts\python.exe app_gradio.py --port 7860

# Test tự động; dùng thư mục tạm mới để không xóa file tạm cũ
.\.venv\py312\Scripts\python.exe -m pytest -q -p no:faulthandler --basetemp=.cache/pytest_manual
```

Nếu cổng 7860 đã được ứng dụng demo sử dụng, mở `http://127.0.0.1:7860` hoặc
khởi chạy bản khác bằng `--port 7861`. Không cần `--share` để xem trên máy mình.

## Chạy so sánh

Hai nhánh đều đọc đúng `tests/golden/model_comparison_v1/inputs.jsonl`.
Không truy xuất lại từ BM25 hay web, không đọc đáp án khi suy luận.
`scripts/evaluate_model_gold.py` chỉ đọc gold ở bước chấm sau cùng.

```powershell
# 1. Xác nhận bộ dữ liệu và giao thức còn nguyên
.\.venv\py312\Scripts\python.exe scripts/evaluate_model_gold.py validate

# 2. PhoBERT với verifier/checkpoint và cấu hình đã khóa; không bật luật cặp tối thiểu
.\.venv\py312\Scripts\python.exe scripts/run_model_gold.py --backend phobert --output outputs/comparison/phobert.jsonl

# 3. Gemini: đọc key/model ID từ .env, gọi API cho đúng 84 ca
.\.venv\py312\Scripts\python.exe scripts/run_model_gold.py --backend gemini --output outputs/comparison/gemini.jsonl

# 4. So sánh hai file cùng 84 ID
.\.venv\py312\Scripts\python.exe scripts/evaluate_model_gold.py score outputs/comparison/phobert.jsonl outputs/comparison/gemini.jsonl --output outputs/comparison/report.json
```

Runner từ chối ghi đè kết quả đã có. Đặt tên mới cho lần chạy mới để giữ lịch sử.
Kết quả chấm có accuracy, macro-F1, precision/recall từng nhãn, ma trận nhầm lẫn,
điểm từng nhóm và các ca chỉ một trong hai model trả đúng. Lỗi API được ghi
`label: null` + `error` và tính sai; không chuyển lỗi thành NOT_ENOUGH_INFO.

Mỗi lần chạy có ba file cạnh nhau:

- `*.jsonl`: dự đoán từng ca, trích dẫn và thời gian xử lý.
- `*.raw.jsonl`: phản hồi JSON từ Gemini, gồm modelVersion/usageMetadata nếu API
  trả về; nhánh PhoBERT để response null vì không có phản hồi API.
- `*.run.json`: cấu hình, mốc UTC, hash đầu vào/prompt/mã chạy, số lỗi và checksum
  checkpoint cho PhoBERT. Không lưu API key trong metadata.

Chạy thử cơ chế nạp dữ liệu mà **không gọi API/model**:

```powershell
.\.venv\py312\Scripts\python.exe scripts/run_model_gold.py --backend gemini --dry-run --output outputs/comparison/gemini_preview.jsonl
```

Muốn thử 3 ca trước khi chạy đủ, thêm `--limit 3` và dùng tên file riêng. Kết quả
chạy ít ca không thể đưa vào lệnh chấm chuẩn 84 ca. Mặc định Gemini gọi tuần tự,
cách nhau 1 giây, không tự retry; cần chốt quy tắc retry trước khi so sánh chính thức.
`--max-output-tokens`, `--timeout`, `--pause-seconds`, `--temperature` là tham số
cấu hình, không chỉnh dựa vào đáp án của test. Temperature không đặt thì dùng
mặc định của model, được ghi rõ trong metadata.

## So sánh model hay so sánh cả hệ thống?

Mặc định `--backend phobert` dùng verifier hiện tại với evidence view và chính
sách tổng hợp theo config, **không áp dụng thêm `MinimalPairVerifier`/guard**.
Đây vẫn là PhoBERT kèm chính sách tổng hợp đã có, không phải logits thô. Các
đoạn được chấm riêng rồi tổng hợp theo thứ tự đầu vào; không tự gộp nhiều đoạn
thành một văn bản mới. Gemini đọc đồng thời các đoạn trong một yêu cầu.

Để đo cấu hình xác minh cuối của project, chạy riêng:

```powershell
.\.venv\py312\Scripts\python.exe scripts/run_model_gold.py --backend phobert --project-rules --output outputs/comparison/phobert_project.jsonl
```

Ghi đúng tên này trong báo cáo vì nó bao gồm luật hậu xử lý. Runner buộc chạy
PhoBERT thật, không lặng lẽ fallback sang rule-based. Không chọn giữa hai cấu
hình dựa vào điểm trên 84 ca; công bố cả hai nếu mục tiêu nghiên cứu cần cả hai.

PhoBERT không nhận instruction prompt như Gemini và hiện không sử dụng trường
`as_of` riêng; ngày nằm trong claim vẫn được giữ nguyên. Nó có giới hạn token
theo config; từng ca ghi độ dài cặp claim–evidence và số cặp có thể bị cắt.
Gemini nhận prompt cố định trong `PROTOCOL.md`, không bật Google Search hay tool.
Vì khác kiến trúc/giao diện, không gọi đây là hai model dùng chung prompt.

84 ca là tư liệu giả lập để đo suy luận trên bằng chứng cố định, chưa có người
gán nhãn thứ hai kiểm tra độc lập. Điểm trên bộ này không đo chất lượng tìm
kiếm web hay năng lực end-to-end ngoài thực tế. Giao thức và gold được giữ nguyên
trong lần bổ sung runner này; không sửa đáp án sau khi xem lỗi model.

## Nếu sau này muốn Gemini xuất hiện trong app

Ranh giới ổn định nằm tại `src/contracts.py`: phương thức
`Verifier.verify(claim, evidence_items) -> VerificationResult`.
`src/system_builder.py` dựng verifier, và `build_system(..., verifier=...)` cho
phép truyền một verifier khác vào sau retrieval. Adapter Gemini cho app cần
thực hiện interface này, rồi giao diện chọn model khi dựng hệ thống.

Hiện **key Gemini chỉ được runner so sánh đọc**, chưa có nút chọn Gemini trong
Gradio/Streamlit. Việc điền key không tự đổi model của ứng dụng. Mã gọi REST nằm
ở `src/gemini_gold.py`; orchestration, ghi dự đoán và metadata nằm ở
`scripts/run_model_gold.py`. Không cần sửa `PhoBERTFactChecker` để chạy so sánh.

Tham chiếu chính thức đã kiểm tra ngày 27/10/2026:
[API key và bắt đầu](https://ai.google.dev/gemini-api/docs/get-started),
[generateContent REST](https://ai.google.dev/api/generate-content),
[danh sách model](https://ai.google.dev/gemini-api/docs/models).
Client dùng HTTPS, key trong header `x-goog-api-key` và JSON Schema cho ba nhãn.
