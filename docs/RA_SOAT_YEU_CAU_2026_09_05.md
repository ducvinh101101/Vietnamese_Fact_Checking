# Rà soát các đầu việc theo yêu cầu đề tài — 05/09/2026

## Căn cứ và kết luận

Người dùng xác nhận dùng yêu cầu hiện có trong dự án: `MA_TRAN_YEU_CAU_DE_TAI.md`, `KE_HOACH_DAY_DU_DE_TAI.md`, `QUY_TRINH_NGHIEN_CUU.md`, các contract, backlog và workbook phân công. Rà soát tại commit `2d568f2`; đây là đánh giá sự phù hợp với yêu cầu, không phải đánh giá trễ hạn.

Các đầu việc đã làm nhìn chung đúng hướng: tách content-risk khỏi kiểm chứng claim, xây verifier với gold evidence, có retrieval baseline và interface tích hợp. Tuy nhiên, chưa đủ căn cứ nghiệm thu toàn bộ đề tài hoặc gọi hệ thống hiện tại là pipeline bài viết hoàn chỉnh. Một số task chỉ hoàn tất thí nghiệm, một số mới đạt contract/MVP, và protocol đánh giá còn điểm cần sửa.

Không phát hiện sai lệch ở các con số Macro-F1 đã lưu khi tính lại từ prediction. Điều này xác nhận tính nhất quán giữa prediction và metric, không thay thế việc huấn luyện lại hay chứng minh toàn bộ quá trình chạy.

## Đối chiếu các đầu việc đã thực hiện

| Đầu việc | Đánh giá | Bằng chứng và giới hạn |
|---|---|---|
| D1, W1-01: audit ViFactCheck | Đạt phần audit cơ bản | Có script, báo cáo 7.232 mẫu, thống kê nhãn và phát hiện overlap của split gốc. Chưa lưu revision upstream bất biến trong audit/manifest chính; có fingerprint của snapshot Arrow. |
| W1-02: group split chống rò rỉ | Đúng phương pháp, cần bổ sung audit | Script chia theo URL, seed 42; báo cáo 5.076/1.080/1.076 mẫu và overlap URL bằng 0. Báo cáo split mới chưa kiểm tra lại overlap context/claim; không được mở rộng kết luận thành đã loại mọi dạng rò rỉ. Chưa đọc lại Parquet trong lần rà soát này do thiếu engine. |
| M1, W1-03, E1: TF-IDF/SVM verifier | Đạt phạm vi baseline oracle | Fit đặc trưng trên train, chọn C theo dev Macro-F1, báo cáo test riêng; tính lại test Macro-F1 40,1526%. |
| M2, W2-02, E2: PhoBERT verifier | Đạt phạm vi thí nghiệm oracle | Có mã fine-tune, word segmentation, early stopping và chọn checkpoint theo dev; prediction test khớp Macro-F1 81,0692%. Không phải kết quả retrieval→verifier. |
| W2-03: so sánh E1/E2 | Đạt phạm vi oracle | Cùng loại input claim–gold evidence và protocol group split; chênh lệch Macro-F1 khoảng 40,92 điểm phần trăm. |
| V5, W2-06, E7: biến thể batch | Đạt phạm vi đã điều chỉnh | Cùng danh sách claim/nhãn test với E2; Macro-F1 80,2528%. Cả hai giữ 256 token nên không được gọi E7 là thử nghiệm tăng ngữ cảnh. Tên experiment trong script vẫn chứa `long_context`. |
| V4: review 10 lỗi E2 | Đạt phạm vi review verifier | Có phân nhóm lỗi ngữ nghĩa, phủ định, thời gian và nghi vấn annotation. Không thay thế W3-04 về phân tích lỗi retrieval/verifier/NEI toàn pipeline. Tài liệu còn đưa test vào điều kiện chọn model mới; cần sửa. |
| V3: 18 claim thủ công | Đạt phạm vi smoke test đã lưu | Có case và kết quả 8/18 với ba passage mẫu; tài liệu nêu rõ giới hạn. Không phải benchmark chính thức. Chưa chạy lại model trong lần rà soát này. |
| R1, W1-04: corpus passage | Đạt baseline cục bộ | Kiểm tra trực tiếp 5.845 passage, 1.041 URL, ID passage duy nhất, không passage nào quá 700 ký tự. Chưa phải corpus nguồn/thời gian hoàn chỉnh. |
| C1, W1-06: schema và data contract | Đạt contract v1; chưa đạt metadata thực | Đã có Article/Claim/Evidence và loader tương thích ngược. Cả 5.845 passage thiếu title, published_at, retrieved_at, authority_score; source_type đều unknown. Contract v1 cho phép điều này, nhưng yêu cầu lọc nguồn/thời gian của đề tài vẫn chưa hoàn thành. |
| R2, W2-01, E3: BM25 benchmark | Đạt baseline URL-level | Tính lại từ 1.076 kết quả: Recall@3 98,1413%, Recall@5 98,9777%, MRR@5 0,967147. Không chứng minh tìm đúng đoạn evidence; coverage so khớp chuỗi gold–passage được báo cáo riêng là 57,0632%. |
| P1, W2-05: tích hợp verifier và contract | Đạt cấu trúc tích hợp | Có Protocol, dependency injection, chuyển evidence từ retriever sang verifier và test bằng stub. Chưa chứng minh chất lượng PhoBERT với retrieved evidence; chính sách NEI còn thiếu. |
| W1-05, U1: khung ứng dụng | Đạt MVP nhập một claim | Có input, nhãn, confidence và danh sách passage/URL. Vẫn dùng corpus mẫu; chưa có content-risk, xử lý bài viết, phân biệt passage được viện dẫn với passage chỉ truy xuất. |
| C2, W2-08, E9: content-only baseline | Đạt kết quả thí nghiệm; protocol cần bổ sung | Có title+body, VFND article-only, chọn C theo group CV; 221 prediction khớp Macro-F1 77,2738% và AUC 88,2108%. Calibration dùng CV không theo domain; chưa có artifact model cuối hoặc interface inference được xuất bởi script. |
| C3, W2-09, E10: content transformer | Có kết quả hợp lệ về số học; chưa đủ nghiệm thu so sánh/calibration | 221 prediction khớp Macro-F1 48,5947%, AUC 70,2029%; 29 domain chỉ thuộc một outer test fold, hash cả 5 fold khớp. Outer folds khác E9; mã chỉ dùng một inner holdout; chưa có ECE/Brier hoặc báo cáo trước/sau calibration. |
| W1-07: môi trường và manifest | Có baseline lịch sử; cần xác nhận bản hiện tại | Manifest lưu 10 test pass ở môi trường cũ. Hiện có 14 hàm test trong repository; chưa chạy lại được do Python khả dụng thiếu pytest và các dependency. Bốn hash lệch đều khớp lại khi chuyển LF/CRLF; không có bằng chứng thay đổi nội dung từ bốn sai lệch này. |

