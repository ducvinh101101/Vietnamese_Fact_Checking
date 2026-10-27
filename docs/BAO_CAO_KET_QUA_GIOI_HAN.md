# Báo cáo kết quả, ablation và giới hạn khoa học (W6-02)

Ngày: 2026-09-29, cập nhật 2026-10-11 (kết quả cấu hình cuối — xem [báo cáo tổng kết](BAO_CAO_TONG_KET.md)). Phạm vi: tổng hợp toàn bộ thí nghiệm đã chạy, các quyết định thiết kế có căn cứ số liệu, phân tích lỗi và giới hạn. Đây là bản báo cáo phương pháp/kết quả cho phần của Vinh; phần retrieval/UI/release do Quang bổ sung.

Nguyên tắc xuyên suốt: **mọi con số được ghi kèm điều kiện đo**. Không trộn metric khác giao thức, không trình bày số dev như accuracy thực tế, không coi proxy URL-level là bằng chứng passage đủ entail.

---

## 1. Bài toán và kiến trúc

Hệ thống nhận một phát biểu (hoặc cả bài viết) tiếng Việt và trả verdict ba nhãn **SUPPORTED / REFUTED / NOT_ENOUGH_INFO** kèm đoạn bằng chứng được trích dẫn, dựa trên bằng chứng truy xuất được — không phán đúng/sai tuyệt đối.

Hai nhánh cố ý tách biệt:

- **Nhánh RAG (quyết định verdict):** claim → truy xuất bằng chứng → verifier phân loại quan hệ claim–bằng chứng → chính sách tổng hợp → verdict + citation.
- **Nhánh content-risk (chỉ cảnh báo):** title + body → điểm rủi ro văn phong/nguồn. **Không** tham gia quyết định verdict. Ràng buộc này được cưỡng chế bằng kiến trúc (trường `content_risk` tách khỏi `ArticleAggregation`, có test chứng minh verdict không đổi khi bật/tắt).

---

## 2. Bảng kết quả chính

### 2.1 Verifier trên bằng chứng vàng (oracle) — tách khỏi RAG

| Thí nghiệm | Cấu hình | Macro-F1 test | Quyết định |
|---|---|---:|---|
| E1 | TF-IDF word+char + Linear SVM | 40,15% | Baseline |
| E2 | PhoBERT-base fine-tune | **81,07%** | Model tốt nhất, đang dùng |
| E7 | PhoBERT, max_length 256, batch variant | 80,25% | Giữ E2 (dev 84,18% < 85,01%) |

E2 hơn E1 **40,92 điểm** — khoảng cách giữa "đếm trùng lặp từ vựng" và "hiểu quan hệ ngữ nghĩa". Đây là bằng chứng định lượng cho việc cần một verifier học entailment, không thể thay bằng độ tương đồng.

### 2.2 End-to-end (tự đi tìm bằng chứng) — năng lực hệ thống thật

| Phép đo | Accuracy | Macro-F1 | Điều kiện |
|---|---:|---:|---|
| Oracle E2 (gold evidence), test | 81,13% | 81,07% | Trần verifier |
| BM25-local E2E, test 1.076 | 64,96% | 62,94% | E11 rank-aware policy |
| BM25-local E2E, test (baseline W4-02 max-conf) | 61,43% | 59,49% | Trước rank policy |
| Reranked-local E2E, test (W4-05) | 70,54% | 69,92% | E2 + rerank metadata W3-08 |
| **Cấu hình cuối, test (2026-10-04, chạy một lần)** | **72,77%** | **72,31%** | RT-V2 + ensemble 3 view + cặp-tối-thiểu, BM25; +12,8 [+10,0; +15,6] so với W4-02 |

**Khoảng cách oracle → end-to-end ban đầu là 18,13 điểm Macro-F1** (còn ~8,8 điểm với cấu hình cuối). Đây là phát hiện trung tâm: retrieval gần như luôn tìm đúng bài (URL Recall@3 = 98,14%), nên khoảng cách nằm ở bước *đọc hiểu đoạn đã truy xuất*, không ở bước tìm.

### 2.3 Nhánh content-risk — baseline, không phải bộ phát hiện tin giả

