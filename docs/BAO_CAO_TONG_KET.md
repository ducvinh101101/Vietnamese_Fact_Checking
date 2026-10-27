# Báo cáo tổng kết — Hệ thống kiểm chứng thông tin tiếng Việt (RAG)

Ngày: 2026-10-11. Tài liệu tổng hợp để báo cáo: sản phẩm làm được gì, đo được bao nhiêu, quyết định nào dựa trên số liệu nào, và còn thiếu gì. Chi tiết từng thí nghiệm: [báo cáo kết quả & giới hạn](BAO_CAO_KET_QUA_GIOI_HAN.md), [báo cáo lỗi & challenge set](BAO_CAO_LOI_TU_TEST_DOI_KHANG.md).

> **Đọc trước:** mọi số dưới đây đo trên ViFactCheck. Test split (1.076 claim) đã được dùng cho nhiều lượt trước đó, nên chỉ nên đọc là **so sánh tương đối giữa các cấu hình**, không phải độ chính xác ngoài đời. Mục tiêu ≥ 80% ngoài thực tế **chưa được đo** (xem § 7).

---

## 1. Sản phẩm

Người dùng nhập một phát biểu tiếng Việt. Hệ thống trả về một trong ba nhãn **SUPPORTED / REFUTED / NOT_ENOUGH_INFO**, kèm đoạn bằng chứng được trích dẫn và đường dẫn tới nguồn.

```
claim ─► kiểm tra đầu vào (chặn prompt-injection)
      ─► truy xuất bằng chứng
           • chế độ "kho local": BM25 trên 5.845 đoạn ViFactCheck (đã đánh giá)
           • chế độ "local + web": BM25 W3-08 + Tavily (33 nguồn allowlist) ─RRF─► neo thời gian ─► gộp URL/xếp chủ đề
      ─► verifier PhoBERT RT-V2: chấm 3 cách dựng bằng chứng, lấy trung bình xác suất (ensemble)
      ─► chính sách quyết định theo hạng (rank-aware)
      ─► luật cặp-tối-thiểu: claim trùng gần nguyên văn nguồn nhưng khác số/chiều/phủ định -> REFUTED;
         trùng nguyên văn -> SUPPORTED
      ─► [guard hậu kiểm — chỉ bật ở nhánh web]
      ─► verdict + citation (JSON contract w3-03/v1)
```

| Thành phần | Vị trí |
|---|---|
| Giao diện | `app.py` — `py -3.13 -m streamlit run app.py` (chọn chế độ ở thanh bên, có ví dụ nhanh) |
| CLI | `scripts/run_web_fact_check.py --claim "..." [--local-only]` |
| Dựng hệ thống (dùng chung UI/CLI) | `src/system_builder.py` |
| Cấu hình đã khóa | `configs/config.yaml` |
| Kiểm tra máy trước khi demo | `scripts/check_release.py [--smoke]` |
| Demo 6 ca có kỳ vọng (W4-04) | `scripts/run_demo_cases.py [--with-web]` → `outputs/demo/demo_cases.md` |

## 2. Dữ liệu và giao thức đo

- ViFactCheck 7.232 mẫu, chia **theo URL** (không rò rỉ bài giữa các split): train 5.076 / dev 1.080 / test 1.076; nhãn cân bằng.
- Kho bằng chứng: 5.845 đoạn từ 1.041 bài; corpus v2 có metadata nguồn/thời gian và SHA-256 trong manifest.
- **Quy tắc chọn cấu hình:** mọi lựa chọn (checkpoint, cách dựng bằng chứng, lớp hậu kiểm) đều quyết định trên **dev có nhãn người**; test chỉ chạy **một lần** cho cấu hình cuối (2026-10-04, `--use-final-config`).
- So sánh hai cấu hình dùng **bootstrap ghép cặp theo claim** (2.000 lượt), báo khoảng tin cậy 95% của chênh lệch Macro-F1.

## 3. Kết quả chính

### 3.1 End-to-end trên test (1.076 claim, hệ thống tự tìm bằng chứng)

| Cấu hình | Verifier | Retrieval | Accuracy | Macro-F1 | Δ so với cuối [CI 95%] |
|---|---|---|---:|---:|---|
| W4-02 baseline | E2 | BM25 | 61,4% | 59,5% | −12,8 [−15,6; −10,0] |
| E11 chính sách theo hạng | E2 | BM25 | 65,0% | 62,9% | −9,4 [−12,0; −6,9] |
| W4-05 rerank metadata | E2 | BM25 + W3-08 | 70,5% | 69,9% | −2,4 [−4,7; −0,1] |
| **Cấu hình cuối** | **RT-V2 + ensemble + cặp-tối-thiểu** | BM25 | **72,8%** | **72,3%** | — |