## Các vấn đề cần sửa trước khi nghiệm thu

### 1. Chính sách NEI chưa đáp ứng yêu cầu không đủ bằng chứng

`src/phobert_fact_checker.py:78` loại các dự đoán NEI khỏi nhóm ứng viên nếu tồn tại bất kỳ nhãn SUPPORTED/REFUTED nào. Không có ngưỡng confidence hay relevance đã hiệu chỉnh trên dev. `src/retriever.py` vẫn trả top-k khi điểm BM25 bằng 0.

Kiểm tra cô lập logic chọn nhãn bằng hai dự đoán giả lập: passage A = NEI 0,99; passage B = SUPPORTED 0,34; cả hai điểm retrieval = 0. Hàm trả SUPPORTED 0,34. Đây là kiểm chứng quy tắc lựa chọn, không phải suy luận từ model thật.

Hệ quả: xử lý danh sách evidence rỗng chưa đủ để đáp ứng yêu cầu abstention; evidence không liên quan nhưng không rỗng vẫn có thể tạo kết luận quyết đoán. Cần chọn ngưỡng/chính sách trên dev và đánh giá F1 NEI cùng chất lượng end-to-end, bao gồm evidence mâu thuẫn và ngoài chủ đề.

### 2. Demo chưa sử dụng kết quả retrieval đã nghiệm thu

`configs/config.yaml:6` vẫn trỏ tới `data/evidence/sample_evidence.jsonl`. Benchmark dùng `vifactcheck_passages.jsonl`, nên kết quả BM25 không đại diện cho cấu hình demo mặc định.

