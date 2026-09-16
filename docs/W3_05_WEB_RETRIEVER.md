# W3-05 — Web retriever allowlist

## Bàn giao

`src.web_retriever.WebRetriever` triển khai nhánh web độc lập: Tavily search,
lọc exact-host allowlist, tải HTML có timeout/redirect guard, trích passage và
trả `RetrievedEvidence` có `passage_id`, URL, title, source, source type,
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
- Tối đa ba redirect, trang 1 MB, passage 120–800 ký tự, tối đa ba passage/trang.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_web_retriever.py tests\test_web_retrieval_config.py
```

Các test hoàn toàn offline, mock provider/page fetch và kiểm tra allowlist,
fallback không key, metadata, DNS private và HTML extraction. Chưa bật call API
thật, chưa trộn evidence web vào BM25/PhoBERT và chưa đo Recall/MRR/Macro-F1;
đó là W4-05/W5-01 sau khi có protocol đánh giá web.
