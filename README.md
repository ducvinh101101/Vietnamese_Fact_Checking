# Vietnamese Fact-Checking — MVP hiện tại và roadmap 6 tuần

Nền tảng cộng tác cho dự án đánh giá độ tin cậy và kiểm chứng thông tin tiếng Việt. Phiên bản này ưu tiên một luồng chạy được ngay:

`claim → truy xuất evidence → kết luận có trích dẫn`

Người mới có thể đọc [giới thiệu tổng quan dự án](docs/GIOI_THIEU_DU_AN.md) trước khi đi vào phần cài đặt và tài liệu kỹ thuật.

Nhánh phân loại nội dung được giữ tách biệt để phát triển sau; nó không quyết định nhãn đúng/sai cuối cùng.

## Bắt đầu nhanh

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py -3.13 scripts/check_release.py          # kiểm tra máy: thư viện, model, Java, hash dữ liệu
py -3.13 app_gradio.py                     # giao diện Gradio (khuyên dùng) -> http://127.0.0.1:7860
py -3.13 -m streamlit run app.py           # giao diện Streamlit (bản cũ, cùng kết quả)
```

Cần chuẩn bị checkpoint verifier `models/rt_v2_balanced/best_model` (RT-V2), VnCoreNLP tại `models/vncorenlp` và Java; chỉ cài requirements là chưa đủ. Xem [hướng dẫn tái lập](docs/REPRODUCIBILITY_BASELINE.md). Nếu Windows Application Control chặn torch, giao diện tự chuyển sang chế độ demo rule-based và báo rõ.

### Hai chế độ (chọn trong giao diện)

| Chế độ | Bằng chứng | Khi nào dùng | Đã đo? |
|---|---|---|---|
| **Kho local** | BM25 trên 5.845 đoạn ViFactCheck | Báo cáo, so sánh, demo có kỳ vọng | Có — test Macro-F1 **72,3%** |
| **Local + web** | + Tavily qua 33 nguồn allowlist, neo thời gian, gộp URL, guard | Claim thời sự ("hôm nay", "hiện nay") | Chưa có tập có nhãn |

Web cần `TAVILY_API_KEY` (đặt trong `.env`, xem `.env.example`). Thiếu key thì tự chạy chỉ với kho local.

### So sánh PhoBERT với Gemini trên 84 gold case

Đặt `GEMINI_API_KEY` và `GEMINI_MODEL` trong `.env` ở thư mục gốc. Chạy
`scripts/run_model_gold.py --backend phobert|gemini --output <file.jsonl>` cho từng
model, sau đó chấm bằng `scripts/evaluate_model_gold.py`. Hai nhánh nhận cùng
bằng chứng cố định, không truy xuất lại và không đọc đáp án khi suy luận.
Xem [hướng dẫn cắm key, chạy app và so sánh](docs/HUONG_DAN_GEMINI_COMPARISON.md).
Gemini chưa được nối vào nút kiểm chứng của giao diện; key này dùng cho runner so sánh.

### Lệnh thường dùng

```powershell
py -3.13 scripts/run_web_fact_check.py --claim "Giá xăng tăng từ chiều nay"      # CLI (local + web)
py -3.13 scripts/run_web_fact_check.py --claim "..." --local-only
py -3.13 scripts/run_demo_cases.py [--with-web]        # demo 6 ca có kỳ vọng -> outputs/demo/demo_cases.md
py -3.13 scripts/compare_final_vs_baselines.py         # bảng so sánh + khoảng tin cậy (không chạy model)
py -3.13 -m pytest -q --basetemp=.pytest_tmp           # ~300 test, không cần GPU
```

Đây là bản thử nghiệm, **chưa được xác nhận đạt 80% ngoài thực tế**. Xem [báo cáo tổng kết](docs/BAO_CAO_TONG_KET.md).

## Kết quả chính (dữ liệu ViFactCheck)

| Phép đo | Macro-F1 | Ghi chú |
|---|---:|---|
| Verifier oracle (E2, bằng chứng vàng) | 81,07% | Trần của verifier, không phải năng lực hệ thống |
| End-to-end baseline W4-02 (test) | 59,49% | BM25 → E2 |
| End-to-end rerank W4-05 (test) | 69,92% | E2 + rerank metadata |
| **End-to-end cấu hình cuối (test, chạy một lần)** | **72,31%** | RT-V2 + ensemble + cặp-tối-thiểu; **+12,8 [+10,0; +15,6]** so với W4-02 |

Mọi lựa chọn cấu hình đều làm trên dev có nhãn người. Test đã được dùng cho các lượt trước nên đây là **so sánh tương đối, không phải bằng chứng độc lập**. Chi tiết: [báo cáo tổng kết](docs/BAO_CAO_TONG_KET.md) · [kết quả & giới hạn](docs/BAO_CAO_KET_QUA_GIOI_HAN.md) · [lỗi & challenge set](docs/BAO_CAO_LOI_TU_TEST_DOI_KHANG.md) · [việc còn lại cần người/GPU](docs/HUONG_DAN_VIEC_CON_LAI.md).

## Cấu trúc

- `src/`: pipeline và các thành phần NLP.
- `data/`: dữ liệu thô, đã xử lý, kho bằng chứng.
- `configs/config.yaml`: cấu hình tập trung.
- `tests/`: kiểm thử tự động cơ bản.
- `docs/`: phân công hai người, quy trình nghiên cứu và backlog.
- `outputs/`: metrics, hình và dự đoán; không đưa artefact lớn lên Git.

## Luồng làm việc hai người

Đọc [phân công](docs/PHAN_CONG_2_NGUOI.md) và [quy trình nghiên cứu](docs/QUY_TRINH_NGHIEN_CUU.md) trước khi bắt đầu. Mỗi thay đổi nên có một nhánh Git riêng và một mục trong `docs/BACKLOG.md`.

## Dữ liệu ViFactCheck

Dữ liệu ViFactCheck dùng để tái lập hiện được lưu trong Git, gồm dữ liệu gốc tại `data/raw/`, dữ liệu đã xử lý tại `data/processed/` và corpus passage tại `data/evidence/`. Corpus giữ các trường tối thiểu:

```json
{"document_id":"...","passage_id":"...","content":"...","source":"...","url":"..."}
```

Sau khi lưu ba split ViFactCheck vào `data/raw/vifactcheck/` (dạng Hugging Face Arrow hoặc Parquet), tạo corpus cục bộ bằng:

```powershell
python scripts/build_vifactcheck_evidence.py
```

Script đọc `Context`, `Author` và `Url`, khử trùng theo URL rồi chia bài báo thành các passage tối đa 700 ký tự.

Kế hoạch triển khai hiện hành nằm trong [workbook phân công Vinh–Quang](KE_HOACH_TRIEN_KHAI_2_NGUOI.xlsx), kèm [quy trình nghiên cứu](docs/QUY_TRINH_NGHIEN_CUU.md) và [backlog](docs/BACKLOG.md).

## Web retrieval và rerank

Web retriever qua allowlist (`src/web_retriever.py`), corpus v2 có metadata, rerank theo nguồn (W3-08), fusion RRF local + web (`src/fusion_retriever.py`), neo thời gian (`src/temporal_gate.py`) và gộp URL (`src/topical_rerank.py`) đều được dựng chung tại `src/system_builder.py` cho cả giao diện lẫn CLI. Tầng hybrid **chưa có số đo định lượng** vì chưa có tập claim thời sự có nhãn. Xem [hướng dẫn test web](docs/HUONG_DAN_TEST_WEB_END_TO_END.md).

## Kế hoạch phạm vi đầy đủ

Để bao phủ cả phân tích nội dung, claim decomposition, retrieval/RAG và tổng hợp cấp bài, xem [kế hoạch 6 tuần](docs/KE_HOACH_DAY_DU_DE_TAI.md).

## Theo dõi phạm vi đề tài

[Ma trận yêu cầu đề tài](docs/MA_TRAN_YEU_CAU_DE_TAI.md) liên kết từng yêu cầu với task và thí nghiệm. Các hạng mục ghi `Planned` chưa được xem là chức năng đã hoàn thành.
