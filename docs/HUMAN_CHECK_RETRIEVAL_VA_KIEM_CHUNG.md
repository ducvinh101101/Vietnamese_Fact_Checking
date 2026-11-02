# Hướng dẫn chạy human check từ đầu đến cuối

Làm lần lượt **Bước 1 → Bước 12**. Sau khi hoàn tất, bạn sẽ có một file chấm kết quả, log chạy thử và danh sách lỗi đủ thông tin để tái hiện.

Quy trình này kiểm tra hai yêu cầu: **top 1 phải liên quan** và **claim cần dữ liệu mới phải lấy được nguồn đúng thời điểm**. Phần verdict được chấm riêng để biết lỗi nằm ở retrieval hay verifier.

Bạn sẽ dùng **hai cửa sổ PowerShell**: cửa sổ **A** để giữ app chạy; cửa sổ **B** để chuẩn bị và lưu log. Các lệnh đều chạy từ `D:\Vietnamese_Fact_Checking`.

## Bước 1 — Mở dự án và kiểm tra Python

Mở PowerShell, gọi đây là **cửa sổ B**, chạy:

```powershell
Set-Location D:\Vietnamese_Fact_Checking
Test-Path .\.venv312\Scripts\python.exe
.\.venv312\Scripts\python.exe --version
```

**Phải thấy:** `True` và phiên bản Python. Máy hiện tại đã có `.venv312`, thường bạn đi thẳng sang Bước 2.

Chỉ khi kết quả là `False`, tạo môi trường và cài thư viện:

```powershell
python -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu máy chưa có Python, cần cài Python 3.12 trước. Nếu thiếu checkpoint/corpus/Java, việc cài requirements chưa đủ; kiểm tra ở Bước 3 và xem [hướng dẫn tái lập](REPRODUCIBILITY_BASELINE.md).

## Bước 2 — Tạo nơi lưu kết quả cho lần kiểm tra này

Vẫn trong **B**, chạy nguyên block:

```powershell
$humanCheckRun = Get-Date -Format "yyyyMMdd_HHmmss"
$humanCheckDay = Get-Date -Format "yyyy-MM-dd"
$humanCheckDir = Join-Path (Get-Location) "outputs\web_retrieval\human_check\$humanCheckRun"
New-Item -ItemType Directory -Force -Path $humanCheckDir | Out-Null
$humanCheckReport = Join-Path $humanCheckDir "KET_QUA_HUMAN_CHECK.md"
Copy-Item -LiteralPath docs\HUMAN_CHECK_RESULT_TEMPLATE.md -Destination $humanCheckReport
git rev-parse HEAD | Tee-Object -FilePath (Join-Path $humanCheckDir "git_commit.txt")
Write-Output "Ngày tham chiếu: $humanCheckDay"
Write-Output "File kết quả: $humanCheckReport"
notepad $humanCheckReport
```

**Phải thấy:** Notepad mở một file mẫu đã có các case và ô cần điền. Điền tên người chấm, commit vừa in ra, ngày giờ và ngày tham chiếu, rồi `Ctrl+S`.

Kiểm tra ngày trên Windows là ngày hiện tại tại Việt Nam. Nếu muốn tái lập một ngày cụ thể, đặt lại biến ngay lúc này, ví dụ `$humanCheckDay = "2026-11-02"`, và dùng đúng ngày đó ở cả app lẫn CLI. Ghi đây là kiểm tra hồi cứu vì dữ liệu web hiện tại có thể đã thay đổi.

**Giữ cửa sổ B mở:** các bước sau dùng lại các biến vừa tạo. Mỗi lần mở B mới, cần chạy lại Bước 2 để bắt đầu một đợt mới.

## Bước 3 — Kiểm tra key và môi trường chạy

Mở `.env` bằng trình soạn thảo trên máy và xác nhận có dòng `TAVILY_API_KEY=...` với key thật. Nếu chưa có file, tạo `.env` ở thư mục gốc theo `.env.example`. Không đưa key vào phiếu hoặc ảnh chụp.

Trong **B**, chạy:

```powershell
.\.venv312\Scripts\python.exe scripts\check_release.py `
  2>&1 | Tee-Object -FilePath (Join-Path $humanCheckDir "00_environment.log")
```

