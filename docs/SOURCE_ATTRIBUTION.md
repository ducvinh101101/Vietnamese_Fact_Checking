# Kiểm tra nguồn (Source Attribution) – định hướng mới của đề tài

> Nhánh: `feature/source-attribution-retrieval`. Pipeline RT-V2 cũ (`configs/config.yaml`)
> **giữ nguyên**; pipeline mới chạy song song qua `configs/source_attribution.yaml`.

## 1. Bài toán

Thay vì phán **thật/giả**, hệ thống trả lời: *phát biểu người dùng nhập có nguồn
ngoài thực tế (báo chí chính thống, cơ quan nhà nước) nói cùng nội dung hay không?*

| Nhãn | Hiển thị | Điều kiện |
|---|---|---|
| `SOURCE_FOUND` | Có nguồn xác nhận | ≥1 đoạn liên quan đủ cao, verifier xác nhận, không lệch số/ngày |
| `SOURCE_CONFLICT` | Có nguồn liên quan nhưng lệch chi tiết | đoạn liên quan nhưng khác số liệu/ngày tháng, hoặc verifier đánh giá mâu thuẫn |
| `NO_SOURCE` | Không tìm thấy nguồn | không đoạn nào vượt ngưỡng liên quan/xác nhận |

Kèm theo: các đoạn trích dẫn (URL, tên nguồn, ngày), số **nguồn độc lập** (tên miền),
và chi tiết khớp / lệch / không được nhắc tới cho từng đoạn.

## 2. Phần NLP và model đã train vẫn được dùng

| Thành phần | Vai trò trong pipeline mới |
|---|---|
| PhoBERT **RT-V2** (đã train) | Điểm khởi tạo cho RT-V3 và RR-V2; vẫn là verifier của pipeline cũ. |
| PhoBERT **RT-V3** (train mới, §5.3) | RT-V2 fine-tune tiếp trên cửa sổ câu. **Verifier mặc định** (SUPPORTED→xác nhận, REFUTED→mâu thuẫn, NEI→không đủ) **và reranker mặc định** (P(SUP)+P(REF), trộn 0,5 điểm lexical). |
| **VnCoreNLP** | Tách từ cho PhoBERT (verifier, reranker, bi-encoder). Một instance dùng chung mỗi tiến trình (`shared_vncorenlp`). |
| Claim decomposition, content-risk, E1 | Giữ nguyên. |
| PhoBERT **RR-V2** (train mới, §5.3) | Cross-encoder liên quan/không liên quan, khởi tạo từ RT-V2. Tùy chọn (xếp hạng tốt hơn, nhận NEI kém hơn). |
| BE-V1 (chưa train) | `kaggle/finetune_bi_encoder.py`, dense retrieval. |

## 3. Kiến trúc

```
claim
 → vi_text: chuẩn hóa, tách câu, rút số / ngày / tên riêng
 → query_generation: claim gốc + truy vấn từ khóa/thực thể
 → HybridSourceRetriever (kho cục bộ): cửa sổ 3 câu cắt trên TOÀN BÀI, BM25 bỏ stopword + bigram âm tiết, (+dense), RRF
   WebRetriever (Tavily, allowlist 25 tên miền, 2 truy vấn, đọc ≤6 trang, chọn đoạn theo độ liên quan)
   FusedRetriever: gộp local + web bằng RRF (web lỗi → chỉ dùng local)
 → reranker: lexical | RT-V3 relevance + lexical (mặc định) | RR-V2 tự train | cross-encoder ngoài
 → ngưỡng liên quan tuyệt đối  ⟶ nếu không đoạn nào qua: NO_SOURCE
 → RT-V3 verifier + kiểm tra số/ngày/tên riêng (check_facets)
 → SOURCE_FOUND / SOURCE_CONFLICT / NO_SOURCE + citation
```

| File | Nội dung |
|---|---|
| `src/vi_text.py` | Tách câu, cửa sổ câu, token BM25, rút số/ngày/tên riêng |
| `src/query_generation.py` | Sinh nhiều truy vấn |
| `src/hybrid_retriever.py` | `SparseBM25`, `HybridSourceRetriever`, `FusedRetriever`, RRF |
| `src/source_reranker.py` | `LexicalSourceScorer`, `VerifierRelevanceScorer`, `CrossEncoderReranker` |
| `src/env_loader.py` | Nạp `TAVILY_API_KEY` từ `.env` (không ghi đè biến môi trường có sẵn) |
| `src/source_attribution.py` | Pipeline, `check_facets`, nhãn, JSON `source-attribution/v1` |
| `src/source_attribution_factory.py` | Dựng pipeline từ config |
| `src/web_retriever.py` | **Sửa lỗi** (xem §4) |
| `app.py` | Thêm chế độ "Kiểm tra nguồn" (mặc định); chế độ RT-V2 cũ vẫn còn |

