# Kịch bản demo của Vinh

## Mục tiêu

Chứng minh phần verifier PhoBERT chạy được với evidence có sẵn, đồng thời nêu rõ giới hạn: đây chưa phải đánh giá retrieval end-to-end.

## Chuẩn bị

```powershell
python scripts/evaluate_manual_claims.py
streamlit run app.py
```

## Ba tình huống trình diễn

| Claim | Kỳ vọng | Evidence |
|---|---|---|
| Chưa có thông báo chính thức về việc thay đổi lịch học trên phạm vi toàn quốc. | SUPPORTED | `sample_003_p01` |
| Đã có thông báo chính thức thay đổi lịch học trên phạm vi toàn quốc. | REFUTED | `sample_003_p01` |
| Ngày mai Hà Nội sẽ có mưa lớn. | NOT_ENOUGH_INFO | Không có evidence cụ thể |

## Cách trình bày

1. Nhập claim, đọc nhãn, confidence và evidence được chọn.
2. Mở evidence để người xem kiểm tra lập luận, không chỉ nhìn nhãn.
3. Nêu rõ Macro-F1 E2 81,07% đo trên **gold evidence** trong group split; kết quả app với kho evidence thật sẽ được đánh giá sau khi Quang hoàn tất retrieval.
