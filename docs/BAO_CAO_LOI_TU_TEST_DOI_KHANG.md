# Báo cáo lỗi từ bộ test đối kháng & challenge set

Ngày: 2026-10-04. Phạm vi: chuỗi RAG kiểm chứng (retrieval local/web → neo thời gian → rerank → verifier → guard) và verifier rule-based.

## 1. Bộ kiểm thử mới

| File | Vai trò | Cần model? |
|---|---|---|
| `tests/test_adversarial_findings.py` | Test đối kháng theo thành phần + hồi quy. **Mọi BUG-xx đã sửa (0 xfail, 2026-10-11)** — xem § 7 | Không |
| `scripts/challenge_set.py` | Sinh challenge set có **nhãn đúng theo cấu trúc** từ corpus (7 loại, 380 claim) | Không |
| `tests/test_challenge_set_construction.py` | 21 test khẳng định **nhãn vàng của challenge set là đúng** | Không |
| `scripts/run_challenge_eval.py` | Chạy challenge set qua pipeline production, báo cáo theo loại + tách lỗi retrieval/verifier + tác động guard | **Có (PhoBERT)** |

Cơ chế `xfail(strict=True)`: suite vẫn xanh khi lỗi chưa sửa; khi bạn sửa xong một lỗi, test tương ứng **XPASS → pytest báo FAIL** để nhắc gỡ nhãn `@bug(...)`. Không lỗi nào bị quên hay "tự khỏi" mà không ai biết.

### Độ tin cậy của phép đo

Trước khi chốt, mọi kỳ vọng đều được kiểm lại tay; đã loại các trường hợp mà chính bộ sinh có thể gán sai nhãn:
- Đổi số trong cụm giới hạn ("chưa đến 50%" → "chưa đến 68%" vẫn đúng) → loại.
- Số là mã/tên/thứ tự (COP27, U20, Quân khu 9, SEA Games 32, Honda 50) hoặc tạo giá trị vô nghĩa ("tháng 16") → loại.
- Đổi chiều tạo câu sai ngữ pháp ("tăng xuống") → đổi cặp "giảm xuống ↔ tăng lên".
- Câu hỏi/mệnh lệnh không phải phát biểu → loại khỏi nhóm SUPPORTED.
- Claim bịa chạm chủ đề có thật trong kho (Bộ Giáo dục, Ngân hàng Nhà nước, Olympic...) → thay; kiểm tự động bằng cặp âm tiết đặc trưng (≤ 27% trùng).

Nhiễu nhãn còn lại ước tính qua soát tay: REF_NEGATION ~5–7% (đổi "đã" trong mệnh đề quan hệ, vd "người dân đã đóng bảo hiểm"). Các loại khác không phát hiện nhiễu trong mẫu đã soát.

## 2. Danh sách lỗi

Mức độ: **Nghiêm trọng** = sai verdict ở luồng chính hoặc làm sai lệch số liệu đánh giá · **Cao** = sai verdict ở nhánh web/thời sự hoặc engine dự phòng · **Thấp** = ảnh hưởng xếp hạng/hiển thị.

### Nghiêm trọng

**BUG-I1 — Pipeline chính thức không đi qua GuardedVerifier. [ĐÃ SỬA, nhưng guard mặc định TẮT — xem 6.8]**
`FactCheckingPipeline` gọi thẳng verifier; guard chỉ nối trong CLI `run_web_fact_check.py`.
Đã sửa: tham số `guard` và `minimal_pair` tách riêng (cấu hình `verification.guard`, `verification.minimal_pair`). Mặc định constructor đều **False** để không đổi số liệu RT-V2 đã khóa; `app.py` bật `minimal_pair`, tắt `guard` (6.8). Cần quyết định có bật cho các script đánh giá e2e hay không sau khi A/B trên dev (xem mục 6).
Test: `test_pipeline_with_guard_flag_applies_verdict_guard`, `test_demo_app_defaults_guard_off_and_minimal_pair_on`.