Đọc log và điền phần môi trường trong file kết quả:

| Quan sát | Việc cần làm |
|---|---|
| `TAVILY_API_KEY` có | Tiếp tục kiểm tra web |
| Key chưa đặt | Đặt key vào `.env`; chạy lại bước này |
| Thiếu corpus/checkpoint/Java hoặc thư viện bắt buộc | Chuẩn bị thành phần thiếu theo tài liệu tái lập trước khi chấm phần phụ thuộc nó |
| Torch bị Windows chặn, app có thể dùng rule-based | Vẫn chấm retrieval; ghi phần chất lượng PhoBERT là `BLOCKED` |
| Hash chỉ khác CRLF | Chạy lệnh chuẩn hóa có kiểm tra hash bên dưới; sau đó đọc lại kết quả |
| Hash khác cả sau chuẩn hóa LF | Ghi lỗi môi trường và đối chiếu nguồn dữ liệu; không tự xoá/reset hoặc đổi manifest |

Log kiểm tra môi trường không phải kết quả human check. Bước này chỉ xác nhận điều kiện chạy.

Nếu log báo `chỉ khác CRLF`, vẫn trong B chạy:

```powershell
.\.venv312\Scripts\python.exe scripts\check_release.py --fix-line-endings `
  2>&1 | Tee-Object -FilePath (Join-Path $humanCheckDir "00_environment_fixed.log")
```

Lệnh chỉ chuyển CRLF về LF cho corpus v2 và source policy khi byte sau chuẩn hóa khớp đúng hash trong manifest. Nếu nội dung thật sự khác, lệnh giữ nguyên file và báo lỗi. Không cần đổi `core.autocrlf`, xoá corpus hoặc checkout cả thư mục. Hai mục hash phải chuyển sang dấu ✓ trước khi tiếp tục; các mục môi trường khác vẫn cần được xử lý riêng.

## Bước 4 — Mở giao diện

Mở thêm PowerShell, gọi đây là **cửa sổ A**, chạy:

```powershell
Set-Location D:\Vietnamese_Fact_Checking
.\.venv312\Scripts\python.exe app_gradio.py
```

Chờ terminal in địa chỉ local, rồi mở `http://127.0.0.1:7860` nếu trình duyệt không tự mở.

**Phải thấy:** ô `Phát biểu cần kiểm chứng`, lựa chọn `Nguồn bằng chứng`, nút `Kiểm chứng` và các tab kết quả. Giữ cửa sổ A chạy trong suốt buổi kiểm tra.

Nếu cổng 7860 đang dùng, trong A chạy `app_gradio.py --port 7861` bằng cùng Python và mở cổng mới. Nếu Gradio không chạy được, ghi lỗi khởi động; có thể thử Streamlit bằng `.\.venv312\Scripts\python.exe -m streamlit run app.py`, nhưng phải ghi bạn đã dùng giao diện khác.

## Bước 5 — Chạy ca local đầu tiên và học cách chấm

Trên giao diện:

1. Chọn `Kho local (đã đánh giá)` ở `Nguồn bằng chứng`.
2. Dán nguyên câu sau vào ô nhập:

   ```text
   Tổng thống Brazil Lula hoãn chuyến thăm 6 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn.
   ```

