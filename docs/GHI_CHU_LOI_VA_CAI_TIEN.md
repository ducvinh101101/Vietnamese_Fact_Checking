# Ghi chú lỗi còn lại và hướng cải thiện (cập nhật 21/11/2026)

> Ghi chú để làm tiếp. Số liệu lấy từ `outputs/metrics/source_attribution_realworld_web.json` (300 claim thực tế)
> và các lần chạy thử trong ngày. Bối cảnh đầy đủ: [SOURCE_ATTRIBUTION.md](SOURCE_ATTRIBUTION.md) §5.4,
> [NHAT_KY_THAY_DOI_KIEM_TRA_NGUON.md](NHAT_KY_THAY_DOI_KIEM_TRA_NGUON.md).

## 0. Trạng thái hiện tại

| Mục | Trạng thái |
|---|---|
| Commit `9f5978e` (sửa robots.txt), `e2be0a1` (kết quả tập thực tế) | Đã push (21/11) |
| Lưu chi tiết chấm từng claim (bước 2) | Xong (21/11) – chưa chạy lại với web (đợi lượt Tavily) |
| Tập test ViFactCheck | Đã chạy một lần: 83,3% – không dò ngưỡng trên test nữa |
| Tập thực tế 300 claim | Đã chạy: có web 49,3%, không web 23,7%; báo nhầm "có nguồn" 0/140 |
| Lượt Tavily tháng 11/2026 | 782/900 (hạn mức tự đặt) – còn ~55 claim; reset đầu tháng 12 |
| Pull Request vào `main` | Chưa – đợi thầy/nhóm xem |

**Quy tắc:** tập thực tế 300 claim đã dùng để đo → **không dò ngưỡng / chọn cấu hình trên tập này**. Muốn dò
ngưỡng cho tin web thì gán một tập riêng (~100 claim) bằng cùng phiếu Excel.

---

## 1. Lỗi còn mở

### 1.1 Recall tin thật thấp (vấn đề chính)

Trên 160 tin thật (`recent_real` + `paraphrase`): chỉ 51 được "Có nguồn xác nhận" (32%).

| Hệ thống trả | Số claim | Ghi chú (đo từ file kết quả) |
|---|---:|---|
| "Không tìm thấy nguồn" | 76 | Điểm liên quan cao nhất: **24 claim ≥ 0,6** (sát ngưỡng 0,7), 19 claim 0,4–0,6, **33 claim < 0,4** (gần như không thấy bài liên quan) |
| "Có nguồn nhưng lệch chi tiết" | 33 | Chỉ 6/33 trích đúng bài gốc → phần lớn là bài **khác** cùng chủ đề có số/ngày khác, hoặc facet lệch do cách viết |
| "Có nguồn xác nhận" | 51 | 33/51 trích đúng bài gốc; nguồn hay gặp: vnexpress, tuoitre, thanhnien, vietnamnet |

Ví dụ đã soi tay:
* rw011 (cổ phiếu Micron/AMD): Tavily **không trả** bài gốc.
* rw022 (Quốc hội thông qua 3 luật y tế): tìm **đúng bài** tuoitre.vn nhưng điểm liên quan 0,68 < 0,7.
* rw023 (Hà Nội nhận đất Phú Thọ): chỉ ra bài cũ cùng chủ đề, không có bài gốc.
* rw009: trước khi sửa robots.txt bị "Không tìm thấy"; sau khi sửa → "Có nguồn xác nhận" đúng bài.

**Giả thuyết cần kiểm chứng** (chưa đo):
1. Khoảng 1/3 lỗi do **tìm kiếm** (Tavily không trả bài gốc) → nhóm < 0,4.
2. Khoảng 1/3 do **ngưỡng** dò trên ViFactCheck quá chặt với văn bản báo 2026 → nhóm ≥ 0,6.
3. "Lệch chi tiết" sai do **facet**: số viết khác (`162.400` / `162,4 nghìn`), ngày `21-11` / `21/11`,
   từ xấp xỉ "hơn", "gần", "khoảng".

### 1.2 Một claim lỗi web không rõ nguyên nhân

`rw045` có `web_status = error`: WebRetriever ném ngoại lệ ngoài dự kiến, bị `FusedRetriever` nuốt, **nội dung lỗi
không được lưu**. *Từ 21/11:* script chấm lưu `last_errors` vào từng dòng – lần chạy sau sẽ thấy lỗi gì.

### 1.3 Hai nguồn trong allowlist không tải được

`moh.gov.vn`, `www.sggp.org.vn`: máy chủ gửi thiếu chứng chỉ SSL trung gian → Python từ chối. **Không** tắt kiểm
tra SSL. Cách đúng: bổ sung chứng chỉ trung gian của họ vào một file CA riêng (certifi + intermediate) cho
WebRetriever.

### 1.4 Chạy chậm do giới hạn tự đặt