**BUG-G1 — Chặn prompt-injection chặn nhầm tin tức thật. [ĐÃ SỬA]**
Regex `bỏ qua … (hướng dẫn|dữ liệu|đối chiếu)` khớp "Bộ Y tế khuyến cáo không **bỏ qua hướng dẫn** tiêm chủng", "không được **bỏ qua dữ liệu** quan trắc". Guard này chạy **trong `FactCheckingPipeline.run`**, nên ảnh hưởng mọi luồng: claim hợp lệ bị trả NEI trước cả khi truy xuất.
Sửa: chỉ coi là injection khi có dấu hiệu ra lệnh cho hệ thống (vd "hãy/bạn/mô hình/hệ thống" + bỏ qua, hoặc "bỏ qua mọi/tất cả hướng dẫn trước") **hoặc** đi kèm token nhãn (SUPPORTED/REFUTED/NEI). Giữ nguyên các mẫu `system:`/`ignore … instructions`.
Test: `test_input_guard_does_not_block_ordinary_news_claims` (2 ca).

**BUG-D1 — Lỗi nhánh web làm sập cả pipeline [ĐÃ SỬA]**
`FusionRetriever.search` không bắt ngoại lệ của `web.search` → trái chính sách `fail_to: local_only`. (Đã từng xảy ra thật với `IncompleteRead`.)
Sửa: bọc `self.web.search(...)` trong `try/except Exception`, ghi `last_web_error`, trả kết quả local.
Test: `test_fusion_falls_back_to_local_when_web_raises`.

**BUG-H4 — Rule-based bác bỏ câu đúng nguyên văn [ĐÃ SỬA]**
`negation_conflict` lấy hiệu đối xứng token của claim và **toàn bộ passage**. Một câu *khác* trong passage có "chưa/không" là claim đúng bị REFUTED. Challenge set: **16/60 (27%) câu nguyên văn bị REFUTED** dù nguồn đứng hạng 1. Rule-based là engine của chế độ demo trong app và là fallback của test.
Sửa: chỉ so phủ định với **câu khớp nhất** trong passage; so marker như từ độc lập, loại từ ghép ("không khí", "không gian", "không quân", "chưa kể").
Test: `test_rule_based_negation_elsewhere_in_passage_does_not_refute_verbatim_claim`, `test_rule_based_does_not_treat_khong_khi_as_negation` (BUG-H1, cùng gốc).

### Cao

**BUG-E1 — Guard cắt đôi số tiền kiểu Việt và hạ SUPPORTED đúng [ĐÃ SỬA]**
`_SENTENCES = re.compile(r"[.!?;]+")` tách "tăng **1.500** đồng/lít từ 15h chiều nay" thành "…tăng 1" + "500 đồng/lít từ 15h chiều nay" → câu chứa "xăng tăng" mất "đồng/lít" và "chiều nay" → hạ xuống NEI. Cùng câu nhưng "500" thì giữ SUPPORTED. Giá bán lẻ xăng luôn ≥ 1.000 đồng nên đây là ca phổ biến nhất của chính tính năng guard nhắm tới.
Sửa: chỉ tách câu khi dấu câu theo sau là khoảng trắng: `re.split(r"(?<=[.!?;])\s+", text)` (hoặc `(?<!\d)[.!?;]+(?!\d)`).
Test: `test_guard_keeps_support_with_vietnamese_thousand_separator`.

**BUG-F1 — Trích ngày đăng lấy nhầm đồng hồ "hôm nay" ở header [ĐÃ SỬA]**
Khi trang không có meta ngày đăng, `extract_published_at` lấy thẻ `<time>` **đầu tiên**, kể cả trong `<header>`. Bài 2023 bị gán ngày hôm nay → **vượt qua neo thời gian**, đúng lỗi mà neo thời gian sinh ra để chặn.
Sửa: không ghi `time_values` khi đang ở trong `header/nav/footer/aside` (parser đã có `_skip_depth`); ưu tiên `<time>` có `itemprop="datePublished"`/`pubdate` hoặc nằm trong `<article>`.
Test: `test_published_at_ignores_header_clock_and_uses_article_time`.

**BUG-E2 — Guard không hiểu phủ định của claim [ĐÃ SỬA]**
`_claim_direction("Giá xăng không tăng …") == "tăng"`. Verifier SUPPORTED sai cho "giá xăng **không** tăng" khi bằng chứng nói "tăng 300 đồng" vẫn lọt qua guard.
Sửa: nếu trước từ chỉ chiều có "không/chưa/chẳng/không hề" thì coi là chiều phủ định (đòi bằng chứng không nói chiều đó, hoặc trả None để không kiểm chiều).
Test: `test_claim_direction_respects_negation`, `test_guard_blocks_support_for_negated_claim_against_increase`.