## 4. Các lỗi retrieval đã sửa

1. **Web retriever chỉ đọc 1 trang**: với `top_k=3` và 3 đoạn/trang, vòng lặp dừng sau trang đầu
   trong 10 kết quả Tavily. Nay đọc tối đa `max_pages` trang và xếp hạng toàn cục.
2. **Web retriever lấy 3 đoạn ĐẦU trang** (sapo/menu/chú thích ảnh). Nay chọn đoạn theo độ liên quan
   với claim; tùy chọn dùng trafilatura để chỉ lấy thân bài.
3. **Không có cách nói "không tìm thấy"**: BM25 luôn trả top-k với điểm dương (trùng "của", "là"…).
   Nay có điểm liên quan tuyệt đối [0,1] và ngưỡng chọn trên dev.
4. **Tokenizer BM25** không bỏ stopword, không có từ ghép. Nay bỏ stopword (giữ từ phủ định) và thêm
   bigram âm tiết (xấp xỉ tách từ, không cần Java).
5. **Allowlist chỉ 3 tên miền** → 25 tên miền theo tầng (nhà nước, TTXVN, báo chí chính thống, tingia.gov.vn).
6. **VnCoreNLP khởi tạo hai lần** trong một tiến trình làm lỗi JVM → dùng instance chung.
7. **Cửa sổ câu không vượt ranh giới passage** (lỗi xử lý dữ liệu, xem §5.3): kho chia sẵn passage ≤700 ký tự;
   Evidence nhiều câu nằm vắt qua hai passage không bao giờ vào trọn một cửa sổ. Nay `window_scope: document`
   nối các passage cùng bài rồi mới cắt.

## 5. Đánh giá

### 5.1 Tập kiểm thử tự động từ ViFactCheck (`scripts/evaluate_source_attribution.py`)

| Nhóm | Cách tạo | Kỳ vọng |
|---|---|---|
| A in_corpus | claim SUPPORTED, kho đầy đủ | SOURCE_FOUND |
| B refuted | claim REFUTED | SOURCE_CONFLICT |
| C leave_gold_out | claim SUPPORTED, **bỏ bài gốc khỏi kho** | NO_SOURCE (cận trên báo nhầm) |
| D nei | claim NEI | NO_SOURCE |
| E perturbed | claim SUPPORTED bị đổi một con số | không phải SOURCE_FOUND |

Nhóm C và E là nhóm quan trọng nhất với đề tài mới: chúng đo việc hệ thống **không bịa ra nguồn**.

### 5.2 Kết quả dev vòng 1 (300 claim, 60/nhóm, seed 42) – trước khi sửa dữ liệu

> Số liệu vòng 1 giữ lại để đối chiếu. Cấu hình mặc định hiện tại và số liệu trên tập lớn hơn: **§5.3**.

Ngưỡng được dò trên chính tập dev này nên số liệu là **lạc quan**; cần xác nhận trên test (một lần)
và trên tập thực tế §5.4.

**Retrieval mức đoạn** (Hit@k: có đoạn chứa ≥80% âm tiết của câu Evidence gold, nhóm A+B, n=120;
trần của kho = 87,5% vì một số câu gold không có nguyên văn trong kho):

| Retriever | Hit@1 | Hit@3 | Hit@5 |
|---|---:|---:|---:|
| BM25 cũ (passage 700 ký tự) | 84,2% | 87,5% | 87,5% |
| Tokenizer mới, passage, 1 truy vấn | 85,0% | 87,5% | 87,5% |
| Tokenizer mới, passage, multi-query | 81,7% | 86,7% | 86,7% |
| Tokenizer mới, cửa sổ 3 câu | 81,7% | 85,0% | 86,7% |