`app.py:41` hiển thị toàn bộ retrieved evidence nhưng không dùng `result.evidence_ids` để đánh dấu passage được verifier chọn làm căn cứ. Cần phân biệt rõ evidence được viện dẫn, bổ sung metadata nguồn khi có và đánh giá chính cấu hình được đem demo.

### 3. So sánh E9/E10 chưa kiểm soát cùng phép chia dữ liệu

Hai CSV có cùng 221 article_id và nhãn, nhưng số mẫu outer test fold khác nhau:

- E9: 80, 79, 21, 21, 20.
- E10: 16, 19, 145, 25, 16.

Đây không chỉ là đổi số thứ tự fold. E10 có một fold chiếm 145/221 bài. Chưa xác định nguyên nhân khác biệt từ artifact hiện có; không quy kết rò rỉ test.

Có thể báo cáo E9 đạt số điểm quan sát cao hơn và tạm giữ baseline này. Chưa nên khẳng định chênh lệch phản ánh riêng ưu thế kiến trúc. Cần lưu danh sách article_id/domain cho cùng outer folds, khóa phiên bản thư viện và đánh giá hai mô hình trên cùng protocol; nên báo cáo cả kết quả từng fold.

### 4. Mô tả calibration/nested CV chưa khớp đầy đủ với mã

- E9, `scripts/train_content_baseline.py:76`: `CalibratedClassifierCV(..., cv=3)` được fit không truyền group splits. Outer evaluation và chọn C có tách domain, nhưng bước calibration không giữ ranh giới domain. Điều này không tự động làm rò outer test; nó làm calibration chưa bám sát bối cảnh nguồn chưa thấy.
- E10, `kaggle/train_phobert_content_risk.py:110`: `next(inner.split(...))` chỉ lấy một train/dev split từ bộ chia ba fold. Báo cáo “3-fold inner” có thể bị hiểu thành chạy đủ ba fold; cần ghi đúng là một group holdout hoặc thực hiện đầy đủ CV như đã mô tả.
- E10 có temperature scaling và nhiệt độ từng fold, nhưng chưa có ECE/Brier, reliability plot hoặc đối chiếu trước/sau. Vì vậy đã thực hiện bước hiệu chỉnh, chưa chứng minh hiệu quả hiệu chỉnh.
- Script E9 chỉ xuất OOF prediction/metrics, chưa xuất model cuối cho inference; `src/pipeline.py` và `app.py` chưa gọi nhánh content-risk. Hoàn thành E9/E10 không đồng nghĩa hoàn thành chức năng phân tích bài viết trong sản phẩm.

### 5. Chưa đủ evidence cho yêu cầu nguồn/thời gian và retrieval thực

Corpus hiện đúng contract legacy khi ghi null cho thông tin không biết. Không được tự điền metadata suy đoán. Cần hoàn thiện ingestion từ nguồn có metadata thực, version corpus, tạo query/gold passage được review và đo chất lượng đúng đoạn evidence.

Việc BM25 index context từ các split để xây kho tìm kiếm không tự nó chứng minh rò rỉ nhãn: script chỉ lấy Context/Author/Url. Tuy nhiên benchmark này là kho đóng được xây từ tài liệu dataset, chưa đo khả năng tìm evidence từ web, nguồn hoặc thời điểm mới.

### 6. Quy tắc chọn mô hình có mâu thuẫn với nguyên tắc chỉ dùng dev

`docs/REVIEW_10_LOI_E2.md:32` yêu cầu model mới có test Macro-F1 không thấp hơn E2 quá 0,5 điểm phần trăm. Dùng điều kiện này để chấp nhận model sẽ biến test thành dữ liệu lựa chọn, trái quy trình nghiên cứu.

Script E1/E2 hiện chọn C/checkpoint theo dev; chưa có bằng chứng các kết quả đó đã được chọn sai. Cần bỏ tiêu chí quyết định dựa trên test trong tài liệu, dùng dev để quyết định và giữ test cho báo cáo cuối. Các mẫu test đã review cần được ghi nhận là đã quan sát khi thiết kế thí nghiệm tiếp theo.

### 7. Tái lập và trạng thái theo dõi chưa đủ chính xác

