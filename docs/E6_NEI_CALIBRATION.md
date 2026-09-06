# E6 — Calibration PhoBERT và chính sách NEI

E6 hiệu chỉnh **verifier** PhoBERT E2 trên 1.080 cặp claim–gold-evidence của dev. Đây không phải metric retrieval hay end-to-end; test không được dùng để chọn temperature hoặc threshold.

## Protocol

- 3-fold `StratifiedGroupKFold` theo `Url` trên dev.
- Mỗi fold fit temperature bằng hai phần fold, sau đó tạo xác suất OOF cho phần còn lại.
- Chọn ngưỡng decisive trên các xác suất OOF bằng Macro-F1; fit temperature cuối cùng trên toàn dev để dùng runtime.
- Artifact: `outputs/metrics/e6_e2_nei_calibration.json` và `outputs/predictions/e6_e2_dev_calibration.csv`.

## Kết quả

| Chỉ số | Trước temperature | OOF temperature |
|---|---:|---:|
| Macro-F1 | 85,01% | 85,01% |
| ECE (10 bins) | 3,74% | 2,91% |
| Multiclass Brier | 0,2398 | 0,2376 |

Temperature runtime fit trên toàn dev là **1,140542**. Grid threshold chọn **0,0**: không có ngưỡng confidence quyết đoán dương nào cải thiện Macro-F1 OOF. F1 NEI theo policy OOF là **89,33%**.

## Chính sách runtime

`PhoBERTFactChecker` nay xét cả ba nhãn của mọi evidence. Nếu NEI có confidence cao nhất, nó được giữ; không còn loại NEI chỉ vì một evidence khác có `SUPPORTED`/`REFUTED`. Điều này sửa lỗi logic trước đây: NEI `0,99` có thể bị `SUPPORTED 0,34` ghi đè.

Không diễn giải `threshold=0,0` là pipeline đã giải quyết abstention với evidence truy hồi. E6 dùng gold evidence. Sau đó E11 chọn riêng trên dev end-to-end policy runtime `rank_bias=1,0`, `threshold=0,60` và xác nhận trên test; xem [E11](E11_RANK_AWARE_POLICY.md). E6 vẫn là artifact calibration oracle, không phải policy selection end-to-end.