→ Trong kho đóng ViFactCheck, retrieval **đã bão hòa** (BM25 đạt trần ở Hit@3). Multi-query làm giảm
điểm vì claim ViFactCheck được viết gần nguyên văn bài gốc, nên tắt cho kho cục bộ (vẫn bật cho web).
Cửa sổ câu thấp hơn ~3 điểm Hit@1 nhưng end-to-end (không verifier, ngưỡng dò trên dev) lại tốt hơn passage:
passage 68,7% · cửa sổ 3 câu 69,7% · cửa sổ 2 câu 70,7%, vì đoạn ngắn ít nhiễu hơn khi chấm liên quan.
Config đang dùng cửa sổ 3 câu (mọi số có verifier bên dưới đo với 3 câu); cửa sổ 2 câu cần đo lại kèm verifier
trước khi đổi.

**End-to-end kiểm tra nguồn** (độ chính xác từng nhóm):

| Hệ thống | A | B | C | D | E | TB 5 nhóm | Báo nhầm "có nguồn" | P / R "có nguồn" |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Cũ, rule-based (BM25 → luật) | 100 | 0 | 43,3 | 1,7 | 0 | 29,0 | 85,0% | 28,2 / 100 |
| Cũ, RT-V2 (BM25 top-3 → rank policy) | 80,0 | 60,0 | 66,7 | 68,3 | 68,3 | 68,7 | 21,7% | 55,2 / 80,0 |
| Mới, lexical, không verifier | 75,0 | 30,0 | 100 | 63,3 | 80,0 | 69,7 | 16,1% | 60,8 / 75,0 |
| Mới, lexical rerank + RT-V2 | 70,0 | 55,0 | 96,7 | 83,3 | 90,0 | 79,0 | **4,4%** | **84,0** / 70,0 |
| Mới, RT-V2 làm reranker (thuần) + RT-V2 | 76,7 | 66,7 | 53,3 | 70,0 | 85,0 | 70,3 | 11,7% | 68,7 / 76,7 |
| **Mới, RT-V2 + lexical (blend 0,5) + RT-V2 — mặc định** | 76,7 | 55,0 | 93,3 | 91,7 | 86,7 | **80,7** | 7,2% | 78,0 / 76,7 |

Ngưỡng của mỗi dòng "Mới" là bộ tốt nhất khi dò trên lưới (relevance 0,35–0,95; support 0,4–0,9).
Cấu hình mặc định: `reranker.model: verifier`, `lexical_blend: 0.5`, `candidate_k: 20`,
ngưỡng relevance 0,8 / support 0,4 / conflict 0,5. Tốc độ trên CPU: lexical ~0,9 s/claim, reranker RT-V2 ~3 s/claim
(chưa tính thời gian gọi web). Kết quả chấm được lưu ở `outputs/assessments/*.pkl` (không commit) để dò lại
ngưỡng bằng `--load-assessments` mà không cần chạy lại model.

Nhận xét:
* Pipeline cũ **bịa nguồn**: khi bỏ bài gốc khỏi kho (C), RT-V2 cũ vẫn trả SUPPORTED/REFUTED 33% số claim;
  với claim bị sửa số (E) vẫn nói "có nguồn" 32%.
* Cấu hình mặc định tăng độ chính xác trung bình 12 điểm (68,7% → 80,7%) và giảm báo nhầm "có nguồn" 3 lần
  (21,7% → 7,2%), đổi lại recall nhóm A giảm (80,0% → 76,7%).
* **RT-V2 thuần làm reranker kém**: nó coi bài khác cùng chủ đề là "liên quan", nên ở nhóm C (bỏ bài gốc) báo nhầm
  có nguồn hoặc nguồn mâu thuẫn 47% số claim. Trộn điểm lexical (blend 0,5) giữ được tín hiệu khớp chi tiết.
* Lexical + RT-V2 có báo nhầm thấp nhất (4,4%) và nhanh gấp ~3 lần: phù hợp khi cần độ chặt hoặc chạy trên máy yếu.
* Chênh lệch 1–2 điểm giữa các dòng "Mới" nằm trong nhiễu (60 claim/nhóm, ngưỡng dò trên chính dev).
  Reranker tự train (RR-V1) là hướng chính để tăng recall nhóm A và B.

**Kiểm tra nhanh trên web thật** (Tavily, cấu hình mặc định, 2 claim, chỉ minh họa, không phải phép đo):

| Claim | Kết quả |
|---|---|
| Từ 1/7/2025 vận hành chính quyền địa phương hai cấp, còn 34 tỉnh, thành (tin thật, ngoài kho ViFactCheck) | `SOURCE_FOUND`, nguồn vtv.vn, vov.vn |
| Bộ Y tế khuyến cáo nước chanh ấm chữa khỏi ung thư gan (tin bịa) | `NO_SOURCE` |

