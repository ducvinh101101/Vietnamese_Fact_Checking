# Tiến độ ưu tiên sẵn sàng thực tế

Ngày: 2026-09-12 (bản trước: 2026-09-07). Phạm vi: verifier, cách hiển thị kết quả và dữ liệu train của Vinh; không sửa retriever của Quang.

> Cập nhật 2026-09-12: RT-V1 **đã được huấn luyện** và đã có ba lượt đánh giá dev. Các câu "chưa huấn luyện lại" ở mục 3 thuộc mốc 2026-09-07 và được bổ sung tại mục 4 bên dưới. Xem [phân tích lỗi và citation RT-V1](RT_V1_ERROR_CITATION_ANALYSIS.md) và [việc còn lại của Vinh](VIEC_CON_LAI_VINH.md).

## 1. Chặn kết luận và citation thiếu cơ sở — đã triển khai

- Loại passage điểm BM25 không dương hoặc nội dung rỗng trước khi chấm PhoBERT. Điểm NaN/vô hạn bị từ chối.
- Không còn passage: trả NOT_ENOUGH_INFO, điểm quy ước 0, không citation, không gọi inference. Điểm 0 này không phải xác suất NEI.
- Khi dùng AGG-V1, kết luận SUPPORTED/REFUTED phải có một passage có argmax nhãn tương ứng; chỉ chọn citation trong nhóm đó. Nếu không có, trả NEI và không citation.
- Đây chỉ là kiểm tra nhất quán giữa aggregate và verifier, không chứng minh passage thật sự đủ bằng chứng. Điểm BM25 dương cũng không đảm bảo liên quan ngữ nghĩa.

Kiểm tra pipeline PhoBERT thật với `zxqv987xyz qqqzzzxvv`: ba điểm retrieval đều 0, kết quả NEI, confidence 0 và danh sách citation rỗng.

## 2. Hiển thị và khảo sát ngưỡng — đã triển khai, chưa xác nhận calibration thực tế

UI gọi confidence là **Điểm mô hình**, không phải xác suất thông tin đúng; không hiển thị điểm cho NEI. Tách đoạn được trích dẫn khỏi các đoạn tìm thấy khác; ẩn đoạn điểm 0. Giới hạn ô nhập 2.000 ký tự là giới hạn giao diện, không phải bảo đảm toàn bộ nội dung được model xử lý (model vẫn có truncation).

`scripts/calibrate_aggregation_guard.py` chọn temperature và ngưỡng bằng dự đoán dev OOF theo URL, không đọc test. Kết quả được lưu ở `outputs/metrics/aggregation_guard_dev.json`.

| Cấu hình | Accuracy | Macro-F1 |
| --- | ---: | ---: |
| AGG trước guard | 70,19% | 69,78% |
| Guard, ngưỡng 0,0 được chọn | 69,91% | 69,26% |
| Guard, ngưỡng 0,6 | 65,74% | 64,96% |

Guard từ chối 52 kết luận trên dev ở ngưỡng được chọn. Chấp nhận giảm nhẹ điểm phát triển để tránh citation không cùng nhãn. Temperature được chọn là 1,0: không cải thiện log-loss. Ngưỡng 0,0 nghĩa là **chưa bật từ chối theo confidence cho AGG**. Ngưỡng 0,6 trong YAML thuộc policy fallback, không phải ngưỡng AGG.

Các điểm trên là điểm chọn cấu hình trên dev, không phải accuracy thực tế và không phải phép đo độc lập. Base verifier cũng đã dùng dev trước đó. Chưa có bằng chứng đạt mục tiêu 80%.

## 3. Cửa kiểm tra dữ liệu huấn luyện — đã triển khai, chờ review

CSV gốc `data/evaluation/train_retrieved_pair_review.csv` vẫn giữ pending để bảo toàn nguồn. Đã hoàn tất lượt AI-review riêng cho 540 cặp: 487 nhãn silver, 53 cặp cần người phân xử. Không có human approval mới. Xem [review AI v1](REVIEW_TRAIN_PAIRS_AI_V1.md) và [hướng dẫn fine-tune RT-V1](KAGGLE_RETRIEVAL_FINETUNE_V1.md).

Sau khi có review:

```powershell
py -3.13 scripts/export_reviewed_training_pairs.py
```

Script chỉ xuất cặp approved, đối chiếu claim thuộc train và passage khớp corpus, loại nguy cơ URL dev/test, kiểm tra nhãn và thông tin người duyệt. Đầu ra mặc định là `data/processed/reviewed_retrieval/train_pairs.parquet` kèm manifest SHA-256; không ghi đè file đã tồn tại. Đây là dữ liệu bổ sung, cần kết hợp với gold train trong bước fine-tuning, không dùng làm test.

Exporter mặc định vẫn chặn CSV gốc vì chưa có cặp approved. Bản silver được xuất riêng với `--allow-ai-reviewed`, không nhận nhóm cần phân xử. Chưa huấn luyện lại hoặc khẳng định tăng accuracy.

## 4. RT-V1 — đã huấn luyện, chưa khóa vào runtime

Cập nhật 2026-09-12. Checkpoint tại `models/rt_v1_silver/best_model`. Ba lượt đánh giá end-to-end trên **dev** (BM25 top-3 → PhoBERT, không truyền nhãn/URL vàng vào pipeline):

| Cấu hình dev | Accuracy | Macro-F1 | F1 REFUTED | Tỷ lệ trả NEI |
| --- | ---: | ---: | ---: | ---: |
| E2 nguyên bản (control) | 64,35% | 62,66% | 52,50% | 30,28% |
| RT-V1 silver, ngưỡng 0,6 | 71,20% | 70,12% | 59,60% | 43,89% |
| RT-V1 silver, ngưỡng 0,5 | **72,31%** | **71,35%** | **61,40%** | 40,93% |

So khớp từng claim: RT-V1 sửa đúng 140, làm sai 54, ròng +86 (lỗi 385 → 299).

Ba điều phải nói kèm:

- Dev đã được dùng để chọn ngưỡng 0,5, nên đây **không** phải phép đo độc lập.
- **Chưa có lượt đối chứng gold-only.** `models/` chỉ có `rt_v1_silver`; cái đang gọi là control là E2 nguyên bản chứ không phải E2 được train tiếp trên gold. Vì vậy chưa tách được phần cải thiện do nhãn silver với phần do huấn luyện thêm.
- `configs/config.yaml` vẫn trỏ `models/e2_phobert` + AGG-V1. AGG-V1 fit trên logits E2 nên không tái dùng cho checkpoint mới; phải fit lại từ cache dev mới trước khi đổi runtime.

Về citation: mức giảm 67,50% → 57,59% **không phải hồi quy chất lượng**. Mọi dự đoán NEI đều không sinh citation nhưng vẫn nằm trong mẫu số. Tính riêng trên các kết luận quyết đoán, citation URL-match là 96,81% → 97,49%. Chi tiết ở [RT_V1_ERROR_CITATION_ANALYSIS.md](RT_V1_ERROR_CITATION_ANALYSIS.md).

## Kiểm thử và phần tiếp theo

- 74 test tự động đều pass, gồm trường hợp không có hit phù hợp, loại hit điểm 0, NEI không citation, guard và kiểm tra export.
- Smoke pipeline thật xác nhận nhánh không có evidence. Không xem một smoke case là đánh giá chất lượng tổng thể.
- Tiếp theo (cập nhật 2026-09-12): đối chứng gold-only và RT-V2 balanced → chọn checkpoint bằng dev end-to-end → re-calibrate và fit lại aggregator từ cache mới → khóa pipeline → đánh giá gold thực tế mới có người duyệt. Danh sách đầy đủ kèm runbook ở [VIEC_CON_LAI_VINH.md](VIEC_CON_LAI_VINH.md). Web retrieval và tích hợp cấp bài vẫn là các hạng mục riêng, chưa được hoàn thành bởi đợt sửa này.
- Phân tích lỗi RT-V1 cho thấy chỉ 7/299 lỗi còn lại đến từ retrieval; 175/299 lỗi có nhãn vàng REFUTED. Nhóm REFUTED → NEI có URL vàng trong top-k 96,9% và confidence NEI trung bình 0,87, nên **không sửa được bằng cách hạ ngưỡng quyết đoán**.