- Metadata thí nghiệm chưa đồng bộ commit Git, revision dữ liệu/model, phiên bản môi trường và artifact hashes theo yêu cầu quy trình.
- Manifest hiện có giữ đúng hash checkpoint trọng số. `requirements.lock`, sample evidence, tokenizer_config và vocab khác byte do LF/CRLF; nên thống nhất quy tắc xuống dòng và cập nhật manifest sau kiểm tra, không coi đây là bằng chứng hỏng model.
- E3 trong workbook vẫn ghi chưa bắt đầu dù benchmark đã có. W3-01 ghi chưa bắt đầu trong khi tích hợp kỹ thuật đã tồn tại; cần tách tích hợp khỏi đánh giá end-to-end.
- Quy trình nghiên cứu và workbook dùng mã E4/E5 không thống nhất giữa BM25 end-to-end và dense/hybrid; cần một danh mục thí nghiệm duy nhất.
- C1 hoàn thành chỉ nên được hiểu là contract v1. C3 hoàn thành thí nghiệm E10 chưa đủ cho mọi yêu cầu calibration và chức năng content-risk.

## Các yêu cầu chưa triển khai hoặc chưa có kết quả nghiệm thu

| Yêu cầu | Trạng thái thực tế |
|---|---|
| Claim decomposition, W3-06/E11 | Mới có schema Claim; chưa có luồng tách bài thành claim nguyên tử. |
| Tổng hợp cấp bài/fusion, W4-06 | Chưa có policy và output nhiều claim; chưa tích hợp content-risk. |
| Dense/hybrid/reranker, W2-04/W3-08/W5-01 | Có kế hoạch, chưa có implementation/metric tương ứng trong phạm vi mã đã rà soát. W2-04 cho phép quyết định bỏ nếu được ghi nhận đúng tiêu chí. |
| Web retrieval allowlist, W2-07/W3-05/E8 | Có kế hoạch; chưa có provider/config allowlist và web retriever hoạt động. |
| Temporal/source filters, W3-07/W3-08 | Metadata thực còn thiếu; chưa có lọc và benchmark tương ứng. |
| Calibration/NEI cho verifier, W3-02/E6 | Chưa có ngưỡng chọn trên dev và báo cáo F1 NEI/calibration cho pipeline. Calibration E10 không thay thế việc này. |
| Đánh giá end-to-end, P2/R5/W4-02/W5-02 | Chưa có benchmark chính thức verdict từ evidence thực truy hồi. |
| Citation audit/joint score/temporal test, C6/E13 | Chưa có 50 citation review và báo cáo; source-domain CV của content branch không thay thế external validity của toàn pipeline. |
| Release/demo đầy đủ, C7/W6-01/W6-03 | Chưa chứng minh cài từ đầu và demo bài viết→claim→evidence→verdict; chưa có bộ release/slide hoàn chỉnh trong artefact đã rà soát. |

## Thứ tự xử lý đề xuất

1. Chốt protocol đánh giá và trạng thái nghiệm thu: dùng chung outer folds E9/E10, mô tả calibration đúng, bỏ điều kiện chọn theo test, cập nhật backlog/workbook theo evidence.
2. Nối corpus thật vào cấu hình đánh giá/demo; hoàn thiện NEI trên dev, đánh dấu citation theo evidence_ids và đo BM25→PhoBERT end-to-end.
3. Hoàn thiện nhánh content-risk dùng được khi inference, claim decomposition và aggregation cấp bài; điền metadata nguồn/thời gian từ dữ liệu thực.
4. Thực hiện các thí nghiệm retrieval/web, citation audit, temporal/source evaluation và ablation theo phạm vi đã chốt.
5. Khóa môi trường/manifest và chạy kiểm thử, tái lập rồi đóng gói release/báo cáo/demo.

## Giới hạn lần rà soát

Đã đọc mã nguồn, tài liệu, workbook và artifact; tính lại metric bằng thư viện chuẩn Python từ các CSV/JSONL; kiểm tra corpus, hash fold E10 và sai khác LF/CRLF; kiểm tra cô lập logic chọn nhãn verifier. Không cài thêm dependency, không sửa model/pipeline/metric gốc, không huấn luyện lại và không chạy benchmark PhoBERT/GPU. Lần thử pytest trước đó không chạy được do môi trường; không công bố bộ test hiện tại đã pass.
