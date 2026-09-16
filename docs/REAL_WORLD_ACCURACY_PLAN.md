# Đánh giá thực tế và mục tiêu accuracy ≥80%

Ngày rà soát: 2026-09-12 (bản trước: 2026-09-07). **Chưa đạt mục tiêu 80% trên dữ liệu thực tế.**

## Kết quả có thể khẳng định

| Phép đo | Accuracy | Macro-F1 | Giới hạn |
| --- | ---: | ---: | --- |
| Policy theo rank trước đây, test ViFactCheck local | 64,96% | 62,94% | Test đã được xem và dùng phân tích lỗi nhiều lần |
| Policy theo rank, dev | 65,09% | 63,08% | Policy đã được chọn bằng dev |
| AGG-V1 logistic, 5-fold OOF theo URL trên dev | 70,19% | 69,78% | Ước lượng phát triển; PhoBERT và temperature đã dùng dev trước đó |
| AGG-V1 + kiểm tra nhãn passage, dev OOF | 69,91% | 69,26% | Điểm lựa chọn temperature/ngưỡng trên cùng dev OOF, không phải đánh giá độc lập |
| RT-V1 silver, ngưỡng 0,5, end-to-end trên dev | 72,31% | 71,35% | Ứng viên tốt nhất hiện tại; dev đã dùng chọn ngưỡng, chưa có đối chứng gold-only |
| RT-V1 silver, ngưỡng 0,6, end-to-end trên dev | 71,20% | 70,12% | Cùng giới hạn |
| E2 nguyên bản, cùng pipeline, dev | 64,35% | 62,66% | Mốc so sánh cho hai dòng trên |
| Bất kỳ cấu hình nào trên claim thực tế mới | Chưa đo | Chưa đo | Chưa có gold benchmark độc lập |

Ứng viên AGG-V1 đã được fit trên toàn bộ dev sau kiểm tra OOF và được bật trong config bằng `aggregation_model_path`. Đặt trường này thành null để dùng policy rank trước đó. Điểm confidence mới chưa được calibration độc lập; citation là heuristic, chưa phải chứng minh entailment.

Bản hiện tại loại passage điểm không dương hoặc nội dung rỗng trước inference. AGG-V1 chỉ kết luận SUPPORTED/REFUTED khi có passage được verifier chấm cùng nhãn; nếu không trả NEI và không citation. Dev chọn temperature 1,0 và ngưỡng AGG 0,0 (không bật từ chối theo confidence); không ghi nhận cải thiện calibration. Ngưỡng 0,6 trong YAML chỉ áp dụng policy fallback khi AGG không được dùng, bao gồm khi còn dưới ba passage. Xem [tiến độ ưu tiên](PRIORITY_READINESS_PROGRESS.md).

Các con số test lịch sử không đại diện cho runtime AGG-V1. Không chạy lại test cũ để tiếp tục lựa chọn model. Cũng không gọi thí nghiệm này là E11 claim-decomposition ablation của roadmap: các file E11 rank-aware cũ là tên lịch sử đã bị trùng mã.

## Vì sao còn xa 80%

Trong dev có 219/1.080 claim mà cả ba dự đoán nhãn cao nhất của từng cặp claim–passage đều sai. Ngay cả khi biết nhãn vàng và chọn hoàn hảo giữa ba nhãn đó, accuracy chỉ là 79,72%. Đây chỉ là giới hạn chẩn đoán của việc chọn argmax có sẵn, không phải trần cho huấn luyện lại, reranker hay policy đổi nhãn.

Policy rank trước đó chọn citation hạng 1 trong 91,57% trường hợp. AGG-V1 khai thác cả ba vector xác suất và tỷ lệ điểm BM25, dùng logistic C=0,1 cố định. Không dùng URL vàng, evidence annotation hoặc nội dung claim làm feature. Cross-validation tách URL; nhãn validation không dùng fit fold đó. Các đặc trưng và hệ số được xuất JSON; kết quả runtime được đối chiếu với sklearn trên toàn dev.

## Dữ liệu để cải thiện verifier

`data/evaluation/train_retrieved_pair_review.csv` chứa 540 cặp của 180 claim train, 60 claim mỗi nhãn. Corpus dùng để lấy candidate chỉ có URL train (4.204 passage), loại URL dev/test. Không sửa retriever/corpus của Quang.

