# Kế hoạch web retrieval có kiểm soát

**Trạng thái: Planned — chưa có mã nguồn, API key hay truy vấn web trong ứng dụng.**

## Mục tiêu

Bổ sung evidence thời gian thực từ các website uy tín, nhưng vẫn giữ kho evidence cục bộ là nguồn nền. Mỗi kết luận từ web phải hiển thị URL, domain, tiêu đề và thời điểm truy cập.

## Nguyên tắc nguồn

1. Chỉ nhận kết quả thuộc allowlist do nhóm quản lý; mặc định ưu tiên cổng cơ quan nhà nước, tổ chức quốc tế và báo chí uy tín đã được chấp thuận.
2. Không lấy kết quả từ blog cá nhân, mạng xã hội, trang tổng hợp không rõ tác giả hoặc domain ngoài allowlist.
3. Không coi thứ hạng tìm kiếm là bằng chứng. Chỉ passage trích trực tiếp từ trang được duyệt mới được gửi cho verifier.
4. Lưu snapshot/metadata tối thiểu để truy vết: `title`, `url`, `domain`, `fetched_at`, `source_tier` và passage.

## Luồng dự kiến

```text
Claim
 ├─ BM25 kho evidence cục bộ
 └─ Search provider → lọc allowlist → tải trang → trích passage
                         │
                         ▼
             hợp nhất và khử trùng evidence
                         │
                         ▼
                   PhoBERT verifier
                         │
                         ▼
 nhãn + confidence + citation + thời điểm truy cập
```

## Các bước triển khai sau khi được duyệt

1. Chốt nhà cung cấp search API, quota, chi phí và vị trí lưu API key trong biến môi trường.
2. Chốt allowlist theo nhóm nguồn: chính phủ, tổ chức quốc tế, báo chí uy tín.
3. Xây web retriever: timeout, retry giới hạn, tôn trọng điều khoản trang, lọc domain, tải trang và trích main text.
4. Chia passage, khử URL trùng và xếp hạng cùng evidence cục bộ.
5. Hiển thị nguồn web trong UI với URL và thời điểm truy cập; cho phép tắt web retrieval.
6. Đo Recall@3/5, MRR, latency; sau đó mới đo Macro-F1 end-to-end với evidence thực truy hồi.

## Quy tắc kết luận

- Nếu không có passage web/cục bộ liên quan đủ mạnh, trả `NOT_ENOUGH_INFO`.
- Không thay nhãn chỉ vì có nhiều kết quả search cùng chiều.
- Evidence cục bộ đã kiểm duyệt được ưu tiên hơn evidence web trong cùng mức liên quan.
- Các claim thuộc lĩnh vực nhạy cảm (y tế, pháp luật, tài chính) ưu tiên nguồn cơ quan có thẩm quyền; UI luôn hiển thị nguồn để người dùng tự kiểm tra.

## Tiêu chí hoàn thành

| Hạng mục | Điều kiện |
|---|---|
| An toàn nguồn | 100% evidence web trả về thuộc allowlist |
| Minh bạch | Mỗi evidence có URL, domain, title và thời điểm truy cập |
| Chất lượng retrieval | Có Recall@3, Recall@5, MRR và latency trên tập query cố định |
| Chất lượng end-to-end | Báo cáo tách oracle evidence, retrieval và end-to-end |
| Tái lập | Có cấu hình provider/allowlist versioned; API key không nằm trong Git |

## Liên kết roadmap 6 tuần

Web retrieval là một nhánh của roadmap 6 tuần, không thay thế corpus cục bộ hay nhánh content-risk. Xem [ma trận yêu cầu](MA_TRAN_YEU_CAU_DE_TAI.md) để biết task, thí nghiệm và tiêu chí đánh giá liên quan.
