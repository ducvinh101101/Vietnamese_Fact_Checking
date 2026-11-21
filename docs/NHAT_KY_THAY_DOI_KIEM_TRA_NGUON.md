# Nhật ký thay đổi – nhánh `feature/source-attribution-retrieval`

> Tổng hợp mọi thay đổi từ lúc tạo nhánh thử hướng mới (19/11/2026) đến 20/11/2026, kèm kết quả đo
> trước/sau. Pipeline RT-V2 cũ (`configs/config.yaml`) **không bị sửa**; hướng mới chạy song song.
> Chi tiết kỹ thuật đầy đủ: [SOURCE_ATTRIBUTION.md](SOURCE_ATTRIBUTION.md).

## Tóm tắt nhanh

| | Trước (pipeline RT-V2 cũ) | Sau (cấu hình mặc định hiện tại) | Hiệu quả |
|---|---:|---:|---|
| Bài toán | Phán thật / giả | **Có nguồn thực tế hay không** | Đổi hướng theo yêu cầu đề tài |
| Độ chính xác trung bình 5 nhóm (dev 1.252 claim) | 70,5% | **83,1%** | **+12,6 điểm** |
| Báo nhầm "có nguồn" (bịa nguồn) | 19,5% | **5,8%** | **giảm ~3,4 lần** |
| Precision "có nguồn" | 67,2% | **85,8%** | tốt hơn |
| Recall "có nguồn" | **86,7%** | 76,3% | **kém hơn** – đổi lại ít bịa nguồn |
| F1 "có nguồn" | 75,7 | **80,8** | tốt hơn |
| Tìm nguồn ngoài kho (web) | Không có | Tavily, 25 tên miền chính thống | mới |
| Model tự train | E2, RT-V1, RT-V2 | + **RT-V3**, **RR-V2** (train trên GPU máy nhóm) | phần NLP được giữ và mở rộng |

> **Tập test (chạy một lần, 1.259 claim, không dò lại ngưỡng):** pipeline cũ 70,0% → mặc định **83,3%**; báo nhầm
> 19,9% → **5,2%**; recall "có nguồn" 87,7% → 78,7%; F1 75,8 → **82,8**. Số test khớp số dev nên ngưỡng không bị quá khớp
> (chi tiết §5.6). Web mới thử trên vài claim minh họa, chưa có phép đo trên tập thực tế.

---

## 1. Dòng thời gian

| Thời điểm | Commit | Nội dung |
|---|---|---|
| 19/11/2026 | – | Tạo nhánh `feature/source-attribution-retrieval` từ `main` |
| 19/11/2026 23:54 | `be833d6` | Chuyển sang bài toán kiểm tra nguồn, viết lại retrieval, sửa web retriever, đánh giá vòng 1 |
| 20/11/2026 sáng | – | Cài PyTorch bản GPU, train thử reranker trên máy, phát hiện lỗi dữ liệu |
| 20/11/2026 13:51 | `a662b31` | Kiểm tra dữ liệu đầu vào, sửa cửa sổ câu, train **RT-V3** và **RR-V2**, đánh giá vòng 2 |
| 20/11/2026 14:08 | `ae14288` | Giao diện web mới (Streamlit) |

Nhánh đã được push lên GitHub (`origin/feature/source-attribution-retrieval`), chưa có Pull Request vào `main`.

---

## 2. Đổi bài toán: từ "thật/giả" sang "có nguồn hay không"

| Nhãn mới | Hiển thị | Khi nào |
|---|---|---|
| `SOURCE_FOUND` | Có nguồn xác nhận | Có đoạn từ nguồn chính thống nói cùng nội dung, verifier xác nhận, không lệch số/ngày |
| `SOURCE_CONFLICT` | Có nguồn nhưng lệch chi tiết | Nguồn nói cùng sự việc nhưng khác số liệu / ngày tháng, hoặc nói ngược lại |
| `NO_SOURCE` | Không tìm thấy nguồn | Không đoạn nào đủ liên quan và được xác nhận |

