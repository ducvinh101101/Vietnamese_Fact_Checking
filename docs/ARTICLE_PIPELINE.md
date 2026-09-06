# Luồng kiểm chứng cấp bài — phần Vinh

`ArticleFactCheckingPipeline` đưa các component đã có vào một luồng có thể gọi được:

```text
Article
  → ClaimDecomposer
  → ClaimRunner.run(claim) cho từng claim
  → giữ verdict + evidence_ids của từng claim
  → ArticleAggregator
```

`ClaimRunner` là interface `run(claim) -> (VerificationResult, list[RetrievedEvidence])`; vì vậy có thể dùng `FactCheckingPipeline` hiện tại hoặc implementation mới của Quang mà không sửa component này.

## Bảo đảm

- Claim vẫn giữ `claim_id` và `article_id` của bài nguồn.
- Mỗi verdict chỉ được giữ citation thuộc evidence mà claim đó đã truy xuất.
- Output luôn hiển thị verdict từng claim trước khi có assessment cấp bài.
- `HAS_REFUTED_CLAIMS` chỉ nói có claim bị bác bỏ; không kết luận toàn bài là giả.

## Ranh giới còn lại

Module chưa gọi web retrieval, chưa hiển thị UI và chưa trộn E9 content-risk. Content-risk phải được trình bày là tín hiệu riêng, không được biến thành evidence hoặc override verdict claim. E11/W4-05 sẽ đánh giá luồng này trên protocol end-to-end sau khi retrieval của Quang có corpus/query benchmark hoàn chỉnh.
