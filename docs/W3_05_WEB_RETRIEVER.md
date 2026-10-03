# W3-05 — Web retriever allowlist

## Bàn giao

`src.web_retriever.WebRetriever` triển khai nhánh web độc lập: Tavily search,
lọc exact-host allowlist, tải HTML có timeout/redirect guard, trích passage và
trả `RetrievedEvidence` có `passage_id`, URL, `domain`, title, source, source type,
authority score và `retrieved_at` UTC. Mặc định `enabled: false`; thiếu
`TAVILY_API_KEY` hoặc lỗi mạng đều trả danh sách rỗng để caller dùng local-only.

Không có key trong config/log/output. Provider response và nội dung trang không
được ghi cache. Chỉ bộ đếm quota local trong `.cache/web_retrieval` được lưu,
không chứa claim, key hoặc page content.

## Rào chắn nguồn

- Chỉ HTTPS exact hostname trong YAML; chặn credentials, port lạ, hostname giả.
- Kiểm tra DNS công khai trước mỗi request và sau từng redirect; chặn loopback,
  private, link-local và địa chỉ không global.
- Không tự dùng snippet của provider: chỉ passage trích từ HTML trang nguồn
  allowlist mới được trả.
- Đọc `robots.txt` từ chính host đã allowlist trước khi tải trang. Lỗi khi đọc
  robots bị từ chối theo chính sách `robots_failure: deny`; không có file
  `robots.txt` được coi là cho phép.
- Giải nén `gzip`/`deflate` và ưu tiên charset khai báo trong HTML để không đưa
  bytes nén hoặc text lỗi mã hóa vào evidence; content encoding khác bị từ chối.
- Tối đa ba redirect, trang 1 MB, passage 120–800 ký tự, tối đa ba passage/trang.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_web_retriever.py tests\test_web_retrieval_config.py
```

Các test hoàn toàn offline, mock provider/page fetch và kiểm tra allowlist,
fallback không key, metadata, DNS private, `robots.txt` và HTML extraction.
Chưa bật call API thật trong test CI.

## Nghiệm thu live

Một live smoke một URL không đủ nghiệm thu. Chạy từ **PowerShell của người giữ
key** (không nhập key vào tham số và không commit báo cáo):

```powershell
.\.venv\Scripts\python.exe scripts\run_web_retrieval_acceptance.py
```

Script chạy ba truy vấn, yêu cầu mỗi truy vấn có evidence và tổng cộng ít nhất
hai domain allowlist, đồng thời không có passage trùng trong cùng URL. Báo cáo local `outputs/web_retrieval/acceptance_report.json`
chỉ có hash của query/passage cùng URL, domain, title, source và fetched_at;
không chứa API key hoặc nội dung passage. Exit code 0 mới là đạt. Chưa trộn
evidence web vào BM25/PhoBERT và chưa đo Recall/MRR/Macro-F1; đó là W4-05/W5-01
sau khi có protocol đánh giá web.

Kết quả nghiệm thu ngày 2026-09-16: cả ba truy vấn đều `ok`, có 9 passage từ
5 URL thuộc ba domain allowlist (`baochinhphu.vn`, `www.who.int`,
`vnexpress.net`); đầy đủ URL/domain/title/fetched_at và không có hash passage
trùng trong cùng URL. Đây xác nhận chức năng W3-05, không phải metric chất lượng
fact-check end-to-end.
