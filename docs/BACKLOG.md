# Backlog chung

| ID | Việc cần làm | Người phụ trách | Trạng thái | Điều kiện hoàn thành |
|---|---|---|---|---|
| D1 | Tải và audit ViFactCheck | Vinh | Hoàn thành | 7.232 mẫu; không thiếu trường bắt buộc; có audit và split theo URL |
| M1 | TF-IDF + SVM baseline | Vinh | Hoàn thành | E1 group split: Macro-F1 test 40,15%; có confusion matrix và dự đoán |
| M2 | Fine-tune PhoBERT-base | Vinh | Hoàn thành | E2 group split: Macro-F1 test 81,07%; cải thiện 40,92 điểm % so với E1 |
| R1 | Đổi dữ liệu mẫu sang passage ViFactCheck | Quang | Hoàn thành | 5.845 passage từ 1.041 URL ViFactCheck; JSONL hợp lệ, loader đã kiểm tra |
| W1-07 | Khóa môi trường, chạy pytest và ghi manifest/hash artefact | Quang | Hoàn thành | `requirements.lock` (80 dependency), manifest SHA-256 11 artefact và pytest 102/102 pass |
| R2 | Đánh giá BM25 Recall@3/5 | Quang | Hoàn thành | URL-level test: Recall@3 98,14%; Recall@5 98,98%; MRR@5 0,9671; p95 81,20 ms; 10 truy vấn audit |
| W2-04 | Thử dense/FAISS và hybrid RRF | Quang | Hoàn thành | Dev 1.080 query: Recall@5 BM25 98,52%, dense 95,65%, RRF 98,43%; giữ BM25; báo cáo `W2_04_DENSE_HYBRID.md` |
| W2-10 | Protocol corpus ingestion, query set gold và Recall/MRR/nDCG | Quang | Hoàn thành | Query set v1: 2.156 query frozen, manifest/hash, dev/test URL-disjoint; URL-level metrics và passage-qrels/nDCG protocol đã tách rõ |
| W3-01 | Pipeline retrieval → verifier → SUPPORTED/REFUTED/NEI | Quang | Hoàn thành | Corpus ViFactCheck → BM25 top-3 → PhoBERT E2; smoke 3 claim frozen, kiểm tra contract ba nhãn và citation provenance |
| W3-03 | Kiểm tra citation ID/URL, JSON output và trường hợp không có evidence | Quang | Hoàn thành | JSON contract v1 kiểm tra citation ID/URL/score; smoke PhoBERT no-evidence trả NEI, 0 citation; pytest 88 pass |
| W3-05 | Web retrieval: allowlist, passage và metadata nguồn | Quang | Hoàn thành | Sau merge: allowlist 33 exact host; acceptance Tavily 2026-10-03 đạt 6/6 query host-targeted, 6 domain và 6 passage, metadata/URL đầy đủ |
| W3-07 | Corpus passage có metadata nguồn/thời gian và dedup | Quang | Hoàn thành | Corpus v2.0.0: 5.844/5.845 passage, 1.041 URL; exact-host metadata, retrieved_at provenance, published_at không suy đoán, manifest/hash và validator |
| W3-08 | Query, lọc nguồn/thời gian, rerank và dedup evidence | Quang | Hoàn thành | BM25 candidates → metadata filter → lexical/authority rerank → dedup; top-3 cho 1.080 query dev frozen |
| W4-01 | Streamlit: kết quả nhánh, evidence, nguồn, cache | Quang | Hoàn thành | UI tách verifier/retrieval, citation provenance và source URL/metadata; cache model + JSON response |
| W5-01 | Đo BM25/dense/hybrid/reranker query frozen | Quang | Đang thực hiện | Benchmark dev 1.080 query corpus v2 đã xong: giữ BM25; dense/hybrid giảm quality, reranker bằng BM25 nhưng chậm hơn. Chưa đóng vì thiếu passage-qrels review độc lập để tính nDCG@5 |
| W3-02 / E6 | Calibration PhoBERT và chính sách NEI | Vinh | Hoàn thành (oracle) | Dev gold-evidence OOF: temperature 1,140542; ECE 3,74% → 2,91%; Brier 0,2398 → 0,2376. Không có threshold decisive nào cải thiện Macro-F1; retrieval gating chờ E2E |
| P1 | Tích hợp kỹ thuật verifier PhoBERT | Vinh | Hoàn thành | Pipeline dùng `VerificationResult` không đổi; smoke test đạt |
| W2-05 | Chốt interface Retriever và Verifier; review chung | Vinh + Quang | Hoàn thành | `src/contracts.py`, dependency injection trong pipeline, integration contract và test bàn giao |
| U1 | Hoàn thiện Streamlit | Quang + Vinh | Hoàn thành (2026-10-11) | Label, điểm, trích dẫn, URL; chọn chế độ local / local+web; ví dụ nhanh; hiển thị lý do cặp-tối-thiểu/guard/neo thời gian (`app.py`, `src/system_builder.py`) |
| Q1 | Phân tích lỗi + báo cáo | Vinh + Quang | Hoàn thành phần local của Vinh | W3-04 audit 10/415 lỗi local; web/hybrid error analysis chờ Quang |
| V3 | Bộ 18 claim kiểm thử thủ công + script tái lập | Vinh | Hoàn thành | Có nhãn kỳ vọng, kết quả và ghi rõ giới hạn retrieval mẫu |
| V4 | Đọc thủ công 10 lỗi E2 và phân loại nguyên nhân | Vinh | Hoàn thành | Review tại `REVIEW_10_LOI_E2.md`; không bao gồm retrieval |
| V5 | Chạy E7 biến thể batch ở giới hạn 256 token | Vinh | Hoàn thành | Macro-F1 test 80,25%; giữ E2 (81,07%) |

