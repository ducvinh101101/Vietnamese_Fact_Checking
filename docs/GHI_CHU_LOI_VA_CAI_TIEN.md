# Ghi chú lỗi còn lại và hướng cải thiện (cập nhật 21/11/2026, tối)

> Ghi chú để làm tiếp. Số liệu: `outputs/metrics/source_attribution_realworld_web_v2.json` (lần chạy web thật mới,
> 300 claim), `outputs/metrics/source_attribution_realworld_replay_final.json` (chấm lại từ bản ghi web với cấu
> hình hiện tại). Bối cảnh: [SOURCE_ATTRIBUTION.md](SOURCE_ATTRIBUTION.md) §5.4,
> [NHAT_KY_THAY_DOI_KIEM_TRA_NGUON.md](NHAT_KY_THAY_DOI_KIEM_TRA_NGUON.md).

## 0. Trạng thái hiện tại

| Mục | Trạng thái |
|---|---|
| Commit `113a9c7` → `9bdcae7` (7 commit) | Đã push lên `feature/source-attribution-retrieval` |
| Dev ViFactCheck (1.252 claim) | RT-V4: **84,29%** (RT-V3 83,64%, trước nữa 83,08%); báo nhầm "có nguồn" 5,06% (RT-V3 4,91%) |
| Verifier | **RT-V4** `models/rt_v4_augmented` (mục 1b); ngưỡng relevance 0,7 → 0,75 (dò trên dev) |
| Ngưỡng riêng cho web | `decision.web_thresholds` relevance 0,55 / support 0,6 – dò trên tập dev thực tế (mục 1c) |
| Tập dev thực tế | `PHIEU_DEV_THUC_TE.xlsx` 70 claim, bản ghi `.cache/realdev_web_snapshot.jsonl` (144 credit) |
| Tập thực tế 300 claim (kiểm tra độc lập cho ngưỡng web) | **60,7%** (trước 51,3%); báo nhầm "có nguồn" **4/140** (trước 1/140) |
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

## 1b. Verifier RT-V4 (21/11, tối)

**Chẩn đoán** (34 tin thật bị verifier đánh REFUTED trên tập 300 claim): phần lớn là đoạn của sự việc **khác**
(verifier đúng); ca sai thật là **cùng thông tin, khác cách viết** – rw020 "1-3-2027" ↔ "1.3.2027" (REFUTED 0,99),
rw070 "2 năm" ↔ "hai năm", rw017 "21/11" ↔ "21.11". ViFactCheck chép nguyên định dạng nên RT-V3 chưa thấy.

**Dữ liệu** `scripts/build_verifier_augmented_data.py` → `data/processed/verifier_windows_v4`: train RT-V3 (6.103)
+ 1.256 mẫu chỉ đổi claim – giữ nhãn (đổi định dạng ngày, "2" ↔ "hai", "700.000" → "700 nghìn", "430,5" → "hơn 430")
và tương phản (đổi định dạng **và** giá trị → REFUTED). Không đọc dev/test/tập thực tế. Train từ RT-V3, 2 epoch,
chọn checkpoint trên dev **gốc**.

| | RT-V3 | RT-V4 |
|---|---:|---:|
| Dev cặp gốc, macro-F1 | 81,0% | **81,7%** |
| Dev đổi định dạng, macro-F1 (chỉ đo) | 72,6% | **79,6%** |
| – ngày đổi định dạng / "hai năm" / "700 nghìn" | 67,9 / 86,1 / 33,3% | 76,2 / 88,9 / 41,7% |
| Dev ViFactCheck end-to-end, TB 5 nhóm (ngưỡng dò trên dev) | 83,64% | **84,29%** |
| – nhóm A (có nguồn) / báo nhầm "có nguồn" | 76,7% / 4,91% | **80,0%** / 5,06% |
| Tập thực tế 300 claim, phát lại (chỉ báo cáo) | 51,0% | 51,3% |
| – tin thật recent_real / paraphrase / perturbed | 31 / 25 / 52,9% | 35 / 30 / 44,3% |

* "Số gần đúng" (`hơn 430`) vẫn 0/4 trên dev đổi định dạng – chỉ 31 mẫu train; cần thêm mẫu.
* Nhóm perturbed giảm vì **ngưỡng relevance 0,75**: đoạn web của các claim này ở 0,70–0,74 (verifier không đổi
  quyết định). Đúng vấn đề "ngưỡng riêng cho web" ở mục 3 bước 4 – dò trên tập dev thực tế, không trên 300 claim.
* Quay lại RT-V3: `verifier.model_path: models/rt_v3_windows/best_model`, `relevance: 0.7`.

```powershell
.venv\Scripts\python.exe scripts\build_verifier_augmented_data.py
.venv\Scripts\python.exe kaggle\finetune_phobert_retrieval_v1.py --data-dir <abs>\data\processed\verifier_windows_v4 `
  --model-dir <abs>\models\rt_v3_windows\best_model --output-dir <abs>\models\rt_v4_augmented `
  --vncorenlp-dir <abs>\models\vncorenlp --experiment RT-V4 --epochs 2      # ~5 phút trên RTX 5060
.venv\Scripts\python.exe scripts\evaluate_source_attribution.py --limit 1500 --verifier --sweep `
  --save-assessments outputs\assessments\dev1500_rtv4.pkl