3. Bấm `Kiểm chứng`, chờ kết quả.
4. Đọc cảnh báo runtime. Nếu chạy rule-based, ghi vào phiếu trước khi chấm.
5. Chọn tab **Tất cả bằng chứng truy xuất**. Passage đầu danh sách là **top 1**.
6. Đọc toàn bộ passage top 1. Tìm các chi tiết: Lula, hoãn chuyến thăm, 6 ngày, Trung Quốc, viêm phổi.
7. Bấm `Mở nguồn` trên passage đó; tìm câu tương ứng trong bài và đọc đoạn trước/sau.
8. Quay lại tab **Trích dẫn dùng để kết luận**, xem verifier đã cite đoạn nào.
9. Điền **HC-01** trong file kết quả ở Notepad. Lưu ảnh nếu cần bằng `Win+Shift+S`, đặt vào thư mục đợt chạy hoặc ghi vị trí ảnh vào phiếu.

Kỳ vọng từ ví dụ repo: `SUPPORTED`, với citation xác nhận câu nguồn. Nếu sai, ghi kết quả thực tế; không sửa kỳ vọng cho khớp app. Nếu URL nguồn không mở được, vẫn có thể so passage với corpus, nhưng đánh dấu việc xác minh website gốc là chưa hoàn tất.

Quy ước điểm sẽ dùng cho toàn bộ buổi kiểm tra:

| Điểm | Cách chấm |
|---|---|
| 2 | Passage trực tiếp xác nhận hoặc bác bỏ claim, đúng đối tượng và điều kiện |
| 1 | Cùng chủ đề nhưng chưa đủ chi tiết quyết định |
| 0 | Lạc chủ đề, sai đối tượng hoặc sai phạm vi |
| U | Chưa có đủ nội dung/điều kiện để chấm |

**Đừng lấy passage được trích dẫn đầu tiên làm top 1.** Thứ hạng phải đọc từ tab retrieval; verifier có thể cite passage khác.

## Bước 6 — Chạy tiếp ba ca local

Giữ `Kho local`, thay lần lượt câu nhập và bấm `Kiểm chứng` cho từng ca:

| ID | Câu nhập | Điều phải kiểm tra |
|---|---|---|
| HC-02 | Tổng thống Brazil Lula hoãn chuyến thăm 10 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn. | Kỳ vọng REFUTED theo ví dụ repo; passage nói 6 ngày vẫn là bằng chứng liên quan điểm 2 |
| HC-03 | Tổng thống Brazil Lula không hoãn chuyến thăm 6 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn. | Kỳ vọng REFUTED; hệ thống không được bỏ qua chữ “không” |
| HC-04 | Đông Nam Á được xem là vùng trũng của bóng đá thế giới, đặc biệt là sau sự thành công của đội tuyển U23 Việt Nam. | Kỳ vọng NEI theo ví dụ repo; cùng chủ đề chưa đủ xác nhận nhận định |

Với **từng ca**, thực hiện lại Bước 5 mục 5–9: chấm top 1, mở nguồn, xem citation, ghi phiếu và lưu. Đừng chạy cả ba rồi chỉ ghi một kết quả chung.

## Bước 7 — Chốt nguồn đối chứng cho sáu ca web

**Chưa nhập app ngay.** Mở một tab trình duyệt riêng, tìm nguồn cho từng câu dưới đây theo ngày `$humanCheckDay`, rồi ghi URL/ngày/câu nguồn vào phiếu **trước khi xem kết quả app**:

| ID | Câu thử | Nơi bắt đầu tìm nguồn đối chứng |
|---|---|---|
| HC-05 | Giá xăng RON 95 tăng chiều nay. | Bộ Công Thương, Petrolimex |
| HC-06 | Giá vàng SJC hôm nay giảm. | SJC hoặc báo có dữ liệu và mốc so sánh rõ |
| HC-07 | Tỷ giá USD tại Vietcombank hôm nay tăng. | Vietcombank; phân biệt mua tiền mặt, chuyển khoản và bán |
| HC-08 | Hà Nội có mưa lớn hôm nay. | Bản tin NCHMF đúng ngày, đúng địa điểm |
| HC-09 | Lãi suất tiết kiệm tháng này giảm. | Thông báo ngân hàng và nguồn báo có ngày |
| HC-10 | Giá điện sinh hoạt tăng tháng này. | EVN, Bộ Công Thương; kiểm tra ngày có hiệu lực |

