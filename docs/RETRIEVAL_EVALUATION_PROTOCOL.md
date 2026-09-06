# Protocol đánh giá retrieval — W2-10

## Quyết định và phạm vi

W2-10 chốt cách nạp corpus, query set và cách báo cáo retrieval. Protocol này
không thay đổi verifier, nhãn ViFactCheck hoặc `src/`. Nó tách hai câu hỏi:

1. Retriever có đưa được passage từ đúng **bài nguồn** vào top-k không?
2. Retriever có đưa được **đoạn đủ bằng chứng** vào top-k không?

Query audit 10 mẫu ở W2-01 chỉ để đọc kết quả, không là benchmark và không được
dùng để chọn mô hình. Benchmark v1 dùng toàn bộ query frozen: 1.080 dev và 1.076
test từ group split URL-disjoint. Dev chỉ dùng để chọn cấu hình; test chỉ chạy sau
khi chốt cấu hình. Không chọn theo test, không thay query/URL/qrel sau khi nhìn
kết quả test.

## Corpus ingestion contract

Corpus hiện tại là `data/evidence/vifactcheck_passages.jsonl`: 5.845 passages từ
1.041 URL. Mỗi passage cần `passage_id`, `article_id`, `content`, `url`, `source`,
`published_at`, `retrieved_at`, `source_type`, `authority_score` và
`schema_version`; chi tiết schema ở [data contract](DATA_CONTRACT.md).

Mỗi lần ingestion mới phải:

1. Canonicalize URL trước khi sinh `article_id`; giữ URL gốc và ghi quy tắc
   canonicalize trong manifest.
2. Chunk sau khi lấy main text, không tách giữa Unicode code point; ghi chunker,
   max length, overlap, thứ tự passage và phiên bản schema.
3. Khử trùng theo `(normalized_url, normalized_content)`, nhưng không xóa record
   gốc âm thầm: ghi số record bỏ/ghép, lý do và hash đầu vào/đầu ra.
4. Bắt buộc có `retrieved_at`; không suy đoán `published_at`. Web source phải có
   `source_type` và `authority_score` theo policy đã review.
5. Xuất manifest gồm hash corpus, số URL/article/passage, thống kê chunk, metadata
   null-rate, config, thời gian và Git commit. Corpus/hash khác là benchmark khác.

Corpus đang có metadata thời gian/title chưa tin cậy nên là `null`; do đó chưa
được dùng để kết luận temporal filtering. Đây là đầu vào cho W3-07, không phải
lỗi được che giấu trong metric.

## Query set v1 và gold

Chạy:

```powershell
.\.venv\Scripts\python.exe scripts\build_retrieval_query_set.py
```

Script tạo [query set](../data/evaluation/vifactcheck_retrieval_query_set_v1.jsonl)
và manifest. ID có dạng `vifactcheck:{split}:{source_row_id}`, không dựa vào vị
trí dòng. Mỗi query mang `gold_url` và `gold_article_id`; builder dừng nếu gold
URL không nằm trong corpus, ID trùng, trường thiếu hoặc URL dev/test giao nhau.

`silver_exact_passage_ids` chỉ là candidate sinh bằng containment sau chuẩn hóa
từ trường `Evidence`. Nó có coverage được ghi trong manifest nhưng **không phải
passage-qrels**. Không bỏ query không khớp; điều đó sẽ làm benchmark thiên lệch.

Để có passage-qrels, hai người đọc độc lập, không xem ranking/model, gán:

| Grade | Ý nghĩa |
|---:|---|
| 2 | Passage trực tiếp đủ để ủng hộ hoặc bác bỏ claim. |
| 1 | Context liên quan nhưng chưa đủ một mình. |
| 0 | Không liên quan. |

Giải quyết bất đồng bằng adjudication, lưu người chấm/mã guideline/thời điểm và
giữ mọi qrel cũ cùng lý do sửa. Query không chấm không được lặng lẽ xem là gold
negative; khi tính metric, passage không nằm trong qrels được grade 0 theo một
pooling depth đã công bố. Bản qrels review là artefact mới, không sửa annotation
gốc của Vinh.

## Metrics và cách báo cáo

Mọi report ghi corpus hash, query-set manifest hash, config hash, Git commit,
runtime/device, số query và latency scope.

| Metric | Điều kiện dùng | Định nghĩa |
|---|---|---|
| URL Recall@3/5 | Query v1 hiện tại | Tỷ lệ query có ít nhất một passage cùng `gold_url` trong top-k. |
| URL MRR@5 | Query v1 hiện tại | `1/rank` của passage cùng URL đầu tiên trong top 5, không có thì 0. |
| Passage Recall@3/5 | Sau qrels review | Tỷ lệ query có grade 1 hoặc 2 trong top-k. Báo riêng grade≥2 nếu dùng để claim evidence. |
| Passage MRR@5 | Sau qrels review | Reciprocal rank của passage grade≥1 đầu tiên. |
| nDCG@5 | Sau qrels review | `DCG@5 = Σ (2^grade−1)/log2(rank+1)`, chia cho ideal DCG@5. Grade 2/1/0. |
| Latency | Mọi run | p50/p95/mean per query, ghi rõ có gồm encode, network, cache hay không. |

Không so URL-level với passage-level như cùng một metric. Không dùng Macro-F1
verifier gold-evidence để kết luận retrieval tốt. Với web/hybrid, báo cáo local,
web và merged riêng; tỷ lệ evidence ngoài allowlist phải bằng 0.

## Reproduce và nghiệm thu

```powershell
.\.venv\Scripts\python.exe scripts\build_retrieval_query_set.py
.\.venv\Scripts\python.exe -m pytest -q
```

Nghiệm thu W2-10: query set/manifest có hash, toàn bộ 2.156 query frozen,
không giao URL dev/test, config ingestion/evaluation versioned, threshold và
công thức nDCG được chốt, cùng hướng dẫn qrels review. nDCG chưa có số chính thức
cho đến khi qrels review hoàn tất; đây là trạng thái dữ liệu, không phải ước lượng.
