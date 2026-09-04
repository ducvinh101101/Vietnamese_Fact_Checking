# Data contract v1.0

W1-06 chốt định danh và metadata cho dữ liệu bài viết, claim và evidence. Mọi thời điểm dùng ISO 8601 ở UTC (ví dụ `2026-09-03T10:30:00Z`). Trường không thể suy ra từ dữ liệu gốc phải được ghi `null`, không được bịa giá trị.

## Article

| Trường | Bắt buộc | Quy tắc |
|---|---|---|
| `article_id` | Có | ID ổn định, duy nhất trong corpus. |
| `title`, `body`, `url` | Có | Tiêu đề, nội dung gốc và URL canonical. |
| `published_at` | Có thể `null` | Thời điểm xuất bản từ nguồn. |
| `retrieved_at` | Có thể `null` | Thời điểm thu thập/truy xuất. |
| `source`, `source_type`, `authority_score` | Có | Nguồn, loại nguồn và điểm tin cậy 0–1; dùng `unknown`/`null` khi chưa đánh giá. |

`source_type` chỉ nhận: `government`, `international_org`, `news`, `fact_check`, `academic`, `other`, hoặc `unknown`.

## Claim

| Trường | Bắt buộc | Quy tắc |
|---|---|---|
| `claim_id` | Có | ID duy nhất của một claim nguyên tử. |
| `article_id` | Có | Khóa ngoại tới `Article.article_id`. |
| `text` | Có | Nội dung claim nguyên tử. |
| `published_at` | Có thể `null` | Thời điểm của claim nếu khác bài viết. |

## Evidence JSONL

Mỗi dòng là một passage và phải có `document_id`, `passage_id`, `content`, `source`, `url`, `article_id`, `title`, `published_at`, `retrieved_at`, `source_type`, `authority_score`, `schema_version`.

- `article_id` phải tham chiếu một article; với corpus ViFactCheck hiện tại, nó bằng `document_id`.
- `passage_id` duy nhất trong corpus; `content` không dài quá 700 ký tự.
- Corpus ViFactCheck v1.0 chưa cung cấp tiêu đề và thời gian tin cậy nên các trường này là `null`; `source_type` là `unknown`. Web ingestion sau này phải điền metadata thực.
- Loader vẫn đọc JSONL cũ chỉ có các trường bắt buộc để không làm hỏng pipeline MVP.

## Kiểm tra bàn giao

Chạy `python scripts/build_vifactcheck_evidence.py`, sau đó load `data/evidence/vifactcheck_passages.jsonl` bằng `src.io_utils.load_evidence_jsonl`. Test contract nằm tại `tests/test_data_contract.py`.