So với baseline W4-02, cấu hình cuối sửa đúng 177 claim và làm sai 55 claim (ròng +122). Nguồn: `outputs/metrics/final_vs_baselines_test.json`, tái lập bằng `py -3.13 scripts/compare_final_vs_baselines.py`.

Chú ý: so với W4-05 là so **hai thay đổi một lúc** (verifier khác và retriever khác), nên +2,4 không quy được cho riêng thành phần nào.

**F1 từng nhãn (cấu hình cuối):** SUPPORTED 76,5% · REFUTED 66,2% · NOT_ENOUGH_INFO 74,2%.

**Ma trận nhầm lẫn** (hàng = nhãn đúng, cột = dự đoán):

| | SUPPORTED | REFUTED | NEI |
|---|---:|---:|---:|
| **SUPPORTED** (368) | 312 | 21 | 35 |
| **REFUTED** (356) | 88 | 206 | 62 |
| **NEI** (352) | 48 | 39 | 265 |

**Trích dẫn:** 95,4% verdict quyết đoán trích đúng bài gốc (URL-level). Tỷ lệ tính trên toàn bộ claim (63,3%) thấp hơn vì NEI không có trích dẫn theo thiết kế.

**Độ trễ:** p50 1,55 s, p95 2,0 s mỗi claim trên CPU. Ensemble chạy mô hình 3 lần nên chậm khoảng gấp đôi W4-02 (0,69 s).

**Theo nguồn (test):** Macro-F1 dao động 65,8% (tienphong) – 82,1% (thanhnien); F1 REFUTED dao động 55,7% – 78,1%. Không có nguồn nào sụp. Nguồn: `outputs/metrics/final_source_breakdown_test.json`.

### 3.2 Verifier trên bằng chứng vàng (trần của verifier)

E1 TF-IDF + SVM đạt 40,15%, E2 PhoBERT đạt 81,07% Macro-F1 test. Khoảng cách oracle → end-to-end còn khoảng 9 điểm. Retrieval tìm đúng bài 98,1% (URL Recall@3), nên phần mất chủ yếu nằm ở bước đọc hiểu đoạn đã tìm.

### 3.3 Các quyết định chọn trên dev (n = 1.080), đều so với RT-V2 dùng nguyên passage

| Thay đổi | Δ Macro-F1 dev [CI 95%] | Quyết định |
|---|---|---|
| Ensemble 3 cách dựng bằng chứng | **+2,6 [+0,9; +4,2]** | **Bật** (`evidence_view: ensemble`) |
| Câu khớp nhất đứng đầu (`focus_first`) | +1,4 (CI chứa 0) | Không chọn |
| Chỉ câu khớp nhất (`focus_only`) | −6,2 | Không chọn |
| Luật cặp-tối-thiểu | +0,1 (trung tính) | **Bật**: không hại số tổng, sửa đúng các ca đổi số/chiều/phủ định |
| Guard hậu kiểm, ngưỡng phủ 60% / 40% / 25% | −10,0 / −2,4 / −0,4 | **Tắt** ở chế độ local. Hạ nhầm 154 verdict đúng để chặn 51 verdict sai (ngưỡng 60%) |

Bài học phương pháp: trên challenge set tổng hợp (380 claim), `focus_only` thắng lớn (90,6% so với 79,8%), nhưng trên dev có nhãn người nó lại tệ hơn. Challenge set sinh từ câu đơn trong kho nên thiên vị cách dựng này. Vì vậy quyết định cuối luôn dựa trên dev, không dựa trên challenge set.

## 4. Độ vững và kiểm thử

- **Kiểm thử:** khoảng 300 test tự động, chạy không cần GPU (rule-based và giả lập verifier). Gồm test đối kháng theo thành phần, metamorphic, contract JSON, giao diện (Streamlit AppTest), dựng hệ thống, sinh hard negative và toàn vẹn dữ liệu (SHA-256). Chạy: `py -3.13 -m pytest -q --basetemp=.pytest_tmp`.
- **20 lỗi tìm bằng test đối kháng đều đã sửa và có test hồi quy**, chi tiết ở [báo cáo lỗi § 7](BAO_CAO_LOI_TU_TEST_DOI_KHANG.md). Các lỗi nghiêm trọng gồm:
  - chặn nhầm tin thật là prompt-injection;
  - nhánh web lỗi làm sập cả pipeline;
  - engine rule-based bác bỏ câu đúng nguyên văn;
  - trích ngày đăng lấy nhầm đồng hồ ở header trang, làm bài cũ vượt qua neo thời gian;
  - rò rỉ bài đăng "từ tương lai" khi backtest.