| Thí nghiệm | Cấu hình | Macro-F1 OOF | ROC-AUC | Quyết định |
|---|---|---:|---:|---|
| E9 | TF-IDF/SVM, title+body | **77,27%** | 88,21% | Baseline triển khai |
| E10 | PhoBERT, title+body | 48,59% | 70,20% | Không chọn (kém E9) |

E10 kém E9 gần 29 điểm. Lý do: nội dung ngữ nghĩa không phân biệt được thật/giả nếu không đối chiếu bằng chứng; TF-IDF thắng vì khai thác tín hiệu bề mặt của nguồn trên một tập mà **domain trùng hoàn toàn với nhãn** (VFND: mỗi domain một nhãn, 221 bài). E9 recall lớp FAKE chỉ 0,61 — bỏ lọt ~4/10 bài giả. Kết luận đúng: E9 là baseline cho thấy **vì sao content-only không đủ và cần RAG**, không phải bộ phát hiện tin giả để triển khai.

---

## 3. Ablation — các quyết định có căn cứ

### 3.1 Retrieval: giữ BM25

| Retriever | Dev Recall@5 | Ghi chú |
|---|---:|---|
| BM25 | 98,52% | Giữ |
| Dense (E5-small + FAISS) | 95,65% | Kém hơn, bỏ |
| Hybrid RRF | 98,43% | Không vượt BM25, bỏ |

Quy tắc đã áp: chỉ giữ dense/hybrid nếu vượt BM25 theo Recall@5 và latency phù hợp demo. Không đạt → giữ BM25. BM25 test: Recall@3 98,14%, Recall@5 98,98%, MRR@5 0,9671, p95 81,20 ms.

### 3.2 Chính sách quyết định: bốn lớp, chọn trên dev

| Lớp | Chọn trên | Hiệu quả |
|---|---|---|
| E6 temperature scaling | dev gold OOF | ECE 3,74% → 2,91%; threshold quyết đoán tối ưu = 0,0 |
| E11 rank-aware (`rank_bias=1`, `threshold=0,6`) | dev end-to-end | Macro-F1 +3,45, citation URL-match +11,06 điểm trên test |
| AGG-V1 logistic | dev OOF theo URL | dev 70,19% (fit trên logits E2) |
| RT-V1 fine-tune | — | xem 3.3 |

Cảnh báo khoa học đã ghi nhận: cả bốn lớp chọn trên **cùng một tập dev 1.080 claim**, nên độ tin cậy của số dev giảm dần theo từng lớp. Số dev là "hướng đi đúng", không phải "chất lượng đạt được".

### 3.3 RT-V1: sửa train/serve mismatch

Fine-tune tiếp E2 trên gold train + 487 cặp AI-silver (passage BM25 truy xuất, không phải evidence annotation), trọng số silver 0,5.

| Cấu hình dev | Accuracy | Macro-F1 | F1 REFUTED | Tỷ lệ NEI |
|---|---:|---:|---:|---:|
| E2 nguyên bản | 64,35% | 62,66% | 52,50% | 30,28% |
| RT-V1 silver, ngưỡng 0,5 | **72,31%** | **71,35%** | 61,40% | 40,93% |

So khớp từng claim: sửa đúng 140, làm sai 54, ròng **+86**. Chủ yếu sửa tật khẳng định bừa của E2 (71 claim NEI từng bị gọi SUPPORTED).

**Hai giới hạn chưa đóng:**
1. Chưa có đối chứng gold-only, nên chưa tách được cải thiện do nhãn silver với do huấn luyện thêm. (W5-04)
2. Tỷ lệ NEI tăng từ 30% lên 41% — một phần cải thiện có thể đến từ việc abstain nhiều hơn, không phải hiểu hơn. Cần RT-V2 balanced để kiểm chứng.

RT-V1 **chưa được khóa vào config**; `config.yaml` vẫn dùng E2 + AGG-V1.

### 3.4 RT-V2 balanced — kiểm chứng giả thuyết lệch NEI (2026-09-30)

Đóng gói lại bundle cân bằng nhãn: giữ toàn bộ 5.075 cặp gold, chỉ thêm 126 cặp silver (tối đa 42/nhãn) thay vì 487, để giảm lệch 82,3% NEI. Fine-tune tiếp E2 với cùng seed và trọng số silver 0,5.