Mỗi kết quả kèm đoạn trích, URL, tên nguồn, số **nguồn độc lập** (tên miền) và chi tiết khớp / lệch / không được nhắc tới.

**Phần NLP và model cũ không bị bỏ:** PhoBERT RT-V2 và VnCoreNLP được tái sử dụng (RT-V2 là điểm khởi tạo của
cả RT-V3 và RR-V2), pipeline cũ vẫn chạy được trong app (chế độ "Kiểm chứng RT-V2 (cũ)").

---

## 3. Các thay đổi theo nhóm

### 3.1 Retrieval (tìm nguồn)

| # | Thay đổi | File | Vì sao |
|---|---|---|---|
| 1 | Cắt văn bản thành **cửa sổ 3 câu** (chồng lấn) thay cho passage 700 ký tự | `src/vi_text.py`, `src/hybrid_retriever.py` | Đoạn ngắn ít nhiễu khi chấm liên quan |
| 2 | **Cửa sổ cắt trên toàn bài** (`window_scope: document`) | `src/hybrid_retriever.py` | Trước đây cửa sổ không vượt ranh giới passage → Evidence nhiều câu không bao giờ nằm trọn một cửa sổ |
| 3 | BM25 mới: bỏ stopword (giữ từ phủ định), thêm bigram âm tiết | `src/vi_text.py`, `src/hybrid_retriever.py` | BM25 cũ khớp cả "của", "là"… |
| 4 | Sinh nhiều truy vấn (claim gốc + từ khóa + thực thể), gộp bằng RRF | `src/query_generation.py` | Dùng cho web; tắt cho kho cục bộ (làm giảm Hit@1) |
| 5 | Gộp kho cục bộ + web (`FusedRetriever`), web lỗi thì tự dùng kho cục bộ | `src/hybrid_retriever.py` | Tìm được tin ngoài kho ViFactCheck |
| 6 | Điểm liên quan **tuyệt đối** [0,1] + ngưỡng → có thể nói "không tìm thấy" | `src/source_reranker.py`, `src/source_attribution.py` | BM25 luôn trả top-k dù không liên quan |
| 7 | Reranker: lexical / RT-V3 relevance (mặc định) / RR-V2 / cross-encoder ngoài | `src/source_reranker.py` | Xếp hạng lại ứng viên |
| 8 | Kiểm tra khớp **số, ngày, tên riêng** (`check_facets`) | `src/source_attribution.py` | Bắt claim bị sửa số liệu |

### 3.2 Web retriever (Tavily) – sửa lỗi

| Lỗi cũ | Sửa |
|---|---|
| Chỉ đọc **1 trang** trong 10 kết quả Tavily | Đọc tối đa 6 trang, xếp hạng toàn cục |
| Lấy **3 đoạn đầu trang** (sapo, menu, chú thích ảnh) | Chọn đoạn theo độ liên quan; trích thân bài bằng trafilatura |
| Nhiều truy vấn bị nối liền → truy vấn 2 không bao giờ được đọc | Xen kẽ kết quả các truy vấn |
| Allowlist chỉ **3** tên miền | **25** tên miền: cơ quan nhà nước, TTXVN, báo chí chính thống, tingia.gov.vn |
| File `.env` không được đọc → không có `TAVILY_API_KEY` | `src/env_loader.py` nạp `.env` (không in, không log giá trị) |
| (21/11) Web lỗi tạm thời bị **im lặng**: app chỉ tra kho cục bộ, báo "Không tìm thấy nguồn" cho tin thật và **cache** kết quả sai | Trạng thái web có trong JSON (`retrieval.web_status`): tách `pages_unreachable` (tìm được bài nhưng không tải được trang), `rate_limited`, `budget_exhausted` khỏi "không có kết quả". App tự thử lại 1 lần với lỗi tạm thời, hiện cảnh báo nếu vẫn lỗi và **không cache** kết quả lỗi |
| (21/11) Không tải được `robots.txt` (mạng) bị coi như trang cấm tải | Tính là lỗi tải trang (thử lại được); trang bị `robots.txt` chặn thật vẫn bỏ qua |
| (21/11) 7 nguồn trong allowlist **luôn bị loại**: robots.txt của laodong.vn (charset `utf-8,gbk`), tienphong.vn (gzip không khai báo), qdnd.vn, vietnamplus.vn, nld.com.vn, plo.vn (robots.txt chuyển hướng) không đọc được → "cấm tải"; cand.com.vn đã chuyển sang cand.vn | Giải mã robots.txt chịu lỗi, đi theo chuyển hướng trong allowlist (RFC 9309), cache robots.txt theo host, thêm `cand.vn`. Còn lỗi: moh.gov.vn, www.sggp.org.vn (chứng chỉ SSL máy chủ thiếu) |