- **Bảo vệ đầu vào và đầu ra:**
  - chặn chỉ dẫn can thiệp ("bỏ qua mọi hướng dẫn…");
  - verdict quyết đoán luôn có trích dẫn hợp lệ thuộc đúng lượt truy xuất;
  - NEI không bao giờ kèm trích dẫn;
  - web chỉ nhận 33 host trong allowlist (HTTPS, tôn trọng robots.txt).

## 5. Chế độ web (claim thời sự)

Các claim như "giá xăng tăng từ chiều nay" hay "tổng thống X hiện nay" cần dữ liệu mới. Chế độ "local + web" xử lý theo bốn bước:

1. Chèn ngày tham chiếu vào truy vấn web.
2. Trộn kết quả local và web bằng RRF.
3. **Neo thời gian:** claim theo ngày chỉ nhận bằng chứng ≤ 10 ngày, claim "hiện tại" ≤ 365 ngày. Bài không rõ ngày đăng, hoặc đăng sau ngày tham chiếu, bị loại.
4. Gộp mỗi bài một đoạn, rồi bật guard hậu kiểm.

Không có bằng chứng đủ mới thì hệ thống trả NEI, thay vì SUPPORTED dựa trên bài cũ.

**Giới hạn:** chế độ này **chưa có phép đo định lượng trên tập có nhãn**. Hiện chỉ có golden test xác định (`tests/golden`) và test với web giả lập. Không trình bày số 72,3% như năng lực của chế độ web.

## 6. Giới hạn khoa học

1. **Thế giới đóng.** Kho bằng chứng dựng từ chính ViFactCheck nên gần như claim nào cũng có bài nguồn. Ngoài đời, số đo sẽ thấp hơn.
2. **Test đã xem nhiều lần.** Các số ở § 3.1 là so sánh tương đối, không phải ước lượng độc lập.
3. **Trích dẫn đo ở mức URL.** Đúng bài chưa chứng minh đoạn trích đủ để kết luận; audit thủ công ở mức đoạn (W5-03a) đang chờ người đọc.
4. **Lỗi còn lại chủ yếu thuộc verifier.** REFUTED bị đoán SUPPORTED (88 claim) và REFUTED bị đoán NEI (62 claim). Luật hậu kiểm chỉ sửa được ca "gần nguyên văn". Hướng sửa đã chuẩn bị là dữ liệu hard negative RT-V3 (§ 7).
5. **NEI vừa là nhãn sự thật vừa là hành vi từ chối.** Accuracy vì vậy "thưởng" việc từ chối đúng lúc. Báo cáo này tách riêng tỷ lệ trích dẫn trên phần verdict quyết đoán.

## 7. Phần đã xong và phần cần người/GPU

**Đã xong (code, dữ liệu, đo đạc):**
- Pipeline local và web hợp nhất trong giao diện và CLI.
- Verifier RT-V2 với ensemble và luật cặp-tối-thiểu, đã chọn trên dev và đo một lần trên test.
- Sửa 20 lỗi đối kháng.
- Release check, demo 6 ca, so sánh có khoảng tin cậy, phân tích theo nguồn.
- Bundle hard negative RT-V3 dựng sẵn và kiểm hash.

**Cần người hoặc GPU** (hướng dẫn từng bước: [HUONG_DAN_VIEC_CON_LAI.md](HUONG_DAN_VIEC_CON_LAI.md)):

| Việc | Cần | Kết quả điền vào |
|---|---|---|
| W5-06: phân xử 53 cặp + spot-check 50 cặp silver | Người đọc (~2,5 giờ) | Kappa người–AI · _chưa có_ |
| W5-03a: audit 50 trích dẫn ở mức đoạn | Người đọc (~1,5 giờ) | Tỷ lệ đoạn đủ để kết luận · _chưa có_ |
| W5-04: đối chứng gold-only | GPU (~30 phút) | Δ dev do nhãn silver · _chưa có_ |
| RT-V3 hard negative: spot-check 60 cặp, train, so dev | Người + GPU | Δ dev so với RT-V2 · _chưa có_ |
| Bộ gold thực tế ≥ 300 claim, 2 người gán độc lập | Người | Độ chính xác ngoài đời (điều kiện để nói về mốc 80%) · _chưa có_ |

## 8. Kết luận

Sản phẩm chạy đầu-cuối, có giao diện, có trích dẫn kiểm chứng được, chạy được cả kho local lẫn web có neo thời gian. Trên test ViFactCheck, cấu hình cuối đạt **Macro-F1 72,3%**, cao hơn baseline W4-02 **+12,8 điểm (CI 95% [+10,0; +15,6])**. Mọi cải tiến đều được chọn trên dev có nhãn người. Hệ thống **chưa đạt và chưa đo được** mục tiêu 80% ngoài thực tế; § 7 liệt kê đúng các bước còn thiếu để đo điều đó.