Đo trên **dev bằng chứng vàng** (cùng loại đo với E2 oracle, KHÔNG phải end-to-end):

| Model | Train rows | Epochs | Dev Macro-F1 | F1 REFUTED | NEI recall |
|---|---:|---:|---:|---:|---:|
| E2 (trước fine-tune) | — | — | 85,01% | 77,9% | — |
| RT-V1 silver | 5.562 | 10 | 83,41% | 77,96% | 0,924 |
| **RT-V2 balanced** | 5.201 | 5 | **85,08%** | **80,29%** | 0,909 |

Nhận định:
- Trên gold evidence, **RT-V2 vượt RT-V1** ở cả Macro-F1 (85,08 vs 83,41) và F1 REFUTED (80,29 vs 77,96), với NEI recall thấp hơn (0,909 vs 0,924). Kết quả xác nhận **giả thuyết lệch NEI**: giảm tỷ lệ silver-NEI cải thiện nhánh REFUTED — nhánh quan trọng nhất của hệ thống chống tin sai.
- RT-V2 ≈ E2 trên gold evidence (85,08 ≈ 85,01), phù hợp với việc fine-tune không thêm gì khi đã có bằng chứng vàng; giá trị của nó nằm ở nhánh **end-to-end** (passage truy xuất), chưa đo.
- **Confound cần ghi rõ:** RT-V1 chạy 10 epoch, RT-V2 chỉ 5 epoch, nên chênh lệch chưa hoàn toàn quy về việc cân bằng nhãn.
- **Vẫn thiếu gold-only control** (chỉ 5.075 gold, không silver). Chưa tách được cải thiện do nhãn với do huấn luyện thêm; đây là lượt còn phải chạy.

**End-to-end dev (BM25→verifier, tự đi tìm bằng chứng) — phép đo quyết định:**

| Cấu hình dev, ngưỡng 0,5 | Accuracy | Macro-F1 | F1 REFUTED | Tỷ lệ trả NEI |
|---|---:|---:|---:|---:|
| E2 nguyên bản | 64,35% | 62,66% | 52,50% | 30,28% |
| RT-V1 silver | **72,31%** | **71,35%** | 61,40% | 40,93% |
| RT-V2 balanced | 71,30% | 70,75% | **64,23%** | **28,52%** |

Đây là kết quả quan trọng nhất của cả nhánh RT:
- RT-V2 và RT-V1 **gần như hòa về Macro-F1** (70,75 vs 71,35; chênh 0,6 điểm), nhưng RT-V2 **hơn hẳn ở F1 REFUTED** (+2,83 điểm) và **giảm mạnh lệch NEI** (28,52% vs 40,93%, còn thấp hơn cả E2).
- Nghĩa là RT-V2 đạt độ chính xác tương đương **mà không phải nhờ abstain nhiều hơn** — accuracy của nó "thật" hơn. RT-V1 mua điểm một phần bằng cách trả NEI nhiều; RT-V2 dám kết luận hơn và bắt phủ định tốt hơn.
- Với một hệ thống chống tin sai, REFUTED là nhãn đắt nhất, nên **khuyến nghị chọn RT-V2 balanced** làm checkpoint khóa vào runtime (W5-05).
- Citation URL-match tổng của RT-V2 là 68,52% (cao hơn RT-V1 do trả NEI ít hơn); vẫn là proxy URL-level, cần audit passage-level (W5-03a).

**Vẫn còn thiếu:** lượt gold-only control (để tách đóng góp của nhãn silver) và confound epoch (RT-V1 10 vs RT-V2 5). Cả hai số trên là dev, đã dùng chọn ngưỡng, nên chưa phải bằng chứng độc lập; mục tiêu 80% thực tế vẫn cần bộ gold mới (C6/E13).

Artifact: `kaggle/rt_v1_silver/rt_v1_metrics.json`, `kaggle/rt_v2_balanced/finetune_metrics.json`, `outputs/metrics/rt_v2_balanced_e2e_dev.json`.

### 3.5 Reranked-local end-to-end — rerank nâng verdict (W4-05, test, 2026-10-01)