### 3.3 Model train mới (trên GPU máy nhóm: RTX 5060 Laptop 8 GB)

| Model | Là gì | Dữ liệu | Thời gian train | Kết quả trên dev |
|---|---|---|---|---|
| **RT-V3** | Verifier 3 nhãn (xác nhận / mâu thuẫn / chưa đủ) – RT-V2 train tiếp trên **cửa sổ câu** | `data/processed/verifier_windows_v3` (6.103 cặp; 95% đã đổi sang cửa sổ + 929 NEI "liên quan nhưng không phải nguồn") | ~10 phút | macro-F1 **74,3% (RT-V2) → 81,0%**; NEI recall 90% |
| **RR-V2** | Reranker liên quan / không liên quan, khởi tạo từ RT-V2 | `data/processed/reranker_v2` (20.485 cặp, đã lọc âm giả) | ~6 phút | AUC 0,997; gold đứng đầu 98,7% |
| RR-V1 | Bản đầu của reranker | – | ~6 phút | **Hỏng, đã xóa** (xem §4) |

Môi trường: cài `torch 2.14.0+cu130` vào `.venv` (bản cũ là CPU-only nên trước đây không train được trên máy).

### 3.4 Đánh giá và script

| File | Nội dung |
|---|---|
| `scripts/evaluate_source_attribution.py` | Bộ kiểm thử tự động 5 nhóm (A–E), dò ngưỡng, lưu/nạp kết quả chấm, so với pipeline cũ |
| `scripts/evaluate_source_attribution_realworld.py` | Chạy tập claim thực tế có/không web |
| `scripts/build_verifier_window_data.py` | Tạo dữ liệu RT-V3 |
| `scripts/build_reranker_training_data.py` | Tạo dữ liệu RR-V2 |
| `kaggle/finetune_phobert_reranker.py`, `kaggle/finetune_bi_encoder.py` | Script train reranker / bi-encoder (chạy được cả Kaggle lẫn máy nhóm) |
| `tests/test_source_attribution.py`, `tests/test_env_loader.py`, `tests/test_web_retriever.py` | Test mới: 124 test qua |

### 3.5 Giao diện web (`app.py`, `.streamlit/config.toml`)

* Phong cách báo chí: tiêu đề chữ có chân, nền sáng, màu kết luận xanh / hổ phách / đỏ **luôn kèm icon và chữ**.
* Chuyển chế độ "Kiểm tra nguồn" ↔ "Kiểm chứng RT-V2 (cũ)"; hiện trạng thái web đang bật hay chỉ kho cục bộ.
* Nút "Thử nhanh" với 3 claim mẫu; báo lỗi ngay dưới ô nhập khi chưa nhập gì.
* Thẻ kết luận (điểm khớp có thanh đo, số nguồn độc lập, số đoạn đã đánh giá) và thẻ nguồn (đoạn trích, chip "Khớp / Lệch", xác suất RT-V3, nút "Mở bài gốc").
* Kết quả không mất khi thao tác; liên kết chia sẻ `?q=<phát biểu>`; hiển thị gọn trên điện thoại.
* Nội dung lấy từ web được escape trước khi hiển thị.
* (21/11) Sửa lỗi: sau lần kiểm tra đầu, bấm kiểm tra câu mới lại chấm **câu cũ** (URL `?q=` do app tự ghi bị coi là
  link chia sẻ và ghi đè ô nhập). Test chạy app thật bằng Streamlit AppTest: `tests/test_streamlit_app_flow.py`.