**BUG-E3 — Guard không kiểm số liệu [ĐÃ SỬA]**
SUPPORTED sai khi claim "tăng 500 đồng" còn bằng chứng "tăng 300 đồng" vẫn lọt. Đổi số là dạng false positive phổ biến nhất của ViFactCheck.
Sửa: với SUPPORTED, chuẩn hóa số (bỏ dấu chấm hàng nghìn, thống nhất dấu thập phân) và hạ xuống NEI nếu một số trong claim (không phải năm) vắng mặt ở câu được trích **và** câu đó có số khác đi cùng cùng đơn vị.
Test: `test_guard_blocks_support_when_numbers_contradict`.

**BUG-A1 — Claim lịch sử có năm bị coi là "hiện tại" [ĐÃ SỬA]**
`_ABSOLUTE_DATE` chỉ bắt `dd/mm` và `ngày N`. "**Năm 2020**, tổng thống Mỹ là Donald Trump" → `current` (do chức danh nhiệm kỳ) → neo vào 365 ngày gần nhất, loại sạch bằng chứng năm 2020 → NEI oan. Tương tự "**tháng 3/2023**, Thủ tướng …".
Sửa: thêm `năm \d{4}`, `tháng \d{1,2}(/\d{4})?`, `\b\d{1,2}/\d{4}\b` vào mốc tuyệt đối.
Test: `test_recency_class_year_is_absolute_anchor`, `test_recency_class_month_year_is_absolute_anchor`.

**BUG-H2 / BUG-H3 — Rule-based so số quá thô [ĐÃ SỬA]**
H2: "1500" và "1.500" bị coi là mâu thuẫn. H3: bằng chứng không nhắc tới năm trong claim bị coi là bác bỏ (thiếu thông tin ≠ mâu thuẫn).
Sửa: chuẩn hóa số trước khi so; chỉ coi là mâu thuẫn khi bằng chứng có **số khác** ở cùng vị trí ngữ nghĩa (cùng đơn vị/cụm đứng trước).
Test: `test_rule_based_same_number_different_format_is_not_conflict`, `test_rule_based_missing_number_is_not_contradiction`.

**BUG-B1 — Neo thời gian không chặn bằng chứng "từ tương lai" [ĐÃ SỬA]**
Với `--as-of` trong quá khứ (backtest/đánh giá theo thời gian), bài đăng sau ngày tham chiếu vẫn được dùng → rò rỉ thông tin.
Sửa: loại `published > reference + 1 ngày` (dung sai múi giờ).
Test: `test_gate_rejects_evidence_published_after_reference_date`.

### Thấp

**BUG-C1** — `relevance` tách từ bằng khoảng trắng: "tăng." ≠ "tăng", "xăng," ≠ "xăng". Sửa: dùng `re.findall(r"\w+", …)` như guard.
**BUG-C2** — Nhận diện "claim về giá" bằng chuỗi con: "đồng" trong "hội đồng" bật cộng điểm bán lẻ. Sửa: so theo từ ("giá", "xăng", "dầu" là token), bỏ "đồng/tăng/giảm" khỏi bộ kích hoạt.
**BUG-C3** — Không gộp cùng bài khi URL khác `?utm_source`, `www.`, `/` cuối. Sửa: chuẩn hóa URL trước khi gộp.

## 3. Kết quả sơ bộ challenge set (engine rule_based — KHÔNG phải PhoBERT)

Chạy trong môi trường không có model nên chỉ đo được rule-based. Số liệu PhoBERT cần chạy trên máy có model (mục 4).

| Loại | Acc | Hit@k nguồn | Dự đoán |
|---|---|---|---|
| SUP_VERBATIM | 73,3% | 100% | SUP 44, REF 16 |
| SUP_FORMAT | 76,7% | 100% | SUP 46, REF 14 |
| REF_NUMBER | 100% | 100% | REF 60 |
| REF_DIRECTION | 35,0% | 100% | SUP 39, REF 21 |
| REF_NEGATION | 95,0% | 100% | REF 57, SUP 3 |
| NEI_PARTIAL | 0,0% | 100% | REF 39, SUP 21 |
| NEI_FICTIONAL | 55,0% | — | NEI 11, REF 5, SUP 4 |

Tổng: Accuracy 62,9%, Macro-F1 53,2%; **+guard: Macro-F1 66,2%**. Retrieval lấy được câu nguồn 100% (claim gần nguyên văn nên BM25 dễ), vì vậy mọi lỗi ở bảng trên là lỗi **verifier**, không phải retrieval.

