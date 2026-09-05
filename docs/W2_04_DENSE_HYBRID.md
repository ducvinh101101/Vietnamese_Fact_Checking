# W2-04 — thử dense retrieval và hybrid RRF

## Kết quả và quyết định

**Hoàn thành W2-04; giữ BM25 cho cấu hình hiện tại.** Đã chạy toàn bộ 1.080 query
dev trên cùng corpus, tham số cố định. Hai phương án mới đều không đạt tiêu chí
cải thiện cả Recall@5 và MRR@5. Chưa đưa dense/hybrid vào pipeline.

| Phương pháp | Recall@3 | Recall@5 | MRR@5 | Mean ms/query | p95 ms/query |
|---|---:|---:|---:|---:|---:|
| BM25 | 98,15% | 98,52% | 0,96585 | 62,68 | 115,04 |
| E4: E5-small + FAISS | 94,35% | 95,65% | 0,91253 | 23,69 | 33,72 |
| Hybrid RRF retrieval | 97,69% | 98,43% | 0,95469 | 86,49 | 146,12 |

Dense nhanh hơn nhưng Recall@5 giảm 2,87 điểm phần trăm và MRR giảm khoảng
0,05332. Hybrid chỉ kém BM25 một query ở Recall@5 (1.063 so với 1.064 hits),
nhưng MRR cũng thấp hơn và latency tăng. Không kết luận mọi dense model hay
mọi cấu hình hybrid đều kém; đây là quyết định cho cấu hình cố định đã thử.

Số liệu dev không được so trực tiếp với điểm test W2-01 để kết luận tăng/giảm.
Baseline W2-01 đã được tính lại từ predictions và khớp báo cáo. Kiểm tra độc lập
W2-04 xác nhận đủ 1.080 query, top-5 IDs, metrics và hash; pytest đạt 15/15 và
`pip check` không có dependency lỗi. Không thay đổi `src/` hoặc phần verifier.

## Phạm vi và protocol

Quang thử E4 (multilingual-e5-small + FAISS) và E5 (BM25 + dense,
Reciprocal Rank Fusion). Script thí nghiệm gọi BM25 hiện hữu.

Corpus cố định: 5.845 passages ViFactCheck. Query lấy toàn bộ tập **dev**
group split; dùng dev để quyết định giữ hay bỏ cấu hình. Không tuning trên test.
Gold relevance theo URL như W2-01: một passage thuộc đúng URL được tính là hit.
Recall@k ở đây là tỷ lệ query có ít nhất một hit trong k passages, không phải
tỷ lệ toàn bộ passages liên quan được tìm thấy. Nhiều passage cùng URL vẫn chiếm
nhiều vị trí. MRR bị cắt ở 5. Đây chưa phải đánh giá độ đúng của đoạn bằng chứng
hoặc nhãn fact-check; số 57,06% khớp chuỗi ở W2-01 cũng không phải accuracy của BM25.

Tham số được cố định trước khi xem kết quả:

- Model `intfloat/multilingual-e5-small`, revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Prefix `query: ` / `passage: `, tối đa 512 tokens, masked mean pooling và
  chuẩn hóa L2 theo [model card](https://huggingface.co/intfloat/multilingual-e5-small).
- FAISS `IndexFlatIP` tìm kiếm chính xác bằng inner product trên vector chuẩn hóa.
- RRF cộng `1 / (60 + rank)` từ hai danh sách top 100, trọng số bằng nhau.
  Khi hòa điểm, ưu tiên thứ tự passage trong corpus. Không dùng URL gold khi xếp hạng.
- Chỉ xem xét thay BM25 nếu **cả Recall@5 và MRR@5 trên dev đều tăng**.
  Đây là tiêu chí sàng lọc cho thí nghiệm này, chưa phải chứng minh ý nghĩa thống kê.
- CPU, 4 threads. Latency dense gồm encode từng query và search FAISS;
  hybrid gồm BM25 + dense + fusion tuần tự. Thời gian tạo vector corpus được ghi riêng.

## Chạy lại

Từ thư mục gốc repository, dùng Python 3.11 và môi trường đã khóa:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-retrieval.txt
$env:HF_HOME = 'D:\Vietnamese_Fact_Checking\.cache\huggingface'
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; print(snapshot_download('intfloat/multilingual-e5-small', revision='614241f622f53c4eeff9890bdc4f31cfecc418b3', allow_patterns=['*.json','model.safetensors','tokenizer.json'], cache_dir='.cache/huggingface/hub'))"
.\.venv\Scripts\python.exe scripts/evaluate_dense_hybrid.py --model-path .cache/huggingface/hub/models--intfloat--multilingual-e5-small/snapshots/614241f622f53c4eeff9890bdc4f31cfecc418b3
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_w2_04_results.py
```

Sau lần tải đầu, benchmark chạy offline. Model/vector được giữ trong `.cache/`
đã bị Git ignore. Requirements bổ sung duy nhất `faiss-cpu==1.12.0` và kế thừa
`requirements.lock`; không thay phiên bản môi trường baseline của Vinh.

Output `outputs/retrieval/w2_04/dev_metrics.json` ghi tham số, môi trường, hash
corpus/split/model/script, metrics và điều kiện lựa chọn. `dev_predictions.jsonl`
lưu top 5 passage IDs và latency cho từng query, từng phương pháp để tính lại metrics.
Cache vector có khóa phụ thuộc nội dung corpus, model và preprocessing.

## Kiểm chứng

Script kiểm tra URL gold tồn tại, passage ID duy nhất, vector hữu hạn/chuẩn hóa,
và đối chiếu kết quả FAISS với phép nhân vector trực tiếp. Unit tests kiểm tra
RRF, tie-break và cách tính metrics có trường hợp miss. Khi chốt kết quả, kiểm tra
lại metrics độc lập từ prediction và đối chiếu BM25 với baseline W2-01.

E5 trong sheet nhật ký còn yêu cầu Macro-F1 end-to-end của Vinh + Quang.
W2-04 chỉ bàn giao so sánh hybrid retrieval; không kết luận E5 end-to-end đã xong.