---

## 4. Kiểm tra dữ liệu đầu vào – phát hiện và xử lý

| Phát hiện | Số liệu | Đã xử lý? | Ảnh hưởng sau khi xử lý |
|---|---|---|---|
| Cửa sổ câu không vượt ranh giới passage; 27% Evidence gồm nhiều câu | Câu gold nằm trọn 1 cửa sổ: 86,0% | ✅ cắt trên toàn bài | **92,8%** (+6,8 điểm trần retrieval) |
| Dữ liệu RR-V1: dương là câu gold ngắn (~190 ký tự), âm là cửa sổ dài (~430 ký tự) | Model học mẹo "ngắn = liên quan": AUC 0,998 nhưng chấm cửa sổ gold thật **0,006**, end-to-end chỉ 67% | ✅ dương = cửa sổ chứa gold | Độ dài cân bằng (491 / 453 ký tự) |
| Verifier RT-V2 train trên câu gold ngắn nhưng chạy trên cửa sổ 3 câu | Cùng loại lệch phân phối | ✅ train RT-V3 | macro-F1 74,3% → 81,0% |
| Âm giả trong dữ liệu reranker (cùng sự việc, báo khác đăng lại) | 11,7% âm khó phủ ≥50% Evidence gold | ✅ lọc bỏ | – |
| Dấu vết gán nhãn: độ trùng từ claim–Evidence SUPPORTED 0,89 / REFUTED 0,80 / NEI 0,67 | 6 đặc trưng bề mặt đoán đúng 65,6% nhãn (PhoBERT E2: 85,2%) | ❌ chưa | Gợi ý: thêm mẫu tương phản |
| Chú thích ảnh dính vào câu, 129 passage chưa chuẩn Unicode NFC | 324 chỗ; ảnh hưởng đo được +0,2 điểm | ❌ chưa (ưu tiên thấp) | – |
| Thiếu metadata | 81% thiếu ngày đăng, 100% thiếu tiêu đề | ❌ chưa | Chỉ ảnh hưởng hiển thị |
| Rò rỉ train / dev / test | 0 URL, 0 claim, 0 Evidence trùng | ✅ không có | – |

---

## 5. Kết quả – có hiệu quả hơn không?

### 5.1 Bộ kiểm thử (tự động tạo từ ViFactCheck)

| Nhóm | Cách tạo | Kết quả đúng |
|---|---|---|
| A | Claim SUPPORTED, kho đầy đủ | Có nguồn xác nhận |
| B | Claim REFUTED | Có nguồn nhưng lệch |
| C | Claim SUPPORTED, **bỏ bài gốc khỏi kho** | Không tìm thấy nguồn (đo việc bịa nguồn) |
| D | Claim NEI | Không tìm thấy nguồn |
| E | Claim SUPPORTED **bị sửa một con số** | Không phải "có nguồn xác nhận" |

### 5.2 Vòng 1 – đổi bài toán và retrieval (dev 300 claim, 19/11)

| Hệ thống | TB 5 nhóm | Báo nhầm "có nguồn" | P / R |
|---|---:|---:|---:|
| Cũ, rule-based | 29,0% | 85,0% | 28,2 / 100 |
| Cũ, RT-V2 | 68,7% | 21,7% | 55,2 / 80,0 |
| Mới, lexical, không verifier | 69,7% | 16,1% | 60,8 / 75,0 |
| Mới, lexical rerank + RT-V2 | 79,0% | **4,4%** | **84,0** / 70,0 |
| **Mới, RT-V2 + lexical 0,5 (mặc định vòng 1)** | **80,7%** | 7,2% | 78,0 / 76,7 |