```

## 1c. Ngưỡng riêng cho web (22/11)

Tập dev thực tế `PHIEU_DEV_THUC_TE.xlsx`: 70 claim (25 recent_real, 15 paraphrase, 15 perturbed, 15 fabricated),
0 bài trùng V1, kiểm tra chéo 24/24 đồng ý. Web thật 1 lần: 70/70 `ok`, 144 credit (key hiện tại 758/900).
Dò lưới `--replay --sweep` (relevance 0,45–0,70 × support 0,60–0,80), chọn TB nhóm cao nhất với báo nhầm ≤ 5%.
Đoạn kho cục bộ giữ ngưỡng cũ → ViFactCheck không đổi.

| | Web dùng ngưỡng chung 0,75/0,8 | Web 0,55/0,6 |
|---|---:|---:|
| Dev thực tế 70 claim, TB nhóm | 46,7% | **63,7%** |
| 300 claim (không dùng để chọn), độ chính xác | 51,3% | **60,7%** |
| – recent_real / paraphrase / perturbed / fabricated | 35 / 30 / 44,3 / 100% | 42 / 41,7 / 85,7 / **78,6%** |
| – báo nhầm "có nguồn" | 1/140 | **4/140** |

**Còn mở:** 3 tin bịa được "xác nhận" bằng đoạn liên quan lỏng (relevance 0,56–0,64, verifier SUPPORTED 0,71–0,96,
vd. "nghỉ hè 6 tháng" ↔ "nghỉ hè tối đa 6 tuần"); 12 tin bịa ra SOURCE_CONFLICT. Dev chỉ có 15 tin bịa nên không
thấy. **Không chỉnh lại theo 300 claim** – thêm ~30 tin bịa vào tập dev (~60 credit, `--skip-recorded`) rồi dò trên dev
quy tắc kiểu "relevance < 0,7 thì cần support cao hơn".

```powershell
.venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_DEV_THUC_TE.xlsx --replay .cache\realdev_web_snapshot.jsonl --sweep --output outputs\metrics\source_attribution_realdev_replay.json
```

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

1. ~~Push~~ – đã xong.
2. **Chạy lại tập test ViFactCheck một lần** với cấu hình mới để chốt số (dev 83,6%, không dò gì trên test).
3. **Tập dev thực tế riêng (~100 claim, cùng phiếu Excel)** – điều kiện để làm 4 và 5 mà không quá khớp tập 300 claim.
   Tốn ~200–400 credit (có chốt chặn hạn mức trong script).
4. **Ngưỡng riêng cho tin web** (40 claim kẹt ở 0,4–0,7): dò `relevance` / `support` cho đường web trên tập dev ở bước 3.
5. **Verifier cho văn bản báo:** RT-V4 đã làm (mục 1b). Còn: thêm mẫu số gần đúng (0/4), mẫu "claim thêm chi
   tiết bài không có → NEI" (rw018/rw068 "34 giường" bị đánh REFUTED).
6. **Tìm kiếm:** đo truy vấn từ khóa mới, thử `topic: news` + giới hạn thời gian của Tavily, `max_pages` 6 → 8–10 –
   so trên tập dev ở bước 3.

### Lệnh cho bước 3–4 (tập dev thực tế)

```powershell
# 1. Tạo phiếu dev 70 claim (mã dv001–dv070)
.venv\Scripts\python.exe scripts\create_realworld_labeling_form.py --output data\evaluation\PHIEU_DEV_THUC_TE.xlsx --prefix dv --targets recent_real=25,paraphrase=15,fabricated=15,perturbed=15
# 2. Chạy thử 0 credit (chỉ kho cục bộ) – bắt lỗi phiếu, trùng bài với V1
.venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_DEV_THUC_TE.xlsx --no-web --exclude-articles data\evaluation\PHIEU_GAN_NHAN_NGUON_V1.xlsx
# 3. Web thật MỘT lần (~140 credit thực, script chặn nếu trường hợp xấu nhất vượt 900)
.venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_DEV_THUC_TE.xlsx --exclude-articles data\evaluation\PHIEU_GAN_NHAN_NGUON_V1.xlsx --snapshot .cache\realdev_web_snapshot.jsonl --skip-recorded --output outputs\metrics\source_attribution_realdev_web.json
# 4. Mọi lần thử sau: phát lại, 0 credit
.venv\Scripts\python.exe scripts\evaluate_source_attribution_realworld.py data\evaluation\PHIEU_DEV_THUC_TE.xlsx --replay .cache\realdev_web_snapshot.jsonl --output outputs\metrics\source_attribution_realdev_replay.json
```

Sau bước 3 **không sửa câu claim** trong phiếu (bản ghi tra theo nội dung claim). Thiếu credit: thêm `--limit N`,
tháng sau chạy lại đúng lệnh 3 – `--skip-recorded` bỏ các claim đã chạy.

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
