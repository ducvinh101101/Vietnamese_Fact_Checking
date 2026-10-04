# BÁO CÁO KIỂM THỬ VÀ ĐÁNH GIÁ CHẤT LƯỢNG HỆ THỐNG
## Dự án: Vietnamese Fact-Checking (Kiểm chứng thông tin tiếng Việt)
*Căn cứ theo tiêu chuẩn và thang đo tại: `Testing_readme.md`*  
*Thời điểm thực hiện: 2026-10-04*

---

## 1. Kết Quả Chạy Kiểm Thử Toàn Bộ Dự Án

### 1.1 Kiểm thử tự động (Pytest Suite)
- **Tổng số testcase:** 155 testcases
- **Trạng thái:** **155/155 PASSED (100%)**
- **Thời gian thực thi:** 9.26s
- **Các thành phần được kiểm thử:**
  - Data contract & Versioned evidence corpus integrity ([test_data_contract.py](file:///d:/Vietnamese_Fact_Checking/tests/test_data_contract.py), [test_versioned_evidence_corpus.py](file:///d:/Vietnamese_Fact_Checking/tests/test_versioned_evidence_corpus.py))
  - Quy tắc bảo vệ thời gian ([test_temporal_gate.py](file:///d:/Vietnamese_Fact_Checking/tests/test_temporal_gate.py))
  - Xếp hạng theo chủ đề & gộp URL ([test_topical_rerank.py](file:///d:/Vietnamese_Fact_Checking/tests/test_topical_rerank.py))
  - Bộ gác phán quyết & bảo vệ bằng chứng ([test_verdict_guard.py](file:///d:/Vietnamese_Fact_Checking/tests/test_verdict_guard.py), [test_verifier_evidence_guard.py](file:///d:/Vietnamese_Fact_Checking/tests/test_verifier_evidence_guard.py))
  - Truy xuất web, allowlist host & parser metadata ([test_web_retriever.py](file:///d:/Vietnamese_Fact_Checking/tests/test_web_retriever.py), [test_web_retrieval_config.py](file:///d:/Vietnamese_Fact_Checking/tests/test_web_retrieval_config.py))

### 1.2 Kiểm thử kịch bản mẫu (Golden Cases)
- **Script kiểm thử:** `scripts/run_golden_eval.py` / `tests/test_golden_web_verification.py`
- **Kết quả:** **11/11 PASSED (100%)**
- **Nội dung bao phủ:**
  - Grounding & freshness check: Tin tức mới, đúng chiều $\to$ `SUPPORTED`
  - Neo thời gian: Tin tức cũ $\to$ `NEI` (không dùng bài cũ để xác nhận)
  - Guard mâu thuẫn trái chiều: Bằng chứng trái chiều $\to$ không `SUPPORTED`
  - Guard lạc chủ đề: Bằng chứng giá dầu thế giới $\to$ không xác nhận giá bán lẻ trong nước
  - Khả năng chịu lỗi: Web rỗng $\to$ tự động fallback sang kho tài liệu cục bộ

### 1.3 Kiểm tra dữ liệu kho chứng cứ (Corpus Integrity)
- **Tập dữ liệu:** `data/evidence/vifactcheck_passages.jsonl`
- **Tổng số passage:** 5,845 dòng (5,844 passage hợp lệ sau khử trùng)
- **Độ dài đoạn văn:** 100% $\le 700$ ký tự (max: 700 ký tự)
- **Tính toàn vẹn trường:** 100% đầy đủ 5 trường bắt buộc (`document_id`, `passage_id`, `content`, `source`, `url`), không có trường rỗng.
- **Tính duy nhất:** Duy nhất 100% `passage_id`.

---

## 2. Nhật Ký Lỗi & Bug Đã Phát Hiện (Bug Log)

> Cập nhật xử lý: 2026-10-04. BUG-01 đến BUG-05 đã được sửa trong mã và có regression test cho các hành vi có thể kiểm thử không cần model thật. BUG-06 đã có regression gate deterministic cho bộ golden web hiện hữu; bộ 60 claim có nhãn được giữ là hạng mục dữ liệu đánh giá, không tạo nhãn giả để đóng lỗi.

| Mã lỗi | Phân loại | Tệp tin / Vị trí | Mức độ | Hiện tượng & Tác động |
|:---:|---|---|:---:|---|
| **BUG-01** | Logic Trích dẫn | [src/fact_checker.py](file:///d:/Vietnamese_Fact_Checking/src/fact_checker.py#L39-L41) | **Cao** | **Gán trích dẫn sai quy chuẩn khi kết luận NEI**: Khi `overlap < support_threshold` (nhãn `NOT_ENOUGH_INFO`), `RuleBasedFactChecker` vẫn trả về `evidence_ids=[best.evidence.passage_id]`. Hành vi này **vi phạm trực tiếp tiêu chí F-04** (*"Kết luận NEI: Không gán trích dẫn như bằng chứng quyết định"*). |
| **BUG-02** | Mã hóa I/O | [scripts/run_golden_eval.py](file:///d:/Vietnamese_Fact_Checking/scripts/run_golden_eval.py#L232), scripts CLI | **Trung bình** | **Crash Unicode trên Windows Console**: Khi chạy script trên terminal Windows mặc định (cp1252), hàm `print()` chuỗi tiếng Việt có dấu làm crash chương trình: `UnicodeEncodeError: 'charmap' codec can't encode character '\u1ed7'`. Cần set `PYTHONUTF8=1` hoặc cấu hình `sys.stdout.reconfigure(encoding='utf-8')`. |
| **BUG-03** | Xử lý ngoại lệ | [src/phobert_fact_checker.py](file:///d:/Vietnamese_Fact_Checking/src/phobert_fact_checker.py#L50-L57) | **Trung bình** | **Che giấu lỗi DLL (Exception Masking)**: Bọc khối `try...except ImportError` bắt mọi lỗi nạp thư viện và hiển thị *"Cần cài torch, transformers và py_vncorenlp..."*. Khi Windows Application Control chặn nạp file `torch/_C.pyd` hoặc thiếu DLL C++ runtime, thông báo này làm người dùng chẩn đoán sai bản chất lỗi. |
| **BUG-04** | Kiểm soát lỗi | [src/phobert_fact_checker.py](file:///d:/Vietnamese_Fact_Checking/src/phobert_fact_checker.py#L64-L67), [app.py](file:///d:/Vietnamese_Fact_Checking/app.py#L14-L30) | **Trung bình** | **Vi phạm Testcase A-02, A-03 & A-04**: Không kiểm tra sự tồn tại của `model_path` và `vncorenlp_dir` trước khi gọi HuggingFace/Java (gây traceback dài dòng thay vì báo lỗi tiếng Việt rõ ràng). Thiếu bộ kiểm tra schema cho `config.yaml` (bị crash `KeyError` nếu thiếu cấu hình). |
| **BUG-05** | Trải nghiệm UI | [app.py](file:///d:/Vietnamese_Fact_Checking/app.py#L43-L46) | **Thấp** | **Vi phạm Testcase G-02 & G-06**: Nhập chuỗi rỗng / dấu cách vẫn kích hoạt gọi backend `run_cached()` rồi mới ném `ValueError` thay vì chặn ngay tại UI. Giao diện thiếu hiển thị ghi chú bắt buộc: *"Bản thử nghiệm, chưa xác nhận 80% ngoài thực tế"*. |
| **BUG-06** | Test Suite | [tests/](file:///d:/Vietnamese_Fact_Checking/tests) | **Thấp** | **Chưa hiện thực hóa Khung Pytest mẫu & Golden Set E2E**: Bộ test hiện tại chỉ mock/stub verifier. File kiểm thử tự động `tests/test_golden_and_gate.py` và tập 60 claim mẫu `tests/golden_claims.jsonl` được quy định tại Mục 4 của `Testing_readme.md` chưa được tạo thực tế trong repo. |

### Trạng thái khắc phục

| Mã lỗi | Trạng thái | Cách xử lý |
|---|---|---|
| BUG-01 | Đã sửa | NEI của `RuleBasedFactChecker` trả danh sách citation rỗng; có test hồi quy. |
| BUG-02 | Đã sửa | Entry point `run_golden_eval.py` tự cấu hình stdout/stderr UTF-8 trên Windows. |
| BUG-03 | Đã sửa | Tách lỗi thiếu package, lỗi import và lỗi DLL/native; thông báo giữ nguyên nguyên nhân kỹ thuật. |
| BUG-04 | Đã sửa | Kiểm tra sớm thư mục model/VnCoreNLP, Java và schema tối thiểu của `config.yaml`. |
| BUG-05 | Đã sửa | UI chặn claim rỗng trước khi gọi backend và hiển thị cảnh báo giới hạn 80%. |
| BUG-06 | Cải thiện một phần | Regression test deterministic hiện có được giữ và mở rộng bằng test guard. Chưa có 60 claim được gán nhãn độc lập, vì đây là dữ liệu đánh giá cần con người phê duyệt. |

---

## 3. Bảng Điểm Đánh Giá Tổng Thể (Thang 100 Điểm)

*Dựa trên mục 2.2 và 2.4 của `Testing_readme.md`:*

| Hạng mục | Điểm tối đa | Điểm đạt | Tiêu chí đánh giá & Căn cứ thực tế |
|---|---:|---:|---|
| **Độ chính xác e2e (Macro-F1)** | 30 | **20** | Macro-F1 trên test đạt **69.92%**, trên dev đạt **70.75%** (mốc 70–75% đạt 20đ). F1 lớp `REFUTED` đạt **64.23%**. |
| **Chất lượng truy xuất** | 15 | **15** | Recall@3 URL đạt **98.15%** (đạt ngưỡng $\ge 85\%$ = 15đ). Khâu BM25 + topical reranking (W3-08) hoạt động chính xác trên corpus. |
| **Chất lượng trích dẫn** | 20 | **12** | Valid 100% (URL và passage_id có thật = 10đ). Tỷ lệ hỗ trợ thực tế đạt **55.39%** trên test; phát hiện bug gán trích dẫn khi NEI ở rule-based checker. |
| **Độ bền và xử lý lỗi** | 10 | **7** | Vượt qua 155 unit tests, chịu được claim dài, emoji, URL. Điểm trừ: lỗi mã hóa cp1252 console và che giấu ngoại lệ import. |
| **Khả năng tái lập** | 10 | **8** | Cố định `seed=42`, kết quả kiểm thử nhất quán 100%. Điểm trừ: chạy CLI trên Windows cần thiết lập thủ công biến môi trường UTF-8. |
| **Hiệu năng vận hành** | 5 | **5** | Độ trễ p50 đạt **583ms – 660ms**, p95 đạt **843ms – 872ms** (vượt xa yêu cầu p95 < 10.000ms). |
| **Trung thực tài liệu** | 10 | **9** | Minh bạch về các hạn chế (nêu rõ chưa có hybrid fusion, không dùng AGG-V1). Điểm trừ: UI Streamlit thiếu dòng disclaimer thực tế. |
| **TỔNG ĐIỂM** | **100** | **76 / 100** | **XẾP HẠNG: B** *(Hệ thống hoạt động tốt, đạt chuẩn trên MVP, còn một số lỗi cần xử lý trước khi release)* |

---

## 4. Các Điểm Cần Tối Ưu Hóa (Actionable Recommendations)

### 4.1 Khắc phục lỗi Codebase (Ưu tiên cao)
1. **Sửa lỗi gán trích dẫn trong [src/fact_checker.py](file:///d:/Vietnamese_Fact_Checking/src/fact_checker.py):**
   ```python
   # Dòng 40 sửa thành:
   evidence_ids = [] if label == "NOT_ENOUGH_INFO" else [best.evidence.passage_id]
   ```
2. **Chuẩn hóa UTF-8 output cho toàn bộ Script CLI:**
   Thêm đoạn mã sau vào đầu các file script entry-point:
   ```python
   import sys
   if sys.platform == "win32":
       sys.stdout.reconfigure(encoding="utf-8", errors="replace")
       sys.stderr.reconfigure(encoding="utf-8", errors="replace")
   ```
3. **Thêm cơ chế kiểm tra môi trường & tài nguyên fail-early:**
   Trước khi nạp model trong `PhoBERTFactChecker`, kiểm tra rõ `Path(model_path).exists()` và `Path(vncorenlp_dir).exists()`, ném ra lỗi tiếng Việt kèm đường dẫn chính xác nếu thiếu.

### 4.2 Cải tiến Giao diện Streamlit ([app.py](file:///d:/Vietnamese_Fact_Checking/app.py))
- Kiểm tra `if not claim.strip(): st.warning("Vui lòng nhập phát biểu cần kiểm chứng"); st.stop()` để chặn gọi backend lãng phí.
- Bổ sung dòng thông báo chuẩn Testcase G-06:
  ```python
  st.warning("⚠️ Bản thử nghiệm nghiên cứu, chưa xác nhận 80% ngoài thực tế. Luôn kiểm tra đối chiếu nguồn gốc trích dẫn.")
  ```

### 4.3 Xây dựng Regression Gate tự động
- Tạo bộ dữ liệu `tests/golden_claims.jsonl` gồm 60 câu mẫu chuẩn (phân chia đều theo E-01 $\to$ E-06).
- Thêm file test `tests/test_golden_and_gate.py` để tự động hóa kiểm tra hồi quy Macro-F1 $\ge 69.5\%$ trước mỗi lần commit.

### 4.4 Nâng cao chất lượng nhận diện `REFUTED`
- F1 lớp `REFUTED` (62.2% - 64.2%) đang kéo lùi điểm tổng thể so với `SUPPORTED` (76.2%). Cần bổ sung thêm negative hard pairs (tập trung vào đảo số liệu, ngày tháng, thay đổi thực thể) vào tập train để đưa Macro-F1 vượt mốc 75%.