## 4. Chạy đánh giá thật (PhoBERT)

```powershell
py -3.13 scripts/run_challenge_eval.py                      # 380 claim, ~4–6 phút CPU
py -3.13 scripts/run_challenge_eval.py --per-category 20    # nhanh
py -3.13 scripts/run_challenge_eval.py --engine rule_based  # đối chiếu
```

Kết quả nằm ở `outputs/challenge_eval/<engine>_<thời gian>/`: `report.md` (bảng + ví dụ lỗi), `summary.json`, `results.jsonl` (từng claim), `challenge_set.jsonl` (để chạy lại đúng bộ cũ bằng `--set`).

Cách đọc để biết sửa ở đâu:
- **Hit@k thấp** → sửa retrieval (BM25/rerank/top-k). **Hit@k cao mà Acc thấp** → sửa verifier.
- **REF_NUMBER / REF_DIRECTION / REF_NEGATION ra SUPPORTED** → verifier mù số liệu / chiều / phủ định — đây là false positive nguy hiểm nhất; cân nhắc tăng cường dữ liệu huấn luyện đúng các phép biến đổi này.
- **NEI_PARTIAL ra SUPPORTED** → verifier coi "đúng một phần" là đúng.
- **NEI_FICTIONAL ra REFUTED/SUPPORTED** → verifier suy diễn từ bài không liên quan; xem lại ngưỡng `decisive_min_confidence`.
- So **Acc vs Acc+guard** và dòng "Guard chặn X sai / hạ nhầm Y đúng" để quyết định có bật guard ở app hay không (BUG-I1).

## 5. Giới hạn của chính bộ test

- Challenge set là **in-distribution** (claim lấy từ kho) và biến đổi **tổng hợp**: đo được điểm yếu theo hiện tượng, không thay cho test split có nhãn người. Báo cáo luận văn vẫn lấy số chính từ test split (chạy một lần).
- Nhãn NEI theo giả định "kho đóng".
- Test đối kháng là deterministic, không chạm PhoBERT; hành vi riêng của PhoBERT chỉ đo qua `run_challenge_eval.py` và `test_metamorphic.py`.

## 6. Kết quả challenge set trên PhoBERT thật và các sửa đổi (2026-10-04)

### 6.1 Kết quả đo (RT-V2 balanced, 380 claim)

Accuracy 78,9% · Macro-F1 79,8% · +guard 81,9%. Hit@k = 100% mọi loại → mọi lỗi là lỗi verifier.

| Loại | Acc thô | Acc+guard | Ghi chú |
|---|---|---|---|
| SUP_VERBATIM | 93,3% | 93,3% | 4 lỗi, cả 4 có câu nguồn ở nửa sau passage |
| SUP_FORMAT | 96,7% | 95,0% | |
| REF_NUMBER | 95,0% | 91,7% | guard hạ nhầm vài REFUTED đúng |
| REF_DIRECTION | 48,3% | 45,0% | 46,7% bị SUPPORTED |
| REF_NEGATION | 63,3% | 60,0% | 36,7% bị SUPPORTED (nhiễu nhãn ~5–7%) |
| NEI_PARTIAL | 100% | 100% | |
| NEI_FICTIONAL | 10,0% | **100%** | thô: 50% SUPPORTED; guard chặn 18/18 |

### 6.2 Chẩn đoán gốc rễ

1. **Vị trí câu trong passage quyết định độ chính xác** (passage trung vị 600 ký tự, nên không phải do cắt 256 token). Câu liên quan ở đầu passage vs sau 200 ký tự: REF_DIRECTION 75% → 24%; SUP_VERBATIM 100% → 78%. Verifier bị nhiễu bởi các câu đứng trước.
2. **Verifier bỏ qua khác biệt nhỏ** (đổi chiều/phủ định) khi claim gần như trùng một câu nguồn.
3. **Claim bịa**: BM25 luôn trả top-k, verifier suy diễn từ bài không liên quan. Guard đã chặn được (chủ đề trọng tâm không có trong câu nào) nhưng chỉ khi được nối vào pipeline (BUG-I1).

### 6.3 Sửa đổi

