# RT-V1 — Phân tích lỗi và phân rã chỉ số citation

Ngày: 2026-09-12. Phạm vi: đọc lại `outputs/predictions/rt_v1_*.csv` đã có trên dev 1.080 mẫu. **Không chạy lại model, không mở test, không sửa retriever/corpus.** Mọi số dưới đây là số dev; dev đã được dùng để chọn ngưỡng 0,5 nên đây không phải phép đo độc lập.

Artifact máy đọc: `outputs/metrics/rt_v1_error_citation_analysis.json` (kèm SHA-256 của ba file predictions đầu vào).

## 1. Citation không hề xấu đi — chỉ số cũ bị nhiễu bởi NEI

Trước đó ghi nhận citation URL-match tụt từ 67,50% xuống 57,59% sau RT-V1 và xem đó là đánh đổi. Phân rã lại cho thấy **không có đánh đổi**:

| Cấu hình | Tỷ lệ trả NEI | Citation URL-match (mọi claim) | Citation URL-match (chỉ kết luận quyết đoán) | Số claim quyết đoán |
| --- | ---: | ---: | ---: | ---: |
| E2 control | 30,28% | 67,50% | **96,81%** | 753 |
| RT-V1 silver | 43,89% | 54,72% | **97,52%** | 606 |
| RT-V1 tuned (ngưỡng 0,5) | 40,93% | 57,59% | **97,49%** | 638 |

Nguyên nhân: mọi dự đoán NEI đều không sinh citation (đã kiểm tra: 0 dự đoán NEI có citation, 0 kết luận quyết đoán thiếu citation ở cả ba cấu hình), nhưng mẫu số của chỉ số cũ tính cả chúng. RT-V1 trả NEI nhiều hơn nên chỉ số tổng giảm, trong khi chất lượng citation trên phần thực sự có citation **tăng nhẹ**, 96,81% → 97,49%.

**Kết luận:** đây là lỗi định nghĩa metric, không phải hồi quy chất lượng. Nên báo cáo hai số tách nhau — tỷ lệ quyết đoán (coverage) và citation URL-match trên phần quyết đoán — thay vì một số gộp. Lưu ý URL-match vẫn chỉ là proxy; nó không chứng minh passage được trích dẫn đủ để entail claim. Việc đó thuộc audit thủ công 50 citation, chưa làm.

## 2. RT-V1 sửa được gì và làm hỏng gì

So khớp theo `source_row_id` giữa E2 control và RT-V1 tuned:

- Sửa đúng: **140** claim.
- Làm sai đi: **54** claim.
- Ròng: **+86** claim đúng (lỗi 385 → 299).

Các chuyển dịch lớn nhất:

| Nhãn vàng | E2 dự đoán | RT-V1 dự đoán | Số claim | Đánh giá |
| --- | --- | --- | ---: | --- |
| NOT_ENOUGH_INFO | SUPPORTED | NOT_ENOUGH_INFO | 71 | Sửa đúng — đây là lỗi nặng nhất của E2 |
| REFUTED | SUPPORTED | NOT_ENOUGH_INFO | 31 | Vẫn sai, nhưng bớt nguy hiểm |
| REFUTED | SUPPORTED | REFUTED | 30 | Sửa đúng |
| REFUTED | NOT_ENOUGH_INFO | REFUTED | 22 | Sửa đúng |
| SUPPORTED | SUPPORTED | NOT_ENOUGH_INFO | 21 | **Làm sai đi** — giá phải trả của lệch NEI |
| NOT_ENOUGH_INFO | REFUTED | NOT_ENOUGH_INFO | 16 | Sửa đúng |
| REFUTED | REFUTED | NOT_ENOUGH_INFO | 14 | **Làm sai đi** |

E2 có xu hướng khẳng định bừa (100 claim NEI bị gọi là SUPPORTED). RT-V1 sửa phần lớn khuynh hướng đó. Chi phí là 35 claim vốn đúng bị đẩy về NEI — phù hợp với việc bộ silver lệch 82,3% NEI. Bản RT-V2 balanced được đóng gói chính là để kiểm tra giả thuyết này.

## 3. Lỗi còn lại của RT-V1 tuned: 299 claim

| Nhóm triage | Số lỗi | Tỷ trọng |
| --- | ---: | ---: |
| nei_decision | 195 | 65,2% |
| verifier_with_gold_url | 97 | 32,4% |
| retrieval_url_miss | **7** | **2,3%** |

**Chỉ 7/299 lỗi là do retrieval không lấy được URL vàng.** Nút thắt nằm hoàn toàn ở verifier và chính sách quyết định, không ở retrieval. Đây là căn cứ để nói rằng phần retrieval nâng cao chưa làm (dense, rerank, web) sẽ không tự nó nâng accuracy lên 80%, và ngược lại, không nên đổ lỗi tồn đọng cho retrieval.

Phân bố lỗi theo nhãn:

| Nhãn vàng → dự đoán | Số claim |
| --- | ---: |
| REFUTED → NOT_ENOUGH_INFO | 98 |
| REFUTED → SUPPORTED | 77 |
| SUPPORTED → NOT_ENOUGH_INFO | 47 |
| NOT_ENOUGH_INFO → REFUTED | 28 |
| NOT_ENOUGH_INFO → SUPPORTED | 28 |
| SUPPORTED → REFUTED | 21 |

**175/299 lỗi (58,5%) có nhãn vàng REFUTED.** Với một hệ thống chống tin sai thì đây là nhóm lỗi đắt nhất.

## 4. Nhóm REFUTED → NEI không sửa được bằng ngưỡng

Kiểm tra riêng 98 claim REFUTED bị trả NEI:

- URL vàng nằm trong top-k: **96,9%** — không phải lỗi retrieval.
- Confidence NEI trung bình: **0,87** — model tự tin chọn NEI, không phải rơi xuống NEI vì dưới ngưỡng quyết đoán.

Nghĩa là hạ `decisive_min_confidence` thêm nữa **không** chạm tới nhóm này. Đây là vấn đề dữ liệu huấn luyện và khả năng bắt mâu thuẫn của verifier, không phải vấn đề policy. Hướng xử lý nên là: RT-V2 balanced, bổ sung cặp REFUTED có mâu thuẫn rõ (đảo số, sai ngày, phủ định), và đọc tay một mẫu nhóm này để xem mâu thuẫn nằm ở mức nào (số liệu, thời gian, thực thể).

## 5. Giới hạn

- Toàn bộ số liệu trên là dev, và dev đã tham gia chọn temperature, ngưỡng và aggregator. Không dùng làm bằng chứng chất lượng độc lập.
- Chưa có đối chứng gold-only, nên chưa tách được phần cải thiện do nhãn silver với phần do huấn luyện thêm.
- URL-level vẫn là proxy; chưa có qrels passage-level và chưa có audit citation thủ công.
- Không có gì ở đây khẳng định hệ thống đạt mục tiêu 80% ngoài thực tế.