**→ Có hiệu quả:** +12 điểm và báo nhầm giảm 3 lần so với pipeline cũ.

### 5.3 Vòng 2 – sửa dữ liệu, RT-V3, RR-V2 (dev 1.252 claim, 20/11)

Tập lớn hơn ~4 lần nên ít nhiễu hơn vòng 1.

| Reranker + verifier | A | B | C | D | E | TB 5 nhóm | Báo nhầm | P / R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cũ, RT-V2 | – | – | – | – | – | 70,5 | 19,5% | 67,2 / 86,7 | 75,7 |
| RT-V2 + RT-V2 (mặc định vòng 1, cửa sổ cấp bài) | 79 | 56 | 91 | 80 | 90 | 79,4 | 7,4% | 83,2 / 79,0 | 81,0 |
| RR-V2 + RT-V2 | 71 | 74 | 87 | 58 | 93 | 76,7 | 4,8% | 87,3 / 71,0 | 78,3 |
| RR-V2 + RT-V3 | 79 | 76 | 85 | 68 | 93 | 80,2 | 6,1% | 85,6 / 79,0 | **82,2** |
| **RT-V3 + RT-V3 (mặc định hiện tại)** | 76 | 72 | 88 | **86** | 93 | **83,1** | 5,8% | 85,8 / 76,3 | 80,8 |

**Retrieval** (nhóm A+B): Hit@5 BM25 cũ 87,8% → cửa sổ cấp bài **90,8%**; Hit@1 sau RR-V2 **86,0%**.

### 5.4 Đánh giá từng thay đổi

| Thay đổi | Hiệu quả hơn? | Bằng chứng |
|---|---|---|
| Đổi bài toán + ngưỡng tuyệt đối + kiểm tra số/ngày | ✅ **Rõ rệt** | Báo nhầm 21,7% → 7,2% (vòng 1) |
| BM25 mới, cửa sổ câu | ✅ Có | End-to-end tốt hơn passage dù Hit@1 thấp hơn chút |
| Multi-query trên kho cục bộ | ❌ Không | Hit@1 giảm (85,0% → 81,7%) → đã tắt, chỉ dùng cho web |
| Cửa sổ cắt trên toàn bài | ✅ Có (retrieval) | Trần 86,0% → 92,8%; Hit@5 → 90,8%; end-to-end gần như không đổi nếu verifier cũ |
| **RT-V3** (verifier train trên cửa sổ) | ✅ **Rõ nhất ở vòng 2** | TB 79,4% → **83,1%**; nhóm B 56% → 72%; NEI 80% → 86% |
| RR-V1 (bản đầu) | ❌ **Hỏng** | Lỗi dữ liệu lệch độ dài → end-to-end 67% → đã xóa |
| RR-V2 làm reranker | ⚖️ Tùy mục tiêu | Xếp hạng tốt hơn, F1 cao nhất (82,2) khi đi với RT-V3, nhưng nhận NEI kém (68%) → để làm tùy chọn |
| Web Tavily + sửa web retriever | ✅ Có (định tính) | Tin thật 2025 ngoài kho → "Có nguồn xác nhận" (vtv.vn, vietnamnet.vn); tin bịa → "Không tìm thấy nguồn" |
| Giao diện mới | ✅ Dễ đọc hơn | Không thay đổi kết quả mô hình |

### 5.5 Thử trên web thật (minh họa, không phải phép đo)

