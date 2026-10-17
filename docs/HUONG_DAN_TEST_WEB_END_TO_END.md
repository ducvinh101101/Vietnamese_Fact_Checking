# Hướng dẫn test end-to-end CÓ web retrieval

> **Cập nhật 2026-10-11.** Web đã có trong giao diện (`streamlit run app.py` → thanh bên chọn "Local + web"). CLI và giao diện dựng chung qua `src/system_builder.py`, nên CLI giờ cũng dùng verifier theo config (RT-V2 ensemble + cặp-tối-thiểu). Allowlist hiện có 33 host (xem `configs/web_retrieval.yaml`), không còn 3 host như mô tả bên dưới. Key có thể đặt trong `.env` (`TAVILY_API_KEY=...`).

Ngày: 2026-10-03. Cho phép gõ một claim và xem verdict dựa trên bằng chứng **local + web hợp nhất**.

## Thành phần mới

| File | Vai trò |
|---|---|
| `src/fusion_retriever.py` | Hợp nhất local (BM25) + web (Tavily) bằng RRF, khử trùng, trả top-k |
| `scripts/run_web_fact_check.py` | CLI: nhập 1 claim → fusion → verifier (RT-V2 đã khóa) → verdict + citation có nguồn |

RRF (Reciprocal Rank Fusion) chỉ dùng thứ hạng nên không phụ thuộc thang điểm BM25 vs Tavily. Passage xuất hiện ở cả hai nguồn được ưu tiên. Web rỗng/lỗi → tự lùi về local (chính sách `fail_to: local_only`).

## Bước 1 — Lấy API key Tavily

1. Đăng ký tại https://www.tavily.com (gói free ~1.000 credit/tháng, không cần thẻ).
2. Lấy key dạng `tvly-xxxxxxxx`.
3. Đặt biến môi trường (PowerShell, **phiên hiện tại**):
```powershell
$env:TAVILY_API_KEY = "tvly-xxxxxxxx"
```
(Đặt vĩnh viễn: `setx TAVILY_API_KEY "tvly-xxxxxxxx"` rồi mở PowerShell mới.)

**Không** commit key vào Git.

## Bước 2 — Chạy

```powershell
py -3.13 scripts/run_web_fact_check.py --claim "Giá xăng tăng từ chiều nay"
```

Kết quả in ra:
- VERDICT: SUPPORTED / REFUTED / NOT_ENOUGH_INFO + điểm mô hình
- Danh sách bằng chứng top-k, mỗi dòng ghi **(local)** hay **(web)**, nguồn, URL; dấu ★ là đoạn được trích dẫn.

Đối chiếu chỉ-local (không gọi web) để thấy khác biệt:
```powershell
py -3.13 scripts/run_web_fact_check.py --claim "..." --local-only
```

## Điều kiện và lưu ý

- **Mạng:** máy phải ra được `api.tavily.com` và 3 host allowlist (`baochinhphu.vn`, `www.who.int`, `vnexpress.net`). Nếu mạng chặn, web trả rỗng → chỉ còn local.
- **Allowlist chặt:** web chỉ nhận đúng 3 host trên. Claim về chủ đề ngoài 3 nguồn này thường sẽ không có bằng chứng web → verdict dựa vào local, hoặc NEI. Muốn thêm nguồn: sửa `source_policy.allowlist` trong `configs/web_retrieval.yaml` (có review nguồn).
- **Thiếu key:** script in cảnh báo `[web] Thiếu biến môi trường TAVILY_API_KEY` và chạy local-only — vẫn ra verdict.
- **Verifier:** dùng đúng checkpoint đang khóa trong `configs/config.yaml` (RT-V2).
- Đây là **fusion cấp claim**, đã hiển thị trên Streamlit (chế độ "Local + web"). Luồng cả bài viết (tách claim → fusion từng claim → tổng hợp) vẫn chỉ có ở mức API (`src/article_pipeline.py`).

## Nếu lỗi

- `No module named rank_bm25` / `transformers` → `py -3.13 -m pip install -r requirements.txt`.
- Treo lâu ở bước web → mạng bị chặn tới Tavily; thử `--local-only` để xác nhận phần còn lại vẫn chạy.
- Cảnh báo `overflowing tokens ... longest_first` → **vô hại**, bỏ qua (cắt 256 token như mọi lần).