| R3 | Chốt search provider, allowlist nguồn web và chính sách API key | Quang | Hoàn thành | W2-07: Tavily basic, allowlist 3 host, YAML + chính sách key/quota; validator và test offline. Live retrieval thuộc W3-05 |
| R4 | Web retrieval: lọc domain, trích passage, metadata URL/thời điểm | Quang | Hoàn thành | W3-05: 100% evidence qua allowlist; timeout/cache, metadata và acceptance test |
| R5 | Đánh giá retrieval web/cục bộ/hợp nhất và end-to-end | Vinh + Quang | Hoàn thành local; hợp nhất đã chạy, chưa đo | Local cuối: test Macro-F1 72,31% (+12,8 [+10,0; +15,6] so với W4-02). Fusion web đã nối vào UI/CLI; chưa có tập có nhãn để đo hybrid |
## Mở rộng phạm vi đề tài — roadmap 6 tuần

| P2 | Đánh giá pipeline PhoBERT trên retrieved evidence thật | Vinh + Quang | Hoàn thành local; mở rộng chờ Quang | E11 local BM25→PhoBERT trên 1.076 test; Macro-F1 62,94%, 377 lỗi; chưa có web/hybrid/citation audit thủ công |
| C1 | Chuẩn hóa schema bài viết/claim/evidence và metadata nguồn-thời gian | Vinh + Quang | Hoàn thành | Data contract v1.0, manifest và loader tương thích ngược |
| C2 | Baseline content-only TF-IDF/SVM trên title + body | Vinh | Hoàn thành | E9 VFND article-only, nested source-domain OOF: Macro-F1 77,27%; ROC-AUC 88,21%; risk score không dùng làm evidence |
| C3 | Content-risk PhoBERT/XLM-R | Vinh | Hoàn thành | E10 PhoBERT nested source-domain OOF: Macro-F1 48,59%; ROC-AUC 70,20%; xác minh không rò rỉ domain. Kém E9 nên giữ E9 làm baseline triển khai |
| C4 | Claim decomposition và tổng hợp cấp bài | Vinh | Hoàn thành phần Vinh | Article→claim→claim verdict→aggregation đã chạy qua contract; chờ Quang nối UI/retrieval benchmark để chạy E11 end-to-end |
| C5 | Corpus ingestion, query generation, time/source filter và reranker | Quang | Hoàn thành | W3-07 corpus v2 metadata/dedup; W3-08 filter/reranker/dedup; W5-01 benchmark frozen, giữ BM25 |
| C6 | Temporal/source-held-out test, joint score và citation faithfulness audit | Vinh + Quang | Đang làm | Theo nguồn: xong (`final_source_breakdown_test.json`); 50 citation review chờ người đọc (W5-03a) |
| C7 | Reproducible release | Quang + Vinh | Hoàn thành phần tự động | `scripts/check_release.py` (thư viện, model, Java, SHA-256 dữ liệu, key web), `.gitattributes` eol=lf cho file có hash, pytest ~300 test không cần GPU, demo `scripts/run_demo_cases.py` |