Bạn có thể gõ vào công cụ tìm kiếm các cụm như `site:petrolimex.com.vn giá xăng [ngày cần kiểm tra]` hoặc `site:nchmf.gov.vn Hà Nội [ngày cần kiểm tra]`. Thay phần trong ngoặc vuông bằng ngày thật; mở trang nguồn, không lấy riêng snippet tìm kiếm làm đáp án.

Mỗi ca cần ghi:

- Claim đúng/sai/chưa đủ thông tin theo nguồn nào.
- Ngày đăng/cập nhật và ngày sự kiện hoặc hiệu lực.
- Chi tiết nguồn xác nhận/bác bỏ; với “tăng/giảm” cần mốc so sánh.
- Hostname có trong `configs/web_retrieval.yaml` không. Có thể mở file bằng `notepad configs\web_retrieval.yaml` trong B.

Nếu không tìm được nguồn xác định, ghi `CHƯA CÓ ĐÁP ÁN NGƯỜI`; vẫn chạy ca để khám phá, nhưng không tính nó là ca có đáp án đã chốt. Những câu này không được mặc định là đúng ngày bạn chạy.

## Bước 8 — Chạy sáu ca web trên giao diện

1. Chọn `Local + web (Tavily)`.
2. Bật `Đặt ngày tham chiếu (chế độ web)`.
3. Điền đúng ngày `$humanCheckDay` đã ghi ở Bước 2.
4. Nhập HC-05, bấm `Kiểm chứng`.
5. Mở tab **Tất cả bằng chứng truy xuất**, đọc top 1 và các passage còn lại.
6. Mở nguồn của top 1 và nguồn được cite; đối chiếu với nguồn đã chuẩn bị ở Bước 7.
7. Điền phiếu HC-05, `Ctrl+S`.
8. Lặp lại mục 4–7 cho HC-06 đến HC-10.

Với mỗi ca web, trả lời lần lượt:

| Câu hỏi | Ghi vào phiếu |
|---|---|
| Top 1 có đúng đối tượng/chủ đề/phạm vi không? | Điểm 0/1/2/U và lý do |
| Passage thật sự nằm trong bài chính hay ở sidebar/tin liên quan? | Đúng / Sai / Chưa xác minh |
| Có bằng chứng gắn nhãn web không? | Số web / số local |
| Ngày trong app có khớp ngày nguồn không? | Ngày app và ngày nguồn |
| Bài có nói đúng thời điểm claim hỏi không? | Đạt / Không đạt / Chưa rõ |
| Verdict có được citation chứng minh không? | Đạt / Không đạt / Bị chặn bởi runtime |
| Nguồn đối chứng chốt trước có bị bỏ sót không? | Có / Không / Nguồn ngoài allowlist |

Lưu ý khi chấm:

- “Có ngày đăng” chưa đủ: bài hôm nay kể chuyện cũ vẫn có thể sai mốc sự kiện.
- Claim “hôm nay” mặc định được tìm trong cửa sổ 10 ngày; passage 5 ngày trước có thể qua gate nhưng chưa đủ chứng minh “hôm nay”.
- Claim “tháng này” phải kiểm tra mốc đầu tháng; không lấy bài tháng trước làm bằng chứng hiện tại.
- Giá vàng/tỷ giá chỉ có một snapshot chưa đủ chứng minh tăng/giảm; lãi suất một ngân hàng chưa đủ kết luận cho toàn thị trường.
- Nếu không có kết quả, ghi **EMPTY**; tiếp tục Bước 9 để xem vì sao.

Tránh chạy dồn nhiều ca cùng lúc: quota hiện giới hạn 10 request/phút, tối đa 3 bước tìm kiếm một claim. Khi gặp rate limit, ghi BLOCKED, chờ qua cửa sổ một phút rồi chạy lại có ghi nhận; giữ kết quả lần đầu.