| Thành phần | File | Tác dụng |
|---|---|---|
| Chọn câu bằng chứng | `src/evidence_focus.py`, tham số `evidence_view` (`passage` \| `focus_first` \| `focus_only`) | Đưa câu khớp claim nhất lên đầu/chỉ giữ câu đó. **Mặc định `passage`** vì chưa đo được tác động lên PhoBERT; cần A/B (6.5). |
| Luật cặp-tối-thiểu | `src/minimal_pair.py` | Claim ≈ một câu nguồn nhưng đổi số / chiều / phủ định → REFUTED; claim ≈ nguyên văn một câu nguồn → SUPPORTED. Xác định, không dùng mô hình. |
| Nối vào pipeline | `FactCheckingPipeline(safety_layers=True)`, `app.py` | Guard + cặp-tối-thiểu cho app. |
| Báo cáo challenge | `scripts/run_challenge_eval.py` | Thêm cột "+safety" và cờ `--evidence-view`. |
| Test | `tests/test_minimal_pair.py` (25 test) | Gồm các ca luật phải im lặng. |

### 6.4 Kết quả sau sửa — ĐỌC KỸ GIỚI HẠN

Phát lại (replay) kết quả PhoBERT đã có + luật mới (không gọi lại mô hình): Accuracy 81,8% → **99,5%** (REF_DIRECTION 45% → 98%, REF_NEGATION 60% → 100%, REF_NUMBER 92% → 100%, SUP_FORMAT 95% → 100%, SUP_VERBATIM 93% → 98%, NEI_* giữ 100%; 0 false-SUPPORTED).

**Con số 99,5% KHÔNG phải năng lực tổng quát.** Luật được thiết kế cho đúng họ biến đổi mà challenge set sinh ra, nên phần lớn là "trúng đề". Kiểm chứng ngoài tập (200+ câu sinh bằng cách khác, từ chính kho):

| Biến đổi | Phát hiện |
|---|---|
| Chèn "không" trước "có" / "được" (cấu trúc mới, từ vựng có trong luật) | 98% / 100% |
| cao hơn→thấp hơn, nhiều→ít | 100% |
| **Trái nghĩa NGOÀI từ vựng luật**: mở rộng→thu hẹp, đồng ý→phản đối, cho phép→cấm, an toàn→nguy hiểm | **0%** (luật im lặng, PhoBERT tự quyết) |
| Thay từ đồng nghĩa vô hại (và→cùng với) | 0% bác bỏ nhầm |
| Cùng câu y hệt | 0% bác bỏ nhầm |

Nghĩa là: luật **chắc chắn** với số liệu, tăng/giảm và phủ định có trong từ vựng; **không giúp gì** với trái nghĩa khác. Muốn phủ rộng cần tăng cường dữ liệu huấn luyện PhoBERT (chỉ dùng split train; giữ challenge set làm held-out). Bằng chứng về bác bỏ nhầm trên dữ liệu thật còn mỏng vì kho gần như không có cặp câu gần trùng.

Rủi ro đã biết khi bật trên dữ liệu thật: bài báo CŨ nói ngược với claim đúng hôm nay có thể kích hoạt REFUTED nếu bài mới không được truy xuất (với claim thời sự, cổng thời gian đã loại bài cũ; câu nguyên văn ở passage khác luôn thắng).

### 6.5 Việc cần làm trên máy bạn (A/B trước khi khóa)

```powershell
py -3.13 -m pytest tests/test_minimal_pair.py tests/test_adversarial_findings.py -q --basetemp=.pytest_tmp
py -3.13 scripts/run_challenge_eval.py --evidence-view passage       # đối chứng (số cũ + cột +safety)
py -3.13 scripts/run_challenge_eval.py --evidence-view focus_first
py -3.13 scripts/run_challenge_eval.py --evidence-view focus_only
```
So cột Acc theo từng loại giữa 3 view. Chọn view chỉ khi **không làm giảm SUP_VERBATIM/SUP_FORMAT/NEI_PARTIAL** và tăng REF_DIRECTION/REF_NEGATION; sau đó **bắt buộc** kiểm trên dev có nhãn người (không chỉ challenge set) trước khi đổi mặc định hay bật `safety_layers` cho script đánh giá e2e.

### 6.6 Kết quả đo thật sau sửa (PhoBERT RT-V2, challenge set 380 claim, 2026-10-04)

Accuracy / Macro-F1 theo cấu hình (cột đầu là **mô hình thuần**, không có luật nào):