`requests_per_minute: 10` → ~5 claim/phút → 300 claim mất ~70 phút. Giới hạn thật của gói Tavily cao hơn; kiểm tra
gói đang dùng rồi nâng (vd. 30–60/phút) nếu được.

### 1.5 Lỗi có từ trước, chưa sửa

`tests/test_versioned_evidence_corpus.py::test_w3_07_*` lỗi do `core.autocrlf=true` làm sai hash corpus (có từ trước
nhánh). Đang bỏ qua khi chạy test (`--deselect tests/test_versioned_evidence_corpus.py`).

---

## 2. Việc nên làm tiếp (theo thứ tự)

### Ưu tiên cao

1. ~~**Push** 2 commit `9f5978e`, `e2be0a1` lên GitHub.~~ Xong 21/11.
2. ~~**Lưu chi tiết chấm từng claim**~~ Xong 21/11. Mỗi dòng trong file kết quả giờ có:
   * `web_trace` (từ `WebRetriever.last_trace`): truy vấn đã gửi, mọi URL Tavily trả (hạng, điểm), kết quả từng
     trang `used / no_passages / robots_blocked / fetch_failed / not_allowed / duplicate / not_read` kèm lỗi và
     điểm liên quan cao nhất;
   * `source_diagnosis`: bài gốc có trong kết quả tìm kiếm không (hạng), tải được không, điểm liên quan cao nhất
     của đoạn bài gốc, `conflicting_details`;
   * `assessed` (8 đoạn được chấm, nội dung cắt 400 ký tự), `best_relevance`, `last_errors`;
   * `miss_stage` cho tin thật bị trượt; tổng hợp ở `report.miss_stage_counts`.
3. **Phân tích lỗi recall** (chạy lại ~60–100 claim tin thật, đầu tháng 12 khi có lượt): đọc
   `report.miss_stage_counts` – các tầng `search_miss / fetch_failed / not_read / robots_blocked / no_passages /
   outranked / below_threshold / facet_conflict / verifier / web_error` → biết sửa phần nào trước. Lọc tin thật
   thành CSV riêng (cột `claim_id,group,claim,expected_label,source_url`) để chỉ tốn lượt cho các claim đó.
4. **Báo cáo thầy**: test 83,3%; thực tế có web 49,3%, không bao giờ bịa nguồn (precision 100%), recall tin thật 32%.

### Ưu tiên trung bình

5. **Facet số / ngày** (`src/source_attribution.py::check_facets`, `src/vi_text.py`): chuẩn hóa số (dấu chấm/phẩy,
   "nghìn/triệu/tỷ"), ngày `dd-mm` / `dd/mm` / "ngày 21 tháng 11", bỏ qua lệch nhỏ khi claim có "hơn/gần/khoảng".
   Thêm test cho từng dạng.
6. **Tìm kiếm cho tin mới**: thử `topic: news` (+ giới hạn thời gian) của Tavily cho claim có mốc gần đây, tăng
   `max_pages` 6 → 8–10, thêm truy vấn theo tên riêng + con số. So sánh trên tập riêng, không trên tập 300 claim.
7. **Ngưỡng cho tin web**: gán ~100 claim mới (tập dev thực tế) → dò lại `relevance` / `support` cho đường web
   (có thể tách ngưỡng local và web).
8. Sửa lỗi SSL cho moh.gov.vn, www.sggp.org.vn (mục 1.3) và nâng giới hạn request/phút (mục 1.4).

### Tùy chọn (từ kế hoạch cũ)

9. Mẫu tương phản để verifier bớt phụ thuộc độ trùng từ.
10. Train bi-encoder BE-V1 (`kaggle/finetune_bi_encoder.py`).
11. Làm sạch chú thích ảnh, chuẩn NFC, bổ sung ngày/tiêu đề trong kho cục bộ.
12. Tạo Pull Request vào `main` sau khi thầy/nhóm duyệt.

---

## 3. Lưu ý khi làm tiếp

* **GPU:** nếu `torch.cuda.is_available()` là `False`, kiểm tra `Get-PnpDevice -Class Display`. Lỗi mã 43 sau khi
  đổi chế độ GPU → **Restart** máy (không phải Shut down).
* **Lệnh chấm tập thực tế** (chạy nền, ~70 phút với giới hạn hiện tại):
  ```powershell
  .venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_GAN_NHAN_NGUON_V1.xlsx
  .venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_GAN_NHAN_NGUON_V1.xlsx --no-web
  ```
* **Hết lượt Tavily:** đổi `TAVILY_API_KEY` trong `.env`; script đang chạy không nhận key mới, phải chạy lại.
* **Chạy app:** `.venv\Scripts\streamlit.exe run app.py` → http://localhost:8501.
* **Chạy test:** `.venv\Scripts\python.exe -m pytest -q --deselect tests/test_versioned_evidence_corpus.py`
  (164 test qua sau bước 2, 21/11).
