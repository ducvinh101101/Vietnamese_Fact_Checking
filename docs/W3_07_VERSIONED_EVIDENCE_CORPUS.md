# W3-07 — Corpus passage có metadata và dedup

## Phạm vi và artefact

Corpus gốc `data/evidence/vifactcheck_passages.jsonl` được giữ nguyên để không
làm thay đổi benchmark/local pipeline đang có. W3-07 tạo corpus dẫn xuất,
versioned tại `data/evidence/vifactcheck_passages_v2.jsonl`, cùng manifest hash
`data/evidence/vifactcheck_passages_v2_manifest.json`.

Kết quả v2.0.0: 5.845 input passage thành **5.844** passage từ 1.041 URL/article;
khử một duplicate theo `(canonical_url, normalized_content_casefold)`. Record gốc
không bị sửa hay xóa; manifest ghi số input/output và quy tắc dedup.

## Metadata và tính trung thực thời gian

- `domain`, `source_type`, `authority_score` được áp bởi exact-host policy
  versioned ở `configs/evidence_source_policy.yaml`: 1 government source và 8
  news source, không dùng metadata này làm verdict.
- Mọi passage có `retrieved_at=2026-09-16T11:10:00Z`, nghĩa là thời điểm **nạp
  snapshot corpus local**, không phải thời điểm crawl hay xuất bản bài báo.
- `published_at` chỉ suy ra từ URL có mẫu ngày hợp lệ: 1.087 passage có giá trị;
  4.757 passage không suy đoán nên giữ `null`.
- `original_url` được lưu cạnh URL canonical. `article_id`/`passage_id` giữ ổn
  định để không phá query set W2-10.

## Tái lập và kiểm tra

```powershell
.\.venv\Scripts\python.exe scripts\ingest_versioned_evidence_corpus.py --retrieved-at 2026-09-16T11:10:00Z
.\.venv\Scripts\python.exe scripts\check_versioned_evidence_corpus.py
.\.venv\Scripts\python.exe -m pytest -q
```

Validator kiểm hash corpus/policy, required metadata, exact-host policy, URL
canonical, uniqueness, count dedup và null-rate `published_at`. W3-07 chưa chạy
temporal/source filter hoặc reranker; đó là W3-08.