| evidence_view | Thô | +guard | +guard+cặp-tối-thiểu |
|---|---|---|---|
| passage (cũ) | 78,9% / 79,8% | 81,9% (F1) | 99,1% (F1) |
| focus_first | 83,9% / 84,2% | 85,8% (F1) | 99,4% (F1) |
| **focus_only** | **91,6% / 90,6%** | 91,7% (F1) | 98,7% (F1) |

Theo loại, mô hình thuần (passage → focus_first → focus_only): REF_DIRECTION 48,3 → 68,3 → **93,3**; REF_NEGATION 63,3 → 68,3 → **88,3**; REF_NUMBER 95,0 → 95,0 → 98,3; SUP_VERBATIM 93,3 → 98,3 → 96,7; SUP_FORMAT 96,7 → 98,3 → 96,7; NEI_PARTIAL 100 mọi view; NEI_FICTIONAL 10 → 10 → 20 (guard đưa về 100).

Đọc kết quả:
- **Mức tăng của `focus_only` là của chính mô hình** (không dựa vào luật) nên có khả năng khái quát hơn các cột "+cặp-tối-thiểu". Hai cột cuối gần trần vì luật được viết cho đúng họ biến đổi này (xem 6.4); chênh 98,7 vs 99,4 giữa các view ở đó là nhiễu, không có ý nghĩa.
- Không có nhóm nào tụt đáng kể khi dùng `focus_only` (SUP_VERBATIM −1 claim so với focus_first, SUP_FORMAT như cũ).
- **Chưa đủ để đổi mặc định**: challenge set thiên vị cho `focus_only` (claim là câu đơn lấy từ chính kho). Trên dữ liệu thật claim có thể cần nhiều câu ngữ cảnh; phải kiểm trên dev có nhãn người.

### 6.7 Quyết định bằng dev có nhãn người

```powershell
py -3.13 scripts/ab_dev_end_to_end.py --limit 150      # chạy thử
py -3.13 scripts/ab_dev_end_to_end.py                   # đầy đủ trên dev.parquet
```
Chạy 3 view x 4 tầng (raw, +guard, +cặp-tối-thiểu, +guard+cặp-tối-thiểu) trên **dev** (script từ chối test split), in Macro-F1 từng nhãn và **khoảng tin cậy bootstrap ghép cặp của chênh lệch Macro-F1 so với cấu hình gốc** (dấu `*` = khác biệt có ý nghĩa). Quy tắc chốt: chỉ đổi mặc định sang cấu hình có Δ Macro-F1 ≥ 0 trên dev (CI không âm) **và** không làm giảm F1 SUPPORTED; test split chỉ chạy một lần sau khi đã chốt (`evaluate_local_end_to_end.py`).

### 6.8 Kết quả trên DEV có nhãn người (n=1080) — đảo ngược vài kết luận trên challenge set

Chạy `scripts/ab_dev_end_to_end.py` (PhoBERT RT-V2, dev.parquet). Δ = chênh Macro-F1 so với (passage, raw), bootstrap ghép cặp 95%.

| view | tầng | Acc | Macro-F1 | Δ [CI] |
|---|---|---|---|---|
| passage | raw | 71,3% | 70,7% | — |
| passage | +guard | 61,8% | 60,6% | **−10,2** [−12,8; −7,5] * |
| passage | +cặp-tối-thiểu | 71,4% | 70,9% | +0,1 [−0,2; +0,5] |
| focus_first | raw | 72,6% | 72,1% | +1,4 [−0,2; +2,9] |
| focus_only | raw | 64,9% | 64,5% | **−6,2** [−9,5; −3,2] * |

