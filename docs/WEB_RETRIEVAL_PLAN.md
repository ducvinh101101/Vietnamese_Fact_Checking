# Kế hoạch web retrieval có kiểm soát

**W2-07 hoàn thành: đã chốt provider, allowlist v1 và chính sách key.**
Ứng dụng vẫn chỉ chạy local; adapter search, tải trang và tích hợp là W3-05/R4.
Config `configs/web_retrieval.yaml` là hợp đồng triển khai, chưa tự thực thi quota,
redirect/DNS protection hay fallback trong pipeline. Có validator/test offline.

## Quyết định provider (2026-09-05)

Chọn **Tavily Search basic**, POST `https://api.tavily.com/search`. Dùng
`Authorization: Bearer ...` từ biến môi trường `TAVILY_API_KEY`.
Lý do: có `include_domains`, kết quả URL/title, cấu hình basic rõ ràng và gói
khởi đầu phù hợp thử nghiệm sinh viên. Tắt `auto_parameters`, `include_answer`
và `include_raw_content`; chỉ dùng search để tìm URL. Chất lượng tìm kiếm tiếng
Việt chưa được đo trực tiếp, phải kiểm tra trong W3-05 trước khi bật ứng dụng.

Theo [pricing Tavily](https://www.tavily.com/pricing), gói khởi đầu có 1.000 credits
tháng không cần thẻ; theo [API docs](https://docs.tavily.com/documentation/api-reference/endpoint/search),
basic dùng 1 credit/request và có bộ lọc domain. Giá/quota có thể đổi: kiểm tra
dashboard trước khi chạy. Không đăng ký trả phí hoặc tự bật pay-as-you-go.

Đã so với [Brave Search API](https://brave.com/search/api/): có API search chính thức
và tín dụng hàng tháng, nhưng lưu kết quả cần quyền lưu trữ phù hợp với gói.
Chưa chọn Brave cho MVP; không có fallback tự động sang provider khác.
Không dùng scraping trang kết quả Google/Bing làm provider dự phòng.

## Allowlist v1

| Host chính xác | Vai trò | Căn cứ |
|---|---|---|
| baochinhphu.vn | Nguồn sơ cấp về thông tin Chính phủ | https://baochinhphu.vn/ |
| www.who.int | Nguồn chuyên môn y tế quốc tế | https://www.who.int/vietnam |
| vnexpress.net | Báo chí tổng hợp; kiểm tra thêm nguồn và thời điểm | https://vnexpress.net/ |

Đây là lựa chọn phạm vi ban đầu của dự án, không bảo đảm mọi bài viết đều đúng.
Nguồn y tế dùng đúng phạm vi chuyên môn; không biến tên miền thành nhãn fact-check
hoặc điểm confidence. Chưa đưa các domain chưa kiểm chứng truy cập vào v1.
Quang quản lý thay đổi config; Vinh được mời review nguồn trong phối hợp sau này,
không ghi rằng Vinh đã phê duyệt danh sách này.

Match hostname chính xác bằng parser URL, không tìm substring, không wildcard
toàn bộ `.gov.vn`, không tự chấp nhận subdomain. Host khác như `who.int` hoặc
`www.vnexpress.net` phải được review rồi thêm riêng nếu thực tế cần dùng.
Lọc kết quả sau search dù đã gửi `include_domains`. HTTPS, không userinfo,
không port lạ. W3-05 phải kiểm tra từng redirect và địa chỉ DNS/IP đích để chặn
loopback/private/link-local, kể cả DNS rebinding; không gửi key search khi tải trang.
Test URL hiện có chỉ kiểm tra cú pháp/allowlist, chưa thay cho bảo vệ mạng này.

## API key, quota và dữ liệu

- Mỗi người tạo key riêng trên dashboard Tavily; không gửi key qua chat/Excel/Git.
  W3-05 đọc environment. `.env.example` chỉ là mẫu; repo hiện chưa tự nạp `.env`.
  Có thể đặt key trong environment qua công cụ quản lý secret của máy, tránh
  gõ literal key trong shell history. CI dùng repository secret khi có test online
  được bật rõ ràng, không cấp key cho PR không tin cậy. Test mặc định offline.
- `.env`, `.env.*` (trừ mẫu), `.streamlit/secrets.toml`, `.cache/` bị Git ignore.
  Không ghi Authorization, key, response body đầy đủ hoặc claim nhạy cảm vào log.
  Khi lộ key: thu hồi ngay, tạo key mới, kiểm tra usage và xử lý lịch sử Git nếu có.
- Chỉ gửi claim công khai/tối thiểu tới provider khi người dùng bật web; không gửi
  cả tài liệu riêng. Thiếu key/hết quota/lỗi mạng: trả trạng thái lý do và dùng local.
  Không suy diễn lỗi mạng thành kết luận claim sai hoặc tự đổi nhãn verifier.
- Giới hạn dự án: 1 request/claim, 10 request/phút, 900 credits/tháng. Mỗi lần retry
  cũng trừ budget dự phòng. W3-05 cần bộ đếm lưu local theo tháng UTC, đồng bộ giữa
  tiến trình, đối chiếu usage dashboard; không chỉ dựa vào đếm trong bộ nhớ.
- Timeout 15 giây/lần, tối đa 1 retry cho 429/5xx được cấu hình, tôn trọng
  Retry-After nhưng không chờ quá ngân sách thời gian. 401/403 hoặc hết quota không
  retry; fallback local. Không xem giới hạn dự án là rate limit chính thức provider.
- Cache local trong `.cache/web_retrieval`, metadata TTL 24 giờ; chưa cho phép
  persist provider response hoặc full page content. Chỉ mở lưu nội dung sau khi
  kiểm tra điều khoản nguồn/provider. Tôn trọng robots và hạn chế truy cập, không
  vượt paywall. Passage tải trực tiếp dùng tạm trong phiên; ghi nguồn/thời gian.

## Nghiệm thu W2-07 và bàn giao

Đầu vào: task không có dependency bắt buộc; kế hoạch web, data contract và local
retrieval đã tồn tại. Không cần GPU hoặc train model để chốt provider/config.
Đầu ra: kế hoạch này, YAML versioned, `.env.example`, ignore rules, validator và
tests allowlist chống giả mạo hostname. Không cần có key thật để hoàn thành W2-07.

```powershell
.\.venv\Scripts\python.exe scripts/check_web_retrieval_config.py
.\.venv\Scripts\python.exe -m pytest -q
git check-ignore .env .env.local .streamlit/secrets.toml .cache/web_retrieval/check.json
```

W3-05 còn phải triển khai adapter, budget/rate limit, fetch/extract, mạng an toàn,
cache/fallback, metadata và test tích hợp bằng key local. Chưa có live API smoke
test ở W2-07; không dùng trạng thái hoàn thành kế hoạch để khẳng định web đã chạy.

## Mục tiêu

Bổ sung evidence thời gian thực từ các website uy tín, nhưng vẫn giữ kho evidence cục bộ là nguồn nền. Mỗi kết luận từ web phải hiển thị URL, domain, tiêu đề và thời điểm truy cập.

## Nguyên tắc nguồn

1. Chỉ nhận kết quả thuộc allowlist do nhóm quản lý; mặc định ưu tiên cổng cơ quan nhà nước, tổ chức quốc tế và báo chí uy tín đã được chấp thuận.
2. Không lấy kết quả từ blog cá nhân, mạng xã hội, trang tổng hợp không rõ tác giả hoặc domain ngoài allowlist.
3. Không coi thứ hạng tìm kiếm là bằng chứng. Chỉ passage trích trực tiếp từ trang được duyệt mới được gửi cho verifier.
4. Lưu snapshot/metadata tối thiểu để truy vết: `title`, `url`, `domain`, `fetched_at`, `source_tier` và passage.

## Luồng dự kiến

```text
Claim
 ├─ BM25 kho evidence cục bộ
 └─ Search provider → lọc allowlist → tải trang → trích passage
                         │
                         ▼
             hợp nhất và khử trùng evidence
                         │
                         ▼
                   PhoBERT verifier
                         │
                         ▼
 nhãn + confidence + citation + thời điểm truy cập
```

## Các bước triển khai web

1. Đã chốt Tavily Search basic, quota dự án và biến môi trường trong W2-07.
2. Đã chốt allowlist v1 theo bảng trên và YAML; mở rộng phải review riêng.
3. Xây web retriever: timeout, retry giới hạn, tôn trọng điều khoản trang, lọc domain, tải trang và trích main text.
4. Chia passage, khử URL trùng và xếp hạng cùng evidence cục bộ.
5. Hiển thị nguồn web trong UI với URL và thời điểm truy cập; cho phép tắt web retrieval.
6. Đo Recall@3/5, MRR, latency; sau đó mới đo Macro-F1 end-to-end với evidence thực truy hồi.

## Quy tắc kết luận

- Nếu không có passage web/cục bộ liên quan đủ mạnh, trả `NOT_ENOUGH_INFO`.
- Không thay nhãn chỉ vì có nhiều kết quả search cùng chiều.
- Evidence cục bộ đã kiểm duyệt được ưu tiên hơn evidence web trong cùng mức liên quan.
- Các claim thuộc lĩnh vực nhạy cảm (y tế, pháp luật, tài chính) ưu tiên nguồn cơ quan có thẩm quyền; UI luôn hiển thị nguồn để người dùng tự kiểm tra.

## Tiêu chí hoàn thành

| Hạng mục | Điều kiện |
|---|---|
| An toàn nguồn | 100% evidence web trả về thuộc allowlist |
| Minh bạch | Mỗi evidence có URL, domain, title và thời điểm truy cập |
| Chất lượng retrieval | Có Recall@3, Recall@5, MRR và latency trên tập query cố định |
| Chất lượng end-to-end | Báo cáo tách oracle evidence, retrieval và end-to-end |
| Tái lập | Có cấu hình provider/allowlist versioned; API key không nằm trong Git |

## Liên kết roadmap 6 tuần

Web retrieval là một nhánh của roadmap 6 tuần, không thay thế corpus cục bộ hay nhánh content-risk. Xem [ma trận yêu cầu](MA_TRAN_YEU_CAU_DE_TAI.md) để biết task, thí nghiệm và tiêu chí đánh giá liên quan.
