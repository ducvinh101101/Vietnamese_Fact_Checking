# Ghi chú lỗi còn lại và hướng cải thiện (cập nhật 21/11/2026, tối)

> Ghi chú để làm tiếp. Số liệu: `outputs/metrics/source_attribution_realworld_web_v2.json` (lần chạy web thật mới,
> 300 claim), `outputs/metrics/source_attribution_realworld_replay_final.json` (chấm lại từ bản ghi web với cấu
> hình hiện tại). Bối cảnh: [SOURCE_ATTRIBUTION.md](SOURCE_ATTRIBUTION.md) §5.4,
> [NHAT_KY_THAY_DOI_KIEM_TRA_NGUON.md](NHAT_KY_THAY_DOI_KIEM_TRA_NGUON.md).

## 0. Trạng thái hiện tại

| Mục | Trạng thái |
|---|---|
| Commit `113a9c7` → `b551592` (6 commit) | **Trên máy, chưa push** |
| Dev ViFactCheck (1.252 claim) | **83,64%** (trước 83,08%); báo nhầm "có nguồn" **4,91%** (trước 5,83%) |
| Tập test ViFactCheck | 83,3% (chạy một lần, cấu hình cũ) – **chưa đo lại** với cấu hình mới |
| Tập thực tế 300 claim | Web thật lần 2: **51,3%**; chấm lại cấu hình mới: **51,0%**; báo nhầm "có nguồn" 1/140 |
| Credit Tavily (key mới, gói Researcher 1.000/tháng) | **614/900** (hạn mức tự đặt) – còn 286 |
| Bản ghi web 300 claim | `.cache/realworld_web_snapshot.jsonl` (không commit) – chấm lại bằng `--replay`, 0 credit |
| Pull Request vào `main` | Chưa – đợi thầy/nhóm xem |

**Quy tắc:** tập thực tế 300 claim chỉ dùng để **chẩn đoán** (soi lỗi), không dò ngưỡng / chọn cấu hình. Mọi thay
đổi đã làm đều được chọn theo **dev**; số trên tập thực tế chỉ để báo cáo.

---

## 1. Đã xử lý (21/11)

| Lỗi | Nguyên nhân thật | Cách sửa |
|---|---|---|
| Đổi key Tavily vẫn bị chặn | Sổ đếm lượt dùng chung mọi key | Đếm riêng theo dấu vân tay sha256 của key |
| moh.gov.vn không tải được | Máy chủ dùng khóa DH quá yếu (**không phải** thiếu chứng chỉ trung gian) | Không đề nghị cipher DHE (như Chrome) |
| www.sggp.org.vn không tải được | Kho CA Windows của Python thiếu root GlobalSign R6 | Nạp thêm root của `certifi` |
| Chạy chậm | Tự giới hạn 10 request/phút | 60/phút (key dev Tavily cho 100) |
| `test_w3_07` lỗi hash | `core.autocrlf` đổi LF → CRLF | `.gitattributes`: `*.jsonl` và file policy luôn LF |
| rw045 lỗi web | Không tái hiện ở lần chạy mới (0/300 lỗi web) | Nay lỗi được ghi vào `last_errors` |
| Facet "hơn/gần/khoảng" báo lệch giả | So số chính xác | Số gần đúng trong khoảng hợp lý là khớp (cả facet lẫn điểm lexical) |
| Facet so tháng "11" với năm "2026" | Coi mọi ngày 1 phần là cùng loại | So theo loại (số phần + có năm hay không) |
| Facet: đoạn có số bất kỳ → số của claim "lệch" | Quá gắt | Chỉ số trong đoạn **không khớp số nào** của claim mới là căn cứ |
| "1km", "50.000m²" không được trích | Regex đòi số không dính chữ | Cho phép đơn vị dính phía sau |
| "8-10%" bị đọc thành ngày 08/10 | Regex ngày | Không bắt khoảng phần trăm; chỉ bỏ vùng ngày hợp lệ |
| Truy vấn web dùng `162400000000000`, `01/01/2028` | Dùng dạng chuẩn hóa | Dùng số/ngày như claim viết (**chưa đo trên web thật**) |
| Xác nhận dù đoạn không nhắc số của claim | Chỉ dựa vào verifier | `decision.require_claim_numbers` (gom số theo bài) |

---

## 2. Lỗi còn mở – recall tin thật thấp (~29%)

112 tin thật bị trượt (lần chạy web thật lần 2), phân theo tầng chặn của đoạn tốt nhất:

| Tầng chặn | Số claim | Ghi chú |
|---|---:|---|
| Điểm liên quan 0,4–0,7, chưa tới verifier | 40 | Ngưỡng 0,7 dò trên ViFactCheck (claim gần nguyên văn) – quá chặt với tin viết lại |
| **Verifier RT-V3 đánh REFUTED** | 36 | Có ca verifier sai rõ: rw002 ("hơn 430 km" ↔ "430,5 km"), rw038 (gần như chép nguyên câu) |
| Không có bài liên quan (< 0,4) | 29 | Tìm kiếm trượt thật |
| Verifier chưa đủ chắc | 6 | |

`miss_stage` (so với **đúng bài gốc** được gán): `search_miss` 69, `below_threshold` 31, `verifier` 6, `facet_conflict` 5,
`not_read` 2, `outranked` 1. Lưu ý: nhiều `search_miss` thật ra có bài **báo khác** cùng sự việc (vd. rw002 có bài
znews cùng nội dung) – tìm kiếm không hẳn trượt, mà bị chặn ở ngưỡng/verifier.

**Nghi lỗi nhãn:** rw041 claim ghi "9 giờ sáng **21.7**", bài nguồn ghi "**21.11**" – nhờ nhóm kiểm lại phiếu.

## 3. Việc nên làm tiếp (theo thứ tự)

1. **Push** 6 commit (cần nhóm đồng ý).
2. **Chạy lại tập test ViFactCheck một lần** với cấu hình mới để chốt số (dev 83,6%, không dò gì trên test).
3. **Tập dev thực tế riêng (~100 claim, cùng phiếu Excel)** – điều kiện để làm 4 và 5 mà không quá khớp tập 300 claim.
   Tốn ~200–400 credit (có chốt chặn hạn mức trong script).
4. **Ngưỡng riêng cho tin web** (40 claim kẹt ở 0,4–0,7): dò `relevance` / `support` cho đường web trên tập dev ở bước 3.
5. **Verifier cho văn bản báo** (36 claim REFUTED): fine-tune RT-V3 thêm cặp claim viết lại / số gần đúng
   (mẫu tương phản, kế hoạch cũ mục 9) – train trên GPU máy nhóm.
6. **Tìm kiếm:** đo truy vấn từ khóa mới, thử `topic: news` + giới hạn thời gian của Tavily, `max_pages` 6 → 8–10 –
   so trên tập dev ở bước 3.

### Tùy chọn (từ kế hoạch cũ)

* Train bi-encoder BE-V1 (`kaggle/finetune_bi_encoder.py`).
* Làm sạch chú thích ảnh, chuẩn NFC, bổ sung ngày/tiêu đề trong kho cục bộ.
* Pull Request vào `main` sau khi thầy/nhóm duyệt.

---

## 4. Lưu ý khi làm tiếp

* **Credit:** script tự từ chối chạy nếu số lượt tối đa (claim × 2 × 2) có thể vượt `monthly_credit_budget` (900).
  `/usage` của Tavily cập nhật trễ – sổ trên máy (`.cache/web_retrieval/usage.json`) là chốt chặn chính.
* **Chạy web thật** (ghi bản ghi vào `.cache/realworld_web_snapshot.jsonl`; `--groups recent_real,paraphrase` để
  chạy bớt):
  ```powershell
  .venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_GAN_NHAN_NGUON_V1.xlsx --output outputs\metrics\ten_file.json
  ```
* **Chấm lại không tốn credit** (sau khi đổi facet/ngưỡng/verifier):
  ```powershell
  .venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_GAN_NHAN_NGUON_V1.xlsx --replay .cache\realworld_web_snapshot.jsonl
  ```
* **Đo thay đổi facet trên dev trong vài giây** (không chạy lại model):
  ```powershell
  .venv\Scripts\python.exe scripts\evaluate_source_attribution.py --limit 1500 --load-assessments outputs\assessments\dev1500_rtv3blend_v3.pkl --recompute-facets
  ```
* **GPU:** nếu `torch.cuda.is_available()` là `False`, kiểm tra `Get-PnpDevice -Class Display`. Lỗi mã 43 sau khi
  đổi chế độ GPU → **Restart** máy.
* **Chạy app:** `.venv\Scripts\streamlit.exe run app.py` → http://localhost:8501.
* **Chạy test:** `.venv\Scripts\python.exe -m pytest -q` (190 test qua, không cần bỏ qua test nào).