Reviewer cần đọc claim và passage, điền `reviewed_pair_label` bằng SUPPORTED/REFUTED/NOT_ENOUGH_INFO, tên và lý do. `original_gold_pair_label` chỉ áp dụng cho evidence annotation gốc. Không copy nhãn đó sang mọi passage, không gán NEI chỉ vì khác URL. CSV gốc giữ pending; bản [AI-review riêng](REVIEW_TRAIN_PAIRS_AI_V1.md) đã đọc đủ 540 cặp, đề xuất 487 nhãn silver và tách 53 cặp chưa chắc. Silver chỉ được xuất khi bật lựa chọn rõ ràng, không xem là human-approved gold. Xem [hướng dẫn RT-V1](KAGGLE_RETRIEVAL_FINETUNE_V1.md).

Cập nhật 2026-09-12: thí nghiệm gold + silver trọng số 0,5 **đã chạy**, checkpoint tại `models/rt_v1_silver/best_model`, kết quả dev ở bảng trên. Hai việc còn thiếu để kết luận về nhãn silver: **lượt đối chứng gold-only** (chưa chạy, nên chưa tách được nguyên nhân cải thiện) và **tỷ lệ đồng thuận người–AI** trên mẫu silver (chưa có; worksheet spot-check 50 cặp đã chuẩn bị tại `data/evaluation/train_pair_silver_spotcheck_v1_worksheet.csv`). Bundle RT-V2 balanced đã đóng gói nhưng chưa train.

Sau review: dùng các cặp train đã xác nhận cùng gold pairs train để fine-tune; giữ dev để chọn checkpoint theo Macro-F1 end-to-end và recall REFUTED. Không huấn luyện trên dev. Chỉ dùng test thực tế mới sau khi đóng băng toàn bộ pipeline.

## Benchmark thực tế cần thu thập

Đề xuất tối thiểu 300 claim mới, có ngày quan sát và nhóm chủ đề, phản ánh phân bố sử dụng dự kiến. Giữ nguyên cả claim khó, thiếu evidence, ngoài corpus; báo cáo riêng nhóm này. Không chọn mẫu theo việc model trả lời đúng. Tách nhóm sự kiện khỏi train/dev và hạn chế nhiều biến thể cùng một sự kiện. Một tập balanced bổ sung có thể dùng đánh giá từng nhãn, nhưng không thay thế tập đại diện thực tế.

Hai reviewer độc lập đọc nguồn và thống nhất nhãn cùng thời điểm đánh giá. Khóa gold CSV bằng SHA-256 trước khi chạy model. Reviewer citation đánh giá passage thực được model trích dẫn; NEI không đồng nghĩa câu khẳng định sai. Gold CSV phải có: claim_id, claim, gold_label, topic_group, source_url, observed_at, reviewer_1, reviewer_2, review_status.

Pipeline nhận claim mà không được nhận nhãn/URL vàng. Predictions CSV: claim_id, predicted_label, citation_faithful (true/false/unknown). Lỗi runtime và abstain phải giữ lại. Bộ chấm `scripts/evaluate_real_world_predictions.py` báo accuracy toàn tập, Macro-F1, coverage, accuracy trên phần đã trả lời, citation correctness và Wilson 95%. Wilson giả định mẫu độc lập; nhiều claim cùng sự kiện cần bổ sung khoảng tin cậy theo nhóm.

Mục tiêu ≥80% áp dụng accuracy trên **toàn bộ** claim. Không lấy accuracy riêng câu dễ/đã trả lời để gọi toàn hệ thống đạt 80%. Báo kèm F1/recall từng nhãn và coverage citation audit. Chưa có bằng chứng đạt mục tiêu cho đến khi bộ gold thực tế được hoàn thiện và chạy đánh giá.

## Artifact và lệnh

- `outputs/metrics/accuracy_gap_dev_audit.json`: chẩn đoán và kết quả từng fold.
- `outputs/predictions/accuracy_gap_dev_oof.csv`: dự đoán ngoài fold.
- `models/aggregation/dev_logistic_v1.json`: mô hình tổng hợp phát triển.
- `outputs/metrics/train_retrieved_pair_review_manifest.json`: manifest bộ review train.

```powershell
py -3.13 scripts/audit_accuracy_gap.py
py -3.13 scripts/calibrate_aggregation_guard.py
py -3.13 scripts/evaluate_real_world_predictions.py --gold PATH_TO_LOCKED_GOLD.csv --predictions PATH_TO_PREDICTIONS.csv --expected-gold-sha256 PRECOMMITTED_HASH --output outputs/metrics/real_world_v1.json
```

Hai lệnh đầu chỉ dùng cache dev, phải chạy theo thứ tự này: audit xuất lại model gốc, calibrate bổ sung cấu hình guard. Lệnh đánh giá thực tế chỉ chấm khi gold đã duyệt và hash khớp. Hiện chưa có file gold thực tế đã duyệt.