Thay BM25 thuần bằng retriever rerank W3-08 (BM25 lấy 20 ứng viên → lọc nguồn/thời gian → rerank theo overlap + authority → khử trùng → top-3), giữ verifier E2 và rank policy. Đo **một lần trên test** 1.076 mẫu.

| Cấu hình test (verifier E2) | Accuracy | Macro-F1 | F1 SUP | F1 REFUTED | F1 NEI |
|---|---:|---:|---:|---:|---:|
| BM25-local (E11 rank-aware) | 64,96% | 62,94% | 71,69% | 49,81% | 67,32% |
| **Reranked-local (W3-08)** | **70,54%** | **69,92%** | 76,20% | **62,21%** | 71,34% |

Rerank nâng **+6,98 điểm Macro-F1** và **+12,40 điểm F1 REFUTED** so với BM25 thuần trên cùng verifier — bước lọc nguồn/thời gian và rerank theo authority thực sự đưa passage tốt hơn lên top, không chỉ cải thiện chỉ số retrieval. Đây là bằng chứng rằng chất lượng ứng viên là một nút thắt thật, bổ sung cho kết luận về verifier ở mục 4.

Lưu ý: verifier ở đây là **E2** (chưa phải RT-V2 đã khóa runtime). REFUTED recall vẫn chỉ 0,522 — rerank cải thiện nhưng chưa giải quyết nhóm phủ định khó. Con số end-state đầy đủ (RT-V2 + rerank) cần **một** lượt test sạch, chưa chạy. Citation URL-match 55,39% (proxy URL-level).

Artifact: `outputs/metrics/reranked_e2e_test.json`.

### 3.6 External validity theo nguồn (W5-03b)

Chia kết quả reranked-local test theo domain nguồn của bằng chứng vàng, để xem model có phụ thuộc nguồn không.

| Nguồn | N | Macro-F1 | F1 REFUTED |
|---|---:|---:|---:|
| baotintuc.vn | 102 | 76,38% | 76,67% |
| baochinhphu.vn | 184 | 74,19% | 71,15% |
| thanhnien.vn | 91 | 71,70% | 61,22% |
| tuoitre.vn | 128 | 70,71% | 59,38% |
| dantri.com.vn | 127 | 69,04% | 60,32% |
| nld.com.vn | 116 | 68,17% | 53,33% |
| vnexpress.net | 114 | 67,55% | 54,55% |
| plo.vn | 95 | 67,55% | 61,29% |
| tienphong.vn | 119 | 61,93% | 57,14% |

Chênh lệch Macro-F1 giữa các nguồn khoảng 14 điểm (61,9%–76,4%) — **model tương đối ổn định, không phụ thuộc nặng vào một nguồn**. Nguồn cơ quan nhà nước (baochinhphu, baotintuc) cao hơn báo tổng hợp, có thể do văn phong chuẩn và số liệu rõ. F1 REFUTED dao động mạnh hơn (53%–77%), tái khẳng định REFUTED là nhãn khó nhất ở mọi nguồn.

Phần **temporal** bị bỏ qua vì file predictions không có cột ngày; để đo theo thời gian cần thêm `published_at` vào predictions (metadata đã có trong corpus v2). Đây vẫn là dữ liệu ViFactCheck, không phải held-out thời sự ngoài đời.

Artifact: `outputs/metrics/w5_03b_source_temporal.json`.

---

## 4. Phân tích lỗi

### 4.1 Nút thắt không nằm ở retrieval

Trên 299 lỗi còn lại của RT-V1 (dev):

| Nhóm triage | Số lỗi | Tỷ trọng |
|---|---:|---:|
| nei_decision | 195 | 65,2% |
| verifier_with_gold_url | 97 | 32,4% |
| retrieval_url_miss | **7** | **2,3%** |

Chỉ 7/299 lỗi do retrieval không lấy được URL vàng. **175/299 lỗi có nhãn vàng REFUTED** — nhóm quan trọng nhất của một hệ thống chống tin sai.

### 4.2 Nhóm REFUTED → NEI không sửa được bằng ngưỡng