## Hạng mục Vinh bổ sung 2026-09-12

Giữ nguyên mã W{tuần}-{thứ tự} của workbook. Chỉ phần Vinh; không thay đổi hạng mục của Quang. Xem [việc còn lại của Vinh](VIEC_CON_LAI_VINH.md).

| ID | Việc cần làm | Người phụ trách | Trạng thái | Điều kiện hoàn thành |
|---|---|---|---|---|
| W4-07 | Fine-tune RT-V1: tiếp tục E2 trên gold train + 487 cặp AI silver (trọng số 0,5) | Vinh | Hoàn thành | Checkpoint `models/rt_v1_silver/best_model`; dev end-to-end acc 72,31%, Macro-F1 71,35% ở ngưỡng 0,5; sửa đúng 140, làm sai 54, ròng +86 claim |
| W5-04 | Chạy đối chứng gold-only và RT-V2 balanced; chọn checkpoint trên dev | Vinh | RT-V2 xong; gold-only chờ GPU | Hai checkpoint đối chứng cùng seed/cấu hình; bảng so dev tách được cải thiện do nhãn silver. Cần GPU |
| W5-05 | Hiệu chỉnh lại temperature/ngưỡng, fit lại aggregator và khóa config | Vinh | Hoàn thành | Cache dev mới, aggregator fit lại từ logits mới, `configs/config.yaml` đã khóa |
| W5-06 | Phân xử 53 cặp `needs_human_review` và spot-check 50 cặp silver | Vinh | Chờ người đọc (worksheet sẵn) | CSV v2 có nhãn người, tên và lý do; có tỷ lệ đồng thuận người–AI theo từng nhãn |

Phần phân tích lỗi và phân rã chỉ số citation của RT-V1 không mở mã mới — nó nằm trong Q1/W3-04 và được ghi tại [RT_V1_ERROR_CITATION_ANALYSIS.md](RT_V1_ERROR_CITATION_ANALYSIS.md). Audit citation 50 mẫu thuộc W5-03, temporal/source held-out thuộc W5-03 và C6, ablation claim decomposition thuộc E11 — đều đã có mã, không tạo thêm.

## Hạng mục bổ sung 2026-10-04 → 2026-10-11

| ID | Việc cần làm | Người phụ trách | Trạng thái | Điều kiện hoàn thành |
|---|---|---|---|---|
| T1 | Challenge set + test đối kháng; sửa mọi BUG-xx | Vinh | Hoàn thành | 380 claim có nhãn cấu trúc; 20 lỗi đã sửa, 0 xfail ([báo cáo](BAO_CAO_LOI_TU_TEST_DOI_KHANG.md) § 7) |
| T2 | Chọn cách dựng bằng chứng + lớp hậu kiểm trên dev | Vinh | Hoàn thành | Ensemble +2,6 [+0,9; +4,2]; cặp-tối-thiểu trung tính, bật; guard tắt ở local |
| T3 | Chạy test một lần cho cấu hình cuối | Vinh | Hoàn thành | Macro-F1 72,31%; so sánh bootstrap `final_vs_baselines_test.json` |
| W4-04 | Demo các ca có kỳ vọng | Vinh | Hoàn thành | `src/demo_cases.py`, `scripts/run_demo_cases.py`, ví dụ nhanh trong UI |
| W6-01 | Kiểm tra release tái lập | Vinh | Hoàn thành | `scripts/check_release.py [--smoke]` |
| RT-V3 | Hard negative từ train split, huấn luyện, so dev | Vinh | Bundle xong; chờ người spot-check 60 cặp + GPU | `kaggle/retrieval_finetune_v3_hardneg.zip`; quy tắc chọn ở [hướng dẫn](HUONG_DAN_VIEC_CON_LAI.md) § 2.3 |
| W6-02 | Báo cáo tổng kết | Vinh | Hoàn thành (điền tiếp khi có số người/GPU) | [BAO_CAO_TONG_KET.md](BAO_CAO_TONG_KET.md) |

