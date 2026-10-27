# Báo cáo tiến độ — Dự án XLNNTN

Cập nhật: 2026-10-11. Báo cáo kết quả để trình bày: [BAO_CAO_TONG_KET.md](BAO_CAO_TONG_KET.md).

## Trạng thái 2026-10-11

- **Phần code đã hoàn thiện.**
  - Giao diện có hai chế độ: kho local (đã đo) và local + web (neo thời gian).
  - CLI dựng chung với giao diện.
  - 20 lỗi đối kháng đã sửa.
  - Có release check và demo W4-04.
- **Số cuối (test, chạy một lần):** Macro-F1 **72,31%**, hơn baseline W4-02 **+12,8 điểm [+10,0; +15,6]**. Mọi lựa chọn đều làm trên dev.
- **Còn lại chỉ là việc cần người hoặc GPU** ([hướng dẫn](HUONG_DAN_VIEC_CON_LAI.md)):
  - đọc tay W5-06 và W5-03a;
  - spot-check hard negative RT-V3;
  - chạy gold-only control và RT-V3 trên GPU;
  - bộ gold thực tế ≥ 300 claim.

---

## Lịch sử: bản 2026-09-30


Cập nhật: 2026-09-30. Nguồn: `KE_HOACH_TRIEN_KHAI_2_NGUOI.xlsx` (đối chiếu bằng chứng thật trong repo).

## Tổng quan

| Nhóm | Hoàn thành | Đang làm | Chưa bắt đầu | Tổng | Tỷ lệ |
|---|---:|---:|---:|---:|---:|
| Toàn dự án | 29 | 3 | 9 | 41 | **71%** |
| Vinh (dữ liệu & mô hình) | 17 | 3 | 5 | 25 | 68% |
| Quang (retrieval & sản phẩm) | 12 | 0 | 4 | 16 | 75% |

Theo tuần: **T1–T3 hoàn thành 100%** (25/25). T4 còn dở (3 xong / 2 đang làm / 2 chưa). T5 gần như chưa (1/6). T6 chưa (0/3).

## Tình hình hai nhánh

**Nhánh Quang (retrieval & sản phẩm) — 75%, phần khó đã qua.** Đã xong web retrieval an toàn (W3-05), corpus v2 có metadata (W3-07), rerank (W3-08), pipeline JSON contract (W3-03), và Streamlit UI (W4-01). Còn: demo 3 case (W4-04), benchmark retrieval Recall/MRR/nDCG (W5-01), release tái lập (W6-01), đóng gói demo (W6-03).

**Nhánh Vinh (dữ liệu & mô hình) — 68%, đang là đường tới hạn.** Verifier và toàn bộ nghiên cứu cốt lõi đã xong; phần còn lại là chạy đánh giá cuối và đọc tay.

## Kết quả nổi bật đã đạt

- **Verifier**: E2 PhoBERT oracle Macro-F1 81,07% (hơn baseline E1 +40,9 điểm).
- **End-to-end local**: BM25→PhoBERT Macro-F1 62,94% (test). Khoảng cách oracle→E2E 18 điểm — nút thắt nằm ở verifier/dữ liệu, không phải retrieval (chỉ 7/299 lỗi do retrieval).
- **RT-V2 balanced (mới, 30/09)**: end-to-end dev **F1 REFUTED 64,23%** (vượt RT-V1 61,40%) và **giảm lệch NEI còn 28,52%** (RT-V1 40,93%), Macro-F1 gần hòa. → **Chọn RT-V2** làm checkpoint chính.
- **Retrieval**: giữ BM25 (dense/RRF không vượt); URL Recall@3 98,14%.
- **Content-risk E9**: baseline Macro-F1 77,27%, đã nối code cấp bài, tách khỏi verdict.

## Việc còn lại

### Của Vinh
| Mã | Việc | Trạng thái | Chặn bởi |
|---|---|---|---|
| W5-05 | Khóa RT-V2 vào config | Chưa | — (5 dòng YAML) |
| W5-06 | Phân xử + spot-check nhãn silver | Chưa | đọc tay |
| W5-03 | Audit citation + temporal/source | Chưa | đọc tay |
| W4-05 | Đo reranked/hybrid end-to-end | Chưa | script sẵn; hybrid chờ fusion |
| W4-06 | Fit + nối content-risk | Đang làm | chạy 1 lệnh fit + UI |
| W4-03 | README + báo cáo | Đang làm | — |
| W6-02 | Ablation/giới hạn | Đang làm | điền số cuối |

Ngoài kế hoạch: lượt **gold-only control** (tách đóng góp nhãn silver) và **bộ gold thực tế ≥300 claim** (C6/E13, cần 2 reviewer, điều kiện để tuyên bố mốc 80%).

### Của Quang
W4-04 demo, W5-01 benchmark retrieval, W6-01 release, W6-03 đóng gói. Và **fusion local+web** (chưa có) — chặn tầng hybrid end-to-end của W4-05.

## Rủi ro

1. **Chưa có phép đo độc lập.** Mọi số hiện tại là dev/test đã xem nhiều lần. Mục tiêu ≥80% thực tế chưa đo được — cần bộ gold mới.
2. **Fusion local+web chưa làm** — chặn demo bài-viết-có-web và W4-05 đầy đủ.
3. **Workbook từng bị lưu đè bằng bản cũ** nhiều lần (thư mục "Claude outputs"). Đã dọn; giữ một bản duy nhất ở gốc repo.

## Ưu tiên tuần này (Vinh)
1. Khóa RT-V2 vào config (W5-05) — 5 phút.
2. Đọc 3 worksheet (W5-06 + W5-03a) — ra kappa nhãn silver + citation faithfulness.
3. Chạy reranked end-to-end (W4-05/W5-02) — 2 lệnh.
4. Điền số cuối vào báo cáo (W6-02/W4-03).