98 claim REFUTED bị trả NEI: URL vàng nằm trong top-k **96,9%**, confidence NEI trung bình **0,87**. Model tự tin chọn NEI khi bằng chứng bác bỏ đã có sẵn. Đây là vấn đề dữ liệu huấn luyện và khả năng bắt mâu thuẫn của verifier, không phải policy hay retrieval. Hạ ngưỡng quyết đoán không chạm tới nhóm này.

### 4.3 Citation URL-match: không hồi quy sau RT-V1

Con số gộp giảm 67,50% → 57,59% ban đầu bị hiểu nhầm là đánh đổi. Phân rã lại: mọi dự đoán NEI đều không sinh citation nhưng vẫn nằm trong mẫu số. Tính riêng trên các kết luận **quyết đoán**, citation URL-match là **96,81% → 97,49%** — tăng nhẹ, không hồi quy. Bài học: báo cáo tách coverage và citation-match trên phần quyết đoán, không gộp một số.

---

## 5. Giới hạn khoa học

1. **Kho evidence là thế giới đóng.** 5.845 passage dựng từ chính ViFactCheck, nên bằng chứng cho mỗi claim gần như luôn tồn tại — đó là lý do Recall@3 98%. Ngoài đời phần lớn claim sẽ không có bằng chứng trong kho; khi nối web, mọi con số sẽ tụt, và đó là bình thường.

2. **Relevance và citation hiện là proxy URL-level.** URL đúng không chứng minh passage đủ để entail/refute claim. Audit passage-level thủ công 50 citation (W5-03a) chưa chạy.

3. **NEI mang hai nghĩa.** Trong dataset NEI là một nhãn sự thật; trong hệ thống NEI cũng là hành vi từ chối. Gộp vào một nhãn khiến accuracy "thưởng" cho việc abstain đúng lúc. Nên báo cáo kèm coverage và accuracy trên phần đã kết luận.

4. **Chưa có phép đo độc lập.** Tập test đã bị xem nhiều lần (phân tích lỗi, so sánh). Mục tiêu ≥80% thực tế chưa đạt và chưa đo được; cần bộ gold mới ≥300 claim, hai reviewer độc lập, khóa SHA-256 trước khi chạy (W5-03/C6/E13).

5. **Web/fusion đã hợp nhất nhưng chưa đo.** Fusion RRF local+web, neo thời gian và gộp URL đã chạy trong giao diện và CLI (`src/system_builder.py`), có test giả lập web và golden test. Chưa có tập có nhãn cho claim thời sự nên tầng hybrid end-to-end **chưa có số đo định lượng**.

6. **Bốn lớp policy chồng trên cùng một tập dev** (xem 3.2) — rủi ro overfitting dev, đã ghi nhận.

---

## 6. Phần đã hoàn thành và phần còn lại

**Đã có bằng chứng số:** E1, E2, E6, E7, E9, E10, BM25/dense/RRF retrieval, rank-aware policy, AGG-V1, RT-V1, phân tích lỗi W3-04, phân rã citation. Pipeline end-to-end local chạy được và đã đo.

**Đã đóng sau 2026-09-29:** khóa RT-V2 (W5-05); đo reranked-local (W4-05); phân tích theo nguồn (W5-03b); challenge set + 20 lỗi đối kháng đã sửa; chọn ensemble/cặp-tối-thiểu trên dev; chạy test một lần cho cấu hình cuối (72,31%); hợp nhất web vào giao diện; release check; demo W4-04; bundle hard negative RT-V3.

**Chưa đóng (cần người/GPU — [hướng dẫn](HUONG_DAN_VIEC_CON_LAI.md)):** đối chứng gold-only (W5-04), phân xử/spot-check nhãn silver (W5-06), audit citation mức đoạn (W5-03a), huấn luyện RT-V3, bộ gold thực tế (C6/E13).

**Kết luận trung thực:** giá trị nghiên cứu của dự án nằm ở việc **định lượng khoảng cách oracle → end-to-end (18 điểm) và truy ra nguyên nhân là verifier/dữ liệu chứ không phải retrieval**, cùng kỷ luật đo tách bạch. Con số tốt nhất hiện có (cấu hình cuối, test Macro-F1 72,31%) là so sánh tương đối trên test đã dùng nhiều lần, chưa phải bằng chứng độc lập, và chưa đạt mục tiêu 80% ngoài thực tế.