Kết luận (khác với challenge set):
1. **`focus_only` làm xấu đi trên dữ liệu thật** (F1 SUPPORTED 75,4 → 61,8): claim thật cần ngữ cảnh ngoài một câu. Thắng ở challenge set chỉ vì claim ở đó là câu đơn lấy từ kho. Loại bỏ làm mặc định (view vẫn còn để thử nghiệm).
2. **Guard có hại trên dev**: hạ nhầm 154 verdict đúng, chỉ chặn được 51 verdict sai. Guard được thiết kế cho claim thời sự nhánh web, nơi claim và bằng chứng dùng từ gần giống nhau; claim dev là diễn đạt lại nên bị coi là "lạc chủ đề". → `app.py` tắt guard mặc định; BUG-I1 chỉ còn là "có cờ để bật", không phải "nên bật".
3. **Luật cặp-tối-thiểu trung tính** (Δ +0,1, CI chứa 0): không gây hại khi claim là diễn đạt lại, và sửa các ca claim chỉ khác một yếu tố (6.4). An toàn để bật cho app.
4. **`focus_first` +1,4 chưa có ý nghĩa thống kê** trên toàn dev (trên 150 claim đầu +4,1 *, nhưng mẫu nhỏ). Không đổi mặc định.
5. **Lỗi chủ đạo trên dev là REFUTED bị đoán SUPPORTED: 108/353 (31%)**, rồi NEI bị đoán SUPPORTED/REFUTED (113/353). Đây là nơi còn nhiều dư địa nhất, không phải guard.
6. **Ensemble 3 view** (offline, vote đa số trên dự đoán dev đã lưu): Macro-F1 **+2,4** [+0,9; +3,8]; luật "SUPPORTED của passage bị REFUTED của focus_only phủ quyết" +1,8 [+0,3; +3,3]. Cả hai đều dương ở hai nửa dev. Các luật này được chọn trên dev (thử 5 biến thể) nên số thật có thể thấp hơn chút.

Đã thêm `evidence_view: ensemble` (trung bình xác suất của 3 view, một lần gọi mô hình cho toàn bộ) để đo trực tiếp, và `--views passage ensemble` làm mặc định của script A/B cùng quét độ phủ chủ đề của guard (g60/g40/g25) để xem có mức nào không hại. Chưa có số đo thật cho `ensemble` — chỉ khi dev xác nhận mới đổi mặc định.

### 6.9 Kết quả A/B dev lần 2 (n=1080) và quyết định cấu hình

| view | tầng | Acc | Macro-F1 | F1 SUP | F1 REF | F1 NEI | Δ vs (passage, raw) |
|---|---|---|---|---|---|---|---|
| passage | raw | 71,3% | 70,7% | 75,4 | 64,2 | 72,6 | — |
| passage | +cặp-tối-thiểu | 71,4% | 70,9% | 75,6 | 64,6 | 72,4 | +0,1 [−0,2; +0,5] |
| passage | +guard@60%+mp | 61,9% | 60,7% | 69,1 | 50,1 | 63,0 | −10,0 * |
| passage | +guard@40%+mp | 69,0% | 68,3% | 74,4 | 62,1 | 68,5 | −2,4 * |
| passage | +guard@25%+mp | 70,9% | 70,4% | 75,3 | 64,3 | 71,5 | −0,4 [−0,9; +0,2] |
| **ensemble** | raw | **73,8%** | **73,4%** | 77,6 | 67,6 | 74,9 | **+2,6 [+0,9; +4,2] *** |
| ensemble | +cặp-tối-thiểu | 73,8% | 73,4% | 77,7 | 67,7 | 74,8 | +2,6 [+0,9; +4,2] * |
| ensemble | +guard@40%+mp | 71,1% | 70,6% | 75,9 | 64,8 | 71,1 | −0,1 |
| ensemble | +guard@25%+mp | 73,2% | 72,8% | 77,1 | 67,5 | 73,9 | +2,1 * (thấp hơn ensemble raw) |

Guard theo độ phủ: 60% hạ nhầm 154/chặn đúng 51; 40% hạ nhầm 33/chặn 7; 25% hạ nhầm 6/chặn 1.

Quyết định:
- **`evidence_view: ensemble` thành mặc định** của cấu hình mới: tăng cả ba F1 theo nhãn (SUP +2,2; REF +3,4; NEI +2,3), khoảng tin cậy không chứa 0, khớp dự báo offline (+2,4). Chi phí: ~3 chuỗi/passage trong một lần gọi mô hình (độ trễ thực tế đo bằng `latency` của pipeline, chưa đo riêng).
- **`minimal_pair: true`**: trung tính trên dev, sửa các ca ở 6.4.
- **`guard: false`**: không cấu hình nào của guard vượt raw trên dev (ở 25% chỉ hòa/kém; chặn được gần như 0). Guard giữ lại cho nhánh web thời sự (`run_web_fact_check.py`) nơi nó được thiết kế.
- Ba khóa mới nằm trong `configs/config.yaml` nhưng `evaluate_local_end_to_end.py` bỏ qua chúng, trừ khi thêm `--use-final-config` — để baseline W4-02 vẫn tái lập được. Chạy cuối trên test **một lần**: `py -3.13 scripts/evaluate_local_end_to_end.py --use-final-config --metrics outputs/metrics/final_local_end_to_end_test.json --predictions outputs/predictions/final_local_end_to_end_test.csv`.