| Claim | Kết quả |
|---|---|
| Từ 1/7/2025 cả nước vận hành chính quyền địa phương hai cấp, còn 34 tỉnh, thành (tin thật, ngoài kho) | Có nguồn xác nhận – vtv.vn, vietnamnet.vn (điểm khớp 0,90) |
| Bộ Y tế khuyến cáo nước chanh ấm chữa khỏi ung thư gan (tin bịa) | Không tìm thấy nguồn |
| Giá xăng RON 95 giảm 500 đồng mỗi lít (lệch số) | Có nguồn nhưng lệch chi tiết – vnexpress.net, lệch "số 500" |

### 5.6 Tập test – chốt số liệu (20/11, chạy một lần)

Cùng cách tạo nhóm, seed và ngưỡng như dev; 1.259 claim (A 300, B 300, C 184, D 300, E 175).

| Pipeline | A | B | C | D | E | TB 5 nhóm | Báo nhầm | P / R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cũ, RT-V2 | 88 | 53 | 66 | 69 | 75 | 70,0 | 19,9% | 66,8 / 87,7 | 75,8 |
| Cũ nhưng thay verifier bằng RT-V3 | 74 | 64 | 89 | 84 | 93 | 80,8 | 6,1% | 84,7 / 73,7 | 78,8 |
| **RT-V3 + RT-V3 (mặc định)** | 79 | 72 | 89 | 83 | 94 | **83,3** | **5,2%** | 87,4 / 78,7 | **82,8** |

* Test khớp dev (83,3% / 83,1%) → kết quả đáng tin hơn con số dev.
* Phần lớn cải thiện đến từ **RT-V3** (pipeline cũ + RT-V3 đã đạt 80,8%); retrieval mới thêm +2,5 điểm TB, +5 điểm recall.
* Lệnh: `python scripts/evaluate_source_attribution.py --split test --limit 1500 --verifier --legacy-baseline`
  (dòng "Cũ, RT-V2" chạy với config trỏ verifier về `models/rt_v2_balanced/best_model`).

---

## 6. Cấu hình mặc định hiện tại (`configs/source_attribution.yaml`)

| Mục | Giá trị |
|---|---|
| Cửa sổ | 3 câu, bước 1, ≤700 ký tự, cắt trên toàn bài |
| Web | Bật (cần `TAVILY_API_KEY` trong `.env`), trọng số 1,5, 2 truy vấn/claim |
| Reranker | RT-V3 relevance + 0,5 điểm lexical, 20 ứng viên |
| Verifier | `models/rt_v3_windows/best_model` |
| Ngưỡng | relevance 0,7 · support 0,8 · conflict 0,5 |

---

## 7. Việc còn lại

| Việc | Ưu tiên | Ghi chú |
|---|---|---|
| ~~Chạy tập test một lần để chốt số~~ | Xong (20/11) | §5.6 – không dò ngưỡng trên test nữa |
| ~~Gán nhãn ~200–300 claim thực tế, đo web~~ | Xong (21/11) | 300 claim; có web 49,3% (không web 23,7%), báo nhầm "có nguồn" 0%, recall tin thật ~32% – xem SOURCE_ATTRIBUTION.md §5.4 |
| Phân tích lỗi recall trên tập thực tế | Cao | Tách: Tavily không trả bài gốc / dưới ngưỡng liên quan / facet lệch; không dò ngưỡng trên tập đã đo |
| Tạo Pull Request vào `main` sau khi nhóm/thầy xem | Cao | Nhánh đã push; model mới (~1 GB) lưu qua Git LFS |
| Giảm dấu vết gán nhãn (mẫu tương phản) | Trung bình | Xem §4 |
| Train bi-encoder BE-V1 | Trung bình | Script đã có |
| Làm sạch chú thích ảnh, chuẩn NFC, bổ sung ngày/tiêu đề | Thấp | |
| Test `test_w3_07_versioned_corpus_is_integrity_checked` lỗi | Thấp | Có từ trước nhánh: Git đổi xuống dòng sang CRLF (`core.autocrlf=true`) làm sai hash corpus |
