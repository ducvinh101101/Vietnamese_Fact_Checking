# Vì sao local trả kết quả thấp? — 27/10/2026

Đã phân tích kết quả lưu sẵn, chạy thêm kiểm tra offline và giữ nguyên cấu hình,
checkpoint cùng bộ gold. Không gọi Gemini, không huấn luyện hay chọn lại ngưỡng.
Mã chạy: `run_diagnostics.py`; kết quả chi tiết: `diagnostics.json`; tổng hợp:
`summary.json` trong cùng thư mục.

## Kết quả kiểm tra trực tiếp

Lấy trước 12 ca cho mỗi nhãn từ DEV ViFactCheck, tổng 36 ca, seed 137/138/139.
Đây là mẫu chẩn đoán nhỏ trên dev, không phải một benchmark độc lập mới.

| Đầu vào cho hệ thống | Đúng | Accuracy | Macro-F1 |
| --- | ---: | ---: | ---: |
| 36 claim dev + bằng chứng chuẩn do người gán nhãn cung cấp | 32/36 | 88,89% | 88,76% |
| Cùng 36 claim, dùng bằng chứng BM25 top 3 như app | 24/36 | 66,67% | 66,75% |
| 84 gold giả lập, kết quả chạy đã lưu | 28/84 | 33,33% | 22,50% |

Hai dòng đầu sử dụng cùng 36 claim để tách ảnh hưởng của bằng chứng đầu vào và
cách tổng hợp. Dòng cuối là tập khác miền và có yêu cầu suy luận khác, không dùng
để suy ra mức giảm nhân quả hoặc so trực tiếp với toàn bộ benchmark ViFactCheck.

Trong mẫu dev, cả **36/36** đều tìm được đúng URL nguồn trong top 3, nhưng có
**10 ca đọc bằng chứng chuẩn thì đúng, chạy local thì sai**. Trong cả 10 ca ấy,
URL nguồn vẫn có mặt. Trước ngưỡng abstain, bộ tổng hợp chọn đoạn hạng 1 ở
**36/36 ca**. Vì vậy URL-level recall cao chưa bảo đảm lấy đúng câu cần kiểm chứng.

## 1. Kho local nhỏ và không phải một công cụ tìm kiếm toàn Internet

Kho mặc định có **5.845 đoạn từ 1.041 bài**; các đoạn v1 không có `published_at`.
App local dùng BM25 và `top_k=3`. Điền Gemini key không bổ sung dữ liệu cho kho
này và không thay đổi trọng số PhoBERT; Gemini hiện có runner riêng.

Trong corpus v2 dùng cho nhánh hybrid, chỉ **1.087/5.844 đoạn có ngày** (18,60%).
Các ngày đã ghi thuộc **2022–2023**, từ 15/08/2022 đến 19/04/2023. **81,40%**
thiếu ngày. Số liệu này nói về metadata hiện có, không khẳng định ngày đăng thật
của mọi đoạn bị thiếu. Claim thời sự cần nguồn mới; bỏ bộ lọc thời gian không
làm nguồn cũ trở thành nguồn xác nhận cho hiện tại.

Ví dụ chạy lại trong chế độ local:

| Claim | Local trả | Confidence | Quan sát bằng chứng |
| --- | --- | ---: | --- |
| Hà Nội là thủ đô của Việt Nam. | NOT_ENOUGH_INFO | 0,4858 | Bài du lịch/hợp tác Việt–Trung, không phải tư liệu được chọn để xác nhận trực tiếp mệnh đề |
| Python là một ngôn ngữ lập trình. | REFUTED | 0,6453 | Đoạn về học ngoại ngữ/người bản xứ; không có thông tin đủ để bác bỏ claim |
| Giá xăng tăng từ chiều nay. | SUPPORTED | 0,9845 | Đoạn nói kỳ điều hành ngày 13/3; local không gắn “hôm nay” vào ngày xét thực tế |
| Claim Lula hoãn chuyến thăm 6 ngày như câu nguồn | SUPPORTED | 0,9898 | Tìm đúng câu nguồn |
| Cùng claim Lula nhưng đổi thành 10 ngày | REFUTED | 0,9853 | Tìm đúng câu nguồn nói 6 ngày |