Với reranker lexical, tin thật bị trả `NO_SOURCE` (điểm 0,64, ngay dưới ngưỡng) do câu chữ khác bài báo; với RT-V2 thuần,
tin bịa bị trả `SOURCE_CONFLICT` vì có các bài bác bỏ "chanh trị bách bệnh".

### 5.3 Kiểm tra dữ liệu đầu vào và vòng 2 (RT-V3, RR-V2)

**Kiểm tra dữ liệu** (kho 5.844 passage / 1.041 bài; ViFactCheck train 5.076, dev 1.080, test 1.076):

| Phát hiện | Số liệu | Xử lý |
|---|---|---|
| Cửa sổ câu không vượt ranh giới passage; 27% Evidence gồm nhiều câu | gold nằm trọn 1 cửa sổ: **86,0%** (cắt trên toàn bài: **92,8%**) | `window_scope: document` |
| Dữ liệu train RR-V1 bản đầu: dương là câu gold ngắn, âm là cửa sổ dài | trung vị 190 vs 430 ký tự → model học "ngắn = liên quan"; chấm cửa sổ gold thật **0,006**, end-to-end 67% | dương = cửa sổ chứa gold (cân bằng 491 vs 453 ký tự) |
| Verifier RT-V2 train trên câu gold ngắn nhưng chạy trên cửa sổ 3 câu | cùng loại lệch phân phối | RT-V3 train trên cửa sổ |
| Âm giả trong dữ liệu reranker (cùng sự việc do báo khác đăng lại) | 11,7% âm khó phủ ≥50% Evidence gold | loại âm phủ ≥0,5 |
| Dấu vết gán nhãn: độ trùng từ claim–Evidence SUPPORTED 0,89 / REFUTED 0,80 / NEI 0,67 | 6 đặc trưng bề mặt (không hiểu nghĩa) đoán đúng **65,6%** nhãn dev; E2 PhoBERT trên gold 85,2% | chưa xử lý (gợi ý: mẫu tương phản) |
| Chú thích ảnh dính vào câu ("- Ảnh: VGP/…"), 129 passage chưa chuẩn NFC | 324 chỗ; ảnh hưởng đo được +0,2 điểm trần | chưa xử lý (ưu tiên thấp) |
| Thiếu metadata | 81% thiếu ngày đăng, 100% thiếu tiêu đề | chưa xử lý (chỉ ảnh hưởng hiển thị) |
| Rò rỉ train/dev/test | 0 URL, 0 claim, 0 Evidence trùng | – |

**Model train mới** (GPU cục bộ RTX 5060 Laptop 8 GB, `torch 2.14.0+cu130`; khởi tạo từ RT-V2; checkpoint chọn trên dev):

| Model | Dữ liệu | Thời gian | Dev |
|---|---|---|---|
| RT-V3 verifier | `scripts/build_verifier_window_data.py` → `data/processed/verifier_windows_v3`: cặp RT-V2 thay Evidence bằng cửa sổ chứa nó (95%), thêm 929 NEI "liên quan nhưng không phải nguồn" (trọng số 0,5) | ~10 phút | macro-F1 trên dev dạng cửa sổ **74,3% (RT-V2) → 81,0%** |
| RR-V2 reranker | `scripts/build_reranker_training_data.py` → `data/processed/reranker_v2`: 20.485 cặp train, cửa sổ cấp bài, đã lọc âm giả | ~6 phút | AUC 0,997, gold đứng đầu 98,7% |

```powershell
python scripts/build_verifier_window_data.py
python kaggle/finetune_phobert_retrieval_v1.py --data-dir data/processed/verifier_windows_v3 `
  --model-dir models/rt_v2_balanced/best_model --output-dir models/rt_v3_windows `
  --vncorenlp-dir models/vncorenlp --experiment RT-V3 --epochs 2
python scripts/build_reranker_training_data.py
python kaggle/finetune_phobert_reranker.py --data-dir data/processed/reranker_v2 `
  --model-dir models/rt_v2_balanced/best_model --output-dir models/phobert_reranker_v2 `
  --vncorenlp-dir models/vncorenlp --epochs 2
```

**End-to-end vòng 2**: dev 1.252 claim (A 300, B 300, C 187, D 300, E 165), cửa sổ cấp bài, ngưỡng dò trên dev
(`outputs/metrics/source_attribution_dev1500_*.json`):

