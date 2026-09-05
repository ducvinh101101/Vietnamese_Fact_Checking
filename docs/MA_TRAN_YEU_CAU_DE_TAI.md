# Ma trận yêu cầu đề tài và kế hoạch triển khai

Tài liệu này là điểm tham chiếu cho phạm vi đầy đủ của đề tài. Trạng thái **planned** không có nghĩa là đã được cài đặt.

| Yêu cầu đề tài | Task / thí nghiệm | Chủ trì | Trạng thái |
|---|---|---|---|
| Phân tích nội dung title + body | C2, C3; E9, E10 | Vinh | E9/E10 hoàn thành; giữ E9 vì E10 Macro-F1 thấp hơn |
| Tách claim nguyên tử | C4; W3-06; E11 | Vinh | Planned |
| Tổng hợp verdict cấp bài | W4-06; E11 | Vinh + Quang | Planned |
| Schema article/evidence có metadata nguồn-thời gian | C1; W1-06 | Vinh + Quang | Hoàn thành |
| Corpus passage và khử trùng | C5; W3-07 | Quang | Planned |
| BM25, dense, hybrid, reranker | W2-01, W2-04, W3-08, W5-01; E3, E4, E5, E12 | Quang | Planned |
| Web retrieval allowlist | R3, R4; W2-07, W3-05; E8 | Quang | Planned |
| Claim–evidence verifier | E1, E2, E7; P1 | Vinh | E2 hoàn thành |
| Calibration và NEI | E6; W3-02 | Vinh | Planned |
| Evaluation retrieval | R2, W5-01 | Quang + Vinh | Planned |
| Evaluation end-to-end và citation | P2, R5, C6; W5-02/W5-03; E13 | Vinh + Quang | Planned |
| Tái lập/release | C7; W1-07, W6-01 | Quang + Vinh | Planned |
| Demo bài viết hoàn chỉnh | W6-03 | Quang + Vinh | Planned |

## Cách đọc metric

- E1/E2/E7: verifier với **gold evidence**, không đại diện cho RAG end-to-end.
- E3/E4/E5/E8/E12: retrieval; cần Recall@k, MRR, nDCG và latency.
- E13: đánh giá cuối gồm verdict, evidence/citation, calibration và temporal/source generalization.
- C2/C3: content-risk; không được trình bày như bằng chứng chứng minh claim đúng/sai.