Các câu trên là truy vấn chẩn đoán; không dùng phản hồi model để xác nhận sự thật
ngoài đời. Đặc biệt, nguồn về một kỳ điều hành cũ không đủ chứng minh giá xăng
ngày chạy tăng hay giảm.

## 2. Đúng bài, sai đoạn; và kết quả bị đoạn đầu chi phối

BM25 xếp theo khớp từ. Ví dụ một claim dev hỏi chi tiết thương hiệu áo: đoạn
hạng 1 của đúng bài chỉ nói “thương hiệu nổi tiếng” và sự kiện xuất hiện trong
video, còn bằng chứng được gán nhãn có chi tiết thương hiệu cần xác minh. PhoBERT
đọc bằng chứng chuẩn trả SUPPORTED; local trả NEI với confidence 0,9646.

`retrieval_rank_bias=1.0` nhân điểm chọn đoạn với `1/rank`. Nếu đoạn đầu đã có
xác suất lớp lớn nhất trên 0,5, mọi đoạn từ hạng 2 trở xuống không thể vượt nó.
Đoạn hạng 3 có điểm tối đa 1/3, nên không thắng được cực đại của ba lớp ở đoạn
hạng 1 (ít nhất 1/3, hòa thì ứng viên trước thắng). Đây là đặc tính của chính
sách hiện tại, không phải bằng chứng rằng tắt rank bias sẽ tự cải thiện.

Do đó chỉ tăng top_k chưa chắc giúp. Nên thử lấy tập ứng viên rộng hơn rồi xếp
lại theo mức liên quan giữa claim và đoạn/câu. Cách retrieve → re-rank này được
mô tả trong [tài liệu Sentence Transformers](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).
Mức cải thiện trên dự án này còn phải đo trên dev riêng.

Mã liên quan: `src/retriever.py`, `src/retrieval_aware_policy.py`,
`src/system_builder.py` trong thư mục gốc dự án.

## 3. Khả năng tổng quát hóa và suy luận của verifier còn hạn chế

Trên 84 ca, model trả **73 REFUTED, 6 SUPPORTED, 5 NOT_ENOUGH_INFO** dù nhãn
chuẩn chia đều 28/28/28. **24/28** ca SUPPORTED và **24/28** ca NEI bị đẩy sang
REFUTED. Đây là hiện tượng lệch dự đoán trên tập này; chưa xác định được đóng góp
nhân quả của từng từ/ngữ liệu khi chưa có thí nghiệm kiểm soát lớn hơn.

Kiến trúc hiện tại chấm từng cặp claim–passage rồi chọn kết quả, không tạo một
lập luận kết hợp các đoạn. Ca kiểm soát mới: đợt đầu trao 40 cuốn, đợt sau trao
50 cuốn, tổng 90; model trả REFUTED với 0,9913. Khi ghép cả hai đoạn thành một
chuỗi, nó vẫn trả REFUTED với 0,9910. Ghép đoạn đơn thuần chưa giải quyết ca này.

