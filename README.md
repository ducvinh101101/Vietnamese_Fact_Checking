# Vietnamese Fact-Checking — MVP hiện tại và roadmap 6 tuần

Nền tảng cộng tác cho dự án đánh giá độ tin cậy và kiểm chứng thông tin tiếng Việt. Phiên bản này ưu tiên một luồng chạy được ngay:

`claim → truy xuất evidence → kết luận có trích dẫn`

Nhánh phân loại nội dung được giữ tách biệt để phát triển sau; nó không quyết định nhãn đúng/sai cuối cùng.

## Bắt đầu nhanh

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Config hiện tại (`configs/config.yaml`) dùng corpus `data/evidence/vifactcheck_passages.jsonl`, checkpoint verifier tại `models/rt_v2_balanced/best_model` (RT-V2, đã khóa runtime), VnCoreNLP tại `models/vncorenlp`, và chính sách quyết định theo hạng (rank policy, không dùng AGG-V1). Cần chuẩn bị model và Java trước khi kiểm chứng; chỉ cài requirements chưa đủ. Xem [hướng dẫn tái lập](docs/REPRODUCIBILITY_BASELINE.md).

Đây là bản thử nghiệm với kho bằng chứng cục bộ, **chưa được xác nhận đạt accuracy 80% ngoài thực tế**. Xem [tiến độ ưu tiên](docs/PRIORITY_READINESS_PROGRESS.md) và [báo cáo kết quả đầy đủ](docs/BAO_CAO_KET_QUA_GIOI_HAN.md).

## Định hướng mới: kiểm tra nguồn (nhánh `feature/source-attribution-retrieval`)

Đề tài chuyển từ phán **thật/giả** sang **kiểm tra phát biểu có nguồn ngoài thực tế hay không**
(`SOURCE_FOUND` / `SOURCE_CONFLICT` / `NO_SOURCE`). Pipeline RT-V2 cũ giữ nguyên; pipeline mới tái sử dụng
RT-V2 và VnCoreNLP, thêm retrieval mở (web allowlist 25 nguồn), reranker và kiểm tra khớp số/ngày/tên riêng.
Trên dev (1.252 claim, 5 nhóm): độ chính xác trung bình 70,5% (pipeline cũ) → 83,1%, báo nhầm "có nguồn"
19,5% → 5,8%, với verifier RT-V3 train lại trên cửa sổ câu và cửa sổ cắt trên toàn bài (ngưỡng dò trên dev, chưa chạy test). Điền `TAVILY_API_KEY` vào `.env` để bật tìm kiếm web.
Chi tiết, cách train reranker/bi-encoder và giới hạn: [docs/SOURCE_ATTRIBUTION.md](docs/SOURCE_ATTRIBUTION.md).

## Kết quả chính (dev/test, dữ liệu ViFactCheck)

| Phép đo | Macro-F1 | Ghi chú |
|---|---:|---|
| Verifier oracle (E2, gold evidence) | 81,07% | Trần verifier, không phải năng lực hệ thống |
| End-to-end BM25-local (test) | 62,94% | Tự đi tìm bằng chứng |
| End-to-end Reranked-local (test) | **69,92%** | Rerank W3-08, +6,98 điểm |
| Verifier RT-V2 balanced (end-to-end dev) | 70,75% | Đã khóa; F1 REFUTED 64,23%, giảm lệch NEI |

Mọi con số trên là dev/test đã xem nhiều lần, **không phải bằng chứng độc lập**. Chi tiết, ablation và giới hạn: [báo cáo kết quả](docs/BAO_CAO_KET_QUA_GIOI_HAN.md).

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

Web retriever qua allowlist (`src/web_retriever.py`), corpus v2 có metadata nguồn/thời gian, và rerank theo nguồn/authority (`src/reranked_retriever.py`, W3-08) **đã được hiện thực và test riêng**. Pipeline chạy mặc định vẫn dùng kho cục bộ + rerank; bước **hợp nhất local + web (fusion) chưa triển khai**, nên tầng hybrid end-to-end chưa đo được. Xem [kế hoạch web retrieval](docs/WEB_RETRIEVAL_PLAN.md).

## Kế hoạch phạm vi đầy đủ

Để bao phủ cả phân tích nội dung, claim decomposition, retrieval/RAG và tổng hợp cấp bài, xem [kế hoạch 6 tuần](docs/KE_HOACH_DAY_DU_DE_TAI.md).

## Theo dõi phạm vi đề tài

[Ma trận yêu cầu đề tài](docs/MA_TRAN_YEU_CAU_DE_TAI.md) liên kết từng yêu cầu với task và thí nghiệm. Các hạng mục ghi `Planned` chưa được xem là chức năng đã hoàn thành.