## Bước 9 — Lấy log cho một ca web thất bại

Quay lại **B**, chọn một câu trong HC-05…HC-10 bị rỗng hoặc sai. Ví dụ dùng HC-05:

```powershell
$humanCheckClaim = "Giá xăng RON 95 tăng chiều nay"
.\.venv312\Scripts\python.exe scripts\run_web_fact_check.py `
  --claim $humanCheckClaim --as-of $humanCheckDay --top-k 5 `
  2>&1 | Tee-Object -FilePath (Join-Path $humanCheckDir "HC-11-default.log")
```

Nếu không có ca thất bại, vẫn chạy câu ví dụ trên để học cách đọc log. Ghi đây là **lần chạy CLI bổ sung**, không tự gộp nó với lần UI vì provider có thể trả tập ứng viên khác.

Mở log:

```powershell
notepad (Join-Path $humanCheckDir "HC-11-default.log")
```

Đọc từ trên xuống và điền HC-11 trong phiếu:

1. `[runtime]`: có bị fallback rule-based không?
2. `[web]`: có thiếu key/lỗi nhánh web không?
3. `dated_news`, `plain_news`, `primary_general`: bước nào chạy, số passage, có bước tìm lại không?
4. `[gate]`: cutoff là ngày nào, loại bao nhiêu bài cũ/không ngày/tương lai?
5. Danh sách `[1]`…: top 1 là gì, có `[ngày từ page]` hay `[ngày từ tavily]` không?
6. So với nguồn đối chứng: do không tìm ra bài, không tải được, không trích được passage, không đọc được ngày hay do rerank?

Các bước fallback được phép dừng sớm khi có bằng chứng hoặc khi thiếu key/quota/mạng. Không thấy đủ ba bước không tự động là lỗi. Nhưng nếu nguồn phù hợp có sẵn mà bị bỏ sót, vẫn phải ghi lỗi coverage/discovery.

**CLI chỉ in 160 ký tự đầu của passage.** Đọc đầy đủ qua UI trước khi chấm điểm nội dung; log chỉ dùng bổ sung chẩn đoán.

## Bước 10 — Chạy hai đối chứng để kiểm tra rerank và ngày

### 10a. Tắt topical rerank trên cùng claim

Vẫn trong B, dùng lại `$humanCheckClaim` từ Bước 9:

```powershell
.\.venv312\Scripts\python.exe scripts\run_web_fact_check.py `
  --claim $humanCheckClaim --as-of $humanCheckDay --top-k 5 --no-topical-rerank `
  2>&1 | Tee-Object -FilePath (Join-Path $humanCheckDir "HC-11-rerank-off.log")
```

Mở hai log default/rerank-off và ghi so sánh trong HC-11:

- Top 1 có đổi không? Điểm liên quan tăng hay giảm?
- Bài đúng có trong top 5 mà bị đẩy xuống không?
- Tập passage đầu vào quan sát được có thay đổi giữa hai lần không?

Nếu ứng viên thay đổi, ghi “không cô lập được tác động rerank”. Để loại biến động web, chạy lại cả hai lệnh với `--local-only` ở cả hai phía và lưu tên log mới. Lưu ý `--local-only` vẫn là chuỗi hybrid tắt web, khác chế độ `Kho local` trên UI; gate vẫn có thể loại hết corpus cũ.

### 10b. Buộc cửa sổ hôm nay là 0 ngày

```powershell
.\.venv312\Scripts\python.exe scripts\run_web_fact_check.py `
  --claim "Giá xăng RON 95 tăng chiều nay" --as-of $humanCheckDay `
  --top-k 5 --recency-today 0 `
  2>&1 | Tee-Object -FilePath (Join-Path $humanCheckDir "HC-12-strict-date.log")