Bộ 84 do trợ lý tạo gồm tư liệu giả lập, tên mới, toán học, thời gian, lượng từ,
xung đột nguồn và chống chỉ dẫn cài trong bằng chứng. Nó khác dữ liệu tin tức
[ViFactCheck](https://arxiv.org/abs/2412.15308). Nhãn chưa có người thứ hai kiểm
tra độc lập. Điểm 33,33% cho thấy hạn chế trên bộ đó, chưa đủ kết luận model
thất bại ở mọi loại claim. Phép thử 32/36 oracle trên dev cũng cho thấy model
vẫn đọc được nhiều ca cùng miền.

Không có dấu hiệu đảo thứ tự nhãn: checkpoint, mã inference và mã train cùng
quy ước 0=SUPPORTED, 1=REFUTED, 2=NEI. Quy trình tách từ ở train/inference đều
dùng VnCoreNLP. Trên bộ 84, **không có cặp vượt giới hạn token**, nên cắt token
không giải thích được điểm thấp của chính bộ đó. PhoBERT có ngữ cảnh tối đa
256 token theo [tài liệu VinAI](https://github.com/VinAIResearch/PhoBERT);
không thể chỉ đổi cấu hình thành 512 rồi kỳ vọng checkpoint tự hỗ trợ.

Manifest train RT-V2 có 5.201 cặp, ba nhãn lần lượt 1.815/1.703/1.683. Không nên
quy lỗi đơn giản cho mất cân bằng nhãn train. Phần augmentation retrieved-pair
được chọn chỉ 126 cặp; cần tăng sự đa dạng có kiểm tra chất lượng nếu muốn phủ
các kiểu câu mới. Manifest không tự chứng minh chất lượng của nhãn AI-silver.

## 4. Confidence không đo trực tiếp xác suất thông tin đúng

Trên bộ 84: **56 ca sai**, trong đó **34 ca confidence ≥0,9**; confidence trung
bình ở các ca sai là **0,8657**. Hiện tượng này cho thấy điểm tự tin cần được
kiểm định về calibration trên dữ liệu mục tiêu.

Confidence thấp có hai nhánh đáng phân biệt:

- Không có bằng chứng có điểm truy xuất dương: trả NEI, confidence **0,0**.
- Nhãn quyết đoán dưới ngưỡng 0,5: policy chuyển về NEI và có thể giữ xác suất
  NEI rất thấp. Ví dụ xác suất `[0,45; 0,40; 0,15]` ở đoạn đầu có thể thành
  `NEI, confidence=0,15`. Đây là abstention theo ngưỡng, không phải “câu sai 85%”.

Trong nhánh rank-aware, lý do trả về hiện vẫn mặc định `model_prediction`, nên
thông báo chưa chỉ rõ việc abstain do ngưỡng. Có thể cải thiện cách giải thích và
tách trạng thái bằng chứng khỏi confidence; việc đó không thay cho cải thiện nhãn.

Temperature scaling là một phương pháp calibration trên dev; với một cặp, nhân
logit bằng hệ số dương không đổi thứ tự lớp. Nó không dạy model kiến thức mới hay
cách cộng nhiều bằng chứng. Tham chiếu:
[Guo và cộng sự, ICML 2017](https://arxiv.org/abs/1706.04599).

## Thứ tự cải thiện đề xuất

1. **Bằng chứng và phạm vi:** bổ sung kho đúng lĩnh vực dùng thật, ngày đăng và
   nguồn; với claim thời sự cần nguồn mới. Khi không có nguồn phù hợp, trả NEI
   với lý do rõ ràng. Đo chất lượng ở mức câu/đoạn, không chỉ trùng URL.
2. **Chọn đoạn:** lấy nhiều ứng viên hơn, thử semantic/cross-encoder reranking
   phù hợp tiếng Việt, chọn đoạn đủ chi tiết; đánh giá lại rank bias trên dev.
   Không giả định tăng top_k hoặc hạ ngưỡng sẽ tăng độ đúng.
3. **Verifier:** xây train/dev mới có nhãn đã rà soát cho số liệu, phủ định,
   sai đối tượng, thiếu bằng chứng, thời gian và kết hợp nhiều đoạn. Huấn luyện
   bổ sung hoặc thay cách tổng hợp nhiều bằng chứng, rồi kiểm tra trên holdout mới.
4. **Confidence và trình bày:** hiệu chỉnh trên dev độc lập, tách “thiếu nguồn”,
   “model không chắc”, “nguồn mâu thuẫn”, và “nguồn bác bỏ”.

Giữ nguyên baseline hiện tại để so với Gemini. Dùng tên phiên bản riêng cho
local cải tiến. Bộ 84 đã được xem lỗi nên nên giữ nó làm bộ chẩn đoán/hồi quy;
cần một holdout mới chưa xem nếu muốn tuyên bố cải thiện tổng quát sau khi sửa.
Không dùng Gemini tạo đáp án test rồi xem đó là phép chấm độc lập cho Gemini.
