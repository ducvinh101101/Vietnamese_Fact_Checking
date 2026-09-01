# E7 — PhoBERT-base, biến thể batch ở giới hạn 256 token

Kaggle hiện giới hạn `max_length=256`, nên E7 không kiểm tra ngữ cảnh dài hơn. E7 giữ dữ liệu, group split, seed, model và max length như E2; chỉ dùng train batch 8 với gradient accumulation 2 (effective batch vẫn là 16).

## Kết quả

E7 đạt Dev Macro-F1 84,18% và Test Macro-F1 80,25%, thấp hơn E2 lần lượt 0,83 và 0,82 điểm phần trăm. Giữ E2 làm model tốt nhất.

Tệp chạy và kết quả: `train_phobert_e7_long_context.py`, `e7_phobert_metrics.json`, `e7_phobert_test_predictions.csv`. Tên file được giữ để không phá vỡ đường dẫn đã dùng; nội dung không còn là thí nghiệm long context.