Giới hạn: cấu hình được chọn trên dev (thử ~10 tổ hợp) nên số trên test có thể thấp hơn chút; lỗi chủ đạo (REFUTED bị đoán SUPPORTED, NEI bị đoán quyết định) còn nguyên — cần dữ liệu huấn luyện chứ không phải luật hậu kiểm.

## 7. Trạng thái sửa lỗi (2026-10-11) — tất cả BUG-xx đã sửa

Mỗi lỗi đã sửa thì gỡ nhãn `xfail` khỏi test tương ứng (test giờ phải PASS) và thêm test hồi quy cho ca biên mà bản sửa phải giữ đúng (nhóm J trong `tests/test_adversarial_findings.py`, tên `test_fix_*`).

| Mã | File sửa | Cách sửa đã áp dụng | Ca biên được giữ (test `test_fix_*`) |
|---|---|---|---|
| I1 | `src/pipeline.py`, `src/system_builder.py` | Cờ `guard`/`minimal_pair` trong pipeline; giao diện + CLI dựng chung qua `system_builder` (local: guard tắt; web: guard bật) | `test_demo_app_defaults_guard_off_and_minimal_pair_on` |
| G1 | `src/input_guard.py` | Không coi là injection khi "bỏ qua" đứng sau không/được/đừng/chớ/hề/chẳng | Vẫn chặn "Hãy bỏ qua hướng dẫn kiểm chứng…" |
| D1 | `src/fusion_retriever.py` | Bắt mọi lỗi nhánh web, lùi về local, ghi `last_web_error` (giao diện hiển thị) | Lỗi web được ghi lại |
| H1/H4 | `src/fact_checker.py` | Phủ định chỉ so trên **câu khớp claim nhất**; bỏ từ ghép (không khí, hàng không, không gian…) | — |
| H2/H3 | `src/fact_checker.py` | Chuẩn hóa số (1.500 = 1500, 2,5 = 2.5); mâu thuẫn chỉ khi **thay số** (claim có số vắng ở nguồn VÀ câu nguồn có số khác) | — |
| E1 | `src/verdict_guard.py` | Không tách câu ở dấu chấm giữa hai chữ số | — |
| E2 | `src/verdict_guard.py` | "không/chưa tăng" không còn là khẳng định "tăng"; claim phủ định + nguồn khẳng định -> hạ NEI | Claim phủ định + nguồn cũng phủ định vẫn SUPPORTED |
| E3 | `src/verdict_guard.py` | Hạ SUPPORTED khi câu nguồn khớp chủ đề nhất mang số khác số trong claim | Nguồn thiếu năm của claim không bị hạ |
| F1 | `src/web_retriever.py` | Bỏ `<time>` nằm trong header/nav/footer/aside | Trang chỉ có đồng hồ header -> ngày "không rõ" (không phải hôm nay) |
| A1 | `src/query_enrichment.py` | "năm 2020", "tháng 3/2023", "3/2023" là mốc tuyệt đối | — |
| B1 | `src/temporal_gate.py` | Loại bằng chứng đăng sau ngày tham chiếu + 1 ngày; đếm riêng `last_dropped_future` | Lệch 1 ngày (múi giờ) vẫn giữ |
| C1 | `src/topical_rerank.py` | Tách từ bằng regex, bỏ dấu câu bám vào từ | — |
| C2 | `src/topical_rerank.py` | "Claim về giá" xét theo từ (giá/xăng/dầu) hoặc số + đơn vị tiền; "hội đồng" không còn kích hoạt | — |
| C3 | `src/topical_rerank.py` | `canonical_url`: bỏ utm_*/fbclid/gclid…, #fragment, www., "/" cuối | `?id=1` và `?id=2` vẫn là hai bài |

Ngoài danh sách đối kháng, đã sửa thêm:
- `scripts/run_golden_eval.py` văng UnicodeEncodeError trên mọi console không phải UTF-8 (trước đây chỉ xử lý Windows).
- Lỗi hash corpus/policy do Git đổi LF→CRLF trên Windows: thêm `.gitattributes` `eol=lf` cho các file có SHA-256 trong manifest. `scripts/check_release.py` nhận diện và gợi ý cách sửa.
- `PhoBERTFactChecker` dựng bằng `__new__` (trong test) thiếu `evidence_view`: thêm mặc định cấp lớp.