```

Điền HC-12: bài nào bị loại so với mặc định? Có còn bài đúng ngày? Bài đúng ngày có nói đúng sự kiện chiều nay không? Không nới cửa sổ cho đến khi ra kết quả rồi chấm PASS. Cửa sổ 0 cũng có thể loại bài hôm qua thông báo hiệu lực hôm nay; ghi đây là đánh đổi của cấu hình thử.

Nếu CLI chưa chạy nổi do verifier nhưng cần kiểm tra riêng retrieval, dùng lệnh sau rồi ghi đây là ca chẩn đoán độc lập:

```powershell
.\.venv312\Scripts\python.exe scripts\run_golden_eval.py --live `
  --claim "Giá xăng RON 95 tăng chiều nay" `
  2>&1 | Tee-Object -FilePath (Join-Path $humanCheckDir "retrieval-only-live.log")
```

Runner này dùng ngày chạy và không có cờ `--as-of`. Exit code 0 chưa chứng minh chất lượng PASS: phải đọc cảnh báo và tự mở nguồn.

## Bước 11 — Chốt điểm và viết lỗi

Mở lại file chấm nếu đã đóng:

```powershell
notepad $humanCheckReport
```

1. Hoàn tất bảng tổng hợp HC-01…HC-12.
2. HC-01…HC-10 là các ca chính. HC-11/HC-12 là đối chứng/chẩn đoán: báo cáo riêng, không tính như claim độc lập để tăng cỡ mẫu.
3. Đếm top 1 điểm 2/1/0/U; đếm EMPTY và BLOCKED riêng.
4. Với HC-05…HC-10, đếm số ca có nguồn đúng thời điểm, số ca bỏ sót nguồn đã chốt trước trong allowlist và số ca chưa đủ đáp án người.
5. Sao chép block “Báo lỗi” trong file kết quả cho mỗi FAIL. Dán claim, URL, passage ID, ngày, kỳ vọng, kết quả thực tế và tên log.
6. Nếu có thể, thử lại ca lỗi một lần, ghi thêm kết quả mới; không xoá lần đầu.
7. Điền ba kết luận riêng: YC1, YC2 và verdict/citation.

Quy tắc chốt:

- Một ca top 1 điểm 0 đã xác minh → **YC1 chưa đạt trên tập thử**.
- Có nguồn phù hợp đã chốt trước trong allowlist nhưng hệ thống bỏ sót → ghi **YC2 còn lỗi tìm nguồn**, dù NEI là kết luận an toàn.
- Có ngày mới nhưng nội dung sai sự kiện/thời điểm → **YC2 FAIL**, không phải PASS.
- Tất cả ca đã chấm không có lỗi → chỉ kết luận “chưa phát hiện lỗi trong N ca”, không khẳng định đúng với mọi claim.
- Nếu nhiều ca không có đáp án người hoặc bị BLOCKED → kết luận “chưa đủ điều kiện xác nhận”.

## Bước 12 — Lưu kết quả và tắt app

Trong Notepad, `Ctrl+S`. Trong B, kiểm tra file đã lưu:

```powershell
Get-ChildItem -LiteralPath $humanCheckDir | Select-Object Name,Length
Write-Output "Kết quả buổi kiểm tra nằm tại: $humanCheckDir"
```

**Bộ bàn giao tối thiểu:** `KET_QUA_HUMAN_CHECK.md`, `git_commit.txt`, `00_environment.log`, log HC-11/HC-12 và ảnh/ghi chú nguồn nếu có. Thư mục này được giữ local theo `.gitignore`; không cần commit log để hoàn thành kiểm tra.

Quay sang cửa sổ A, bấm `Ctrl+C` để dừng app. Bạn đã hoàn tất quy trình từ chạy project đến chấm và báo lỗi.

Nếu cần mở rộng lên 30 ca, chấm hai người hoặc kiểm tra ngày tuyệt đối, bảng giá JS, robots và các tình huống khác, dùng [tài liệu tiêu chí và ca thử mở rộng](HUMAN_CHECK_TIEU_CHI_VA_CA_THU.md).