| Reranker + verifier | A | B | C | D | E | TB 5 nhóm | Báo nhầm "có nguồn" | P / R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cũ, RT-V2 (BM25 top-3 → rank policy) | – | – | – | – | – | 70,5 | 19,5% | 67,2 / 86,7 | 75,7 |
| RT-V2 blend + RT-V2 | 79 | 56 | 91 | 80 | 90 | 79,4 | 7,4% | 83,2 / 79,0 | 81,0 |
| RR-V2 + RT-V2 | 71 | 74 | 87 | 58 | 93 | 76,7 | 4,8% | 87,3 / 71,0 | 78,3 |
| RR-V2 + RT-V3 | 79 | 76 | 85 | 68 | 93 | 80,2 | 6,1% | 85,6 / 79,0 | **82,2** |
| **RT-V3 blend + RT-V3 (mặc định)** | 76 | 72 | 88 | **86** | 93 | **83,1** | 5,8% | 85,8 / 76,3 | 80,8 |

Retrieval (nhóm A+B, n=600): Hit@5 BM25 cũ 87,8% → cửa sổ cấp bài 90,8%; Hit@1 sau rerank: RR-V2 86,0%, RT-V2 blend 83,5%.

Nhận xét:
* **RT-V3 là thay đổi có ích nhất** (+3,7 điểm TB so với RT-V2, cùng retrieval): nhóm B 56% → 72%, NEI 80% → 86%.
  Ngay với ngưỡng cũ chưa dò lại, RT-V3 đã đạt 82,4% và báo nhầm 4,8%.
* **RR-V2 xếp hạng tốt hơn nhưng chấm cao cả đoạn cùng chủ đề của claim NEI** (nhóm D thấp nhất). RR-V2 + RT-V3 có
  F1 "có nguồn" cao nhất; chọn nó nếu ưu tiên recall hơn việc nhận ra claim thiếu thông tin.
* Cấu hình mặc định: `window_scope: document`, `reranker.model: verifier` (blend 0,5), verifier RT-V3,
  ngưỡng relevance 0,7 / support 0,8 / conflict 0,5.
* Web thật (2 claim minh họa ở §5.2, cấu hình mới): tin thật → `SOURCE_FOUND` (vtv.vn, vietnamnet.vn);
  tin bịa → `NO_SOURCE`.

Bi-encoder (chưa train): `kaggle/finetune_bi_encoder.py` dùng `reranker_v2`, sau đó đặt
`local.dense: {model: models/bi_encoder_v1, segment: true}` rồi dò lại ngưỡng.

### 5.4 Tập thực tế (cần nhóm gán nhãn)

ViFactCheck không đo được năng lực tìm nguồn **ngoài kho**. Cần ~200–300 claim theo mẫu
`data/evaluation/source_attribution_realworld_template.csv`, gồm các nhóm `recent_real` (tin sau 2023, có URL),
`paraphrase`, `fabricated`, `perturbed`, rồi chạy:

```powershell
$env:TAVILY_API_KEY = "..."
python scripts/evaluate_source_attribution_realworld.py data/evaluation/source_attribution_realworld_v1.csv
python scripts/evaluate_source_attribution_realworld.py data/evaluation/source_attribution_realworld_v1.csv --no-web
```

So sánh có/không web là con số chính để báo cáo phần retrieval mở.

## 6. Chạy thử

```powershell
pip install -r requirements.txt; pip install trafilatura   # torch/transformers/py_vncorenlp như README
$env:TAVILY_API_KEY = "..."      # tùy chọn; thiếu thì chỉ tra kho cục bộ
streamlit run app.py             # chọn chế độ "Kiểm tra nguồn"
```

## 7. Giới hạn

* Ngưỡng và checkpoint chọn trên dev đã xem → số dev lạc quan; test chưa chạy.
* Dấu vết gán nhãn của ViFactCheck (§5.3): một phần điểm verifier có thể đến từ độ trùng từ, không phải hiểu nghĩa.
* Web search mới chỉ được chạy thật trên vài claim minh họa; chưa có phép đo trên tập thực tế (§5.4).
* Nhóm C chỉ là cận trên của báo nhầm: kho có thể có bài khác đưa cùng tin.
* `check_facets` dùng heuristic (regex số/ngày, chữ hoa cho tên riêng); NER VnCoreNLP có thể thay thế.
