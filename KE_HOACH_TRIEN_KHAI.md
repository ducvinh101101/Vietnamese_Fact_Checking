# Kế hoạch triển khai hệ thống đánh giá độ tin cậy và xác minh thông tin tiếng Việt

## 1. Thông tin đề tài

**Tên đề tài đề xuất:** Xây dựng hệ thống đánh giá độ tin cậy và xác minh thông tin tiếng Việt dựa trên phân tích nội dung kết hợp RAG.

**Phạm vi:** Bài tập lớn môn Xử lý ngôn ngữ tự nhiên.

**Thời gian dự kiến:** 4 tuần.

**Sản phẩm cuối cùng:** Một ứng dụng web cho phép người dùng nhập một phát biểu hoặc đoạn tin tiếng Việt, sau đó trả về:

- Dự đoán dựa trên nội dung.
- Kết quả kiểm chứng dựa trên bằng chứng.
- Nhãn kết luận: `SUPPORTED`, `REFUTED` hoặc `NOT_ENOUGH_INFO`.
- Độ tin cậy của mô hình.
- Các đoạn bằng chứng và nguồn tham khảo.
- Giải thích ngắn gọn cho kết luận.

> Hệ thống được định vị là công cụ hỗ trợ kiểm chứng thông tin, không phải công cụ xác định sự thật tuyệt đối.

## 2. Mục tiêu

### 2.1. Mục tiêu chính

Xây dựng và đánh giá một hệ thống NLP tiếng Việt gồm hai nhánh:

1. Phân tích nội dung để nhận diện dấu hiệu của tin không đáng tin.
2. Truy xuất và đối chiếu bằng chứng để đưa ra kết luận có căn cứ.

### 2.2. Mục tiêu cụ thể

- Tiền xử lý được văn bản tiếng Việt.
- Xây dựng một mô hình phân loại cơ sở bằng TF-IDF và SVM hoặc Logistic Regression.
- Xây dựng một mô hình phân loại nâng cao bằng PhoBERT nếu tài nguyên tính toán cho phép.
- Xây dựng kho tài liệu kiểm chứng từ dữ liệu ViFactCheck.
- Truy xuất được top-k đoạn bằng chứng liên quan bằng BM25 hoặc vector search.
- Sử dụng mô hình ngôn ngữ để đối chiếu phát biểu với bằng chứng.
- Hiển thị kết quả, giải thích và nguồn bằng chứng trên giao diện Streamlit.
- Đánh giá riêng từng thành phần và toàn bộ pipeline.

## 3. Phạm vi và giới hạn

### 3.1. Chức năng thuộc phạm vi

- Đầu vào là văn bản tiếng Việt.
- Xử lý một phát biểu hoặc một đoạn tin ngắn tại mỗi lượt.
- Kho bằng chứng đóng, được chuẩn bị trước.
- Truy xuất tối đa 3–5 đoạn bằng chứng.
- Hỗ trợ ba nhãn kiểm chứng.
- Giao diện chạy cục bộ.
- Lưu kết quả thử nghiệm ra CSV hoặc JSON.

### 3.2. Chức năng ngoài phạm vi

- Thu thập tin tức Internet theo thời gian thực.
- Kiểm chứng hình ảnh, âm thanh hoặc video.
- Phân tích mạng xã hội và tốc độ lan truyền.
- Phát hiện tài khoản bot.
- Xây dựng knowledge graph.
- Huấn luyện mô hình ngôn ngữ lớn từ đầu.
- Triển khai hệ thống ở quy mô sản xuất.

## 4. Câu hỏi nghiên cứu

- **RQ1:** Mô hình PhoBERT có cải thiện Macro-F1 so với TF-IDF kết hợp mô hình học máy truyền thống không?
- **RQ2:** Truy xuất bằng chứng bằng vector search có tốt hơn BM25 trên dữ liệu tiếng Việt không?
- **RQ3:** Kết hợp phân loại nội dung với kiểm chứng bằng RAG có tạo ra kết quả dễ giải thích hơn mô hình phân loại đơn lẻ không?
- **RQ4:** Hệ thống có nhận biết và trả về `NOT_ENOUGH_INFO` khi bằng chứng không đủ hay không?

## 5. Kiến trúc tổng thể

```text
                 Văn bản đầu vào
                        │
                Tiền xử lý tiếng Việt
                        │
          ┌─────────────┴─────────────┐
          │                           │
          ▼                           ▼
  Phân loại nội dung          Truy xuất bằng chứng
 TF-IDF/SVM hoặc PhoBERT       BM25/Vector Search
          │                           │
          │                    Top-k bằng chứng
          │                           │
          └─────────────┬─────────────┘
                        ▼
               Mô-đun kiểm chứng
                 NLI hoặc LLM
                        │
                        ▼
       SUPPORTED / REFUTED / NOT_ENOUGH_INFO
                        │
                        ▼
          Giải thích + nguồn + độ tin cậy
```

## 6. Thiết kế các thành phần

### 6.1. Tiền xử lý

Các bước dự kiến:

1. Chuẩn hóa Unicode.
2. Loại bỏ HTML, URL dư thừa và ký tự không cần thiết.
3. Chuẩn hóa khoảng trắng và dấu câu.
4. Giữ lại số liệu, ngày tháng và tên riêng vì đây là thông tin quan trọng khi kiểm chứng.
5. Ghép tiêu đề và nội dung theo định dạng `[TITLE] ... [CONTENT] ...` nếu dữ liệu có cả hai trường.

Không nên loại bỏ toàn bộ stopword vì các từ phủ định như “không”, “chưa”, “chẳng” có thể làm thay đổi hoàn toàn ý nghĩa của phát biểu.

### 6.2. Nhánh phân loại nội dung

#### Baseline bắt buộc

- Biểu diễn: TF-IDF word n-gram và character n-gram.
- Mô hình: Linear SVM hoặc Logistic Regression.
- Đầu ra: nhãn và xác suất/decision score.

#### Mô hình nâng cao

- Mô hình đề xuất: PhoBERT.
- Bài toán: sequence classification.
- Số nhãn: 2 hoặc 3 tùy cách chuẩn hóa bộ dữ liệu.
- Theo dõi: training loss, validation loss, accuracy và Macro-F1.

Nếu không có GPU hoặc thời gian hạn chế, baseline TF-IDF + SVM được xem là mô hình phân loại chính.

### 6.3. Kho bằng chứng

Sử dụng dữ liệu ViFactCheck làm nguồn chính. Chuẩn hóa mỗi tài liệu theo cấu trúc:

```json
{
  "document_id": "doc_0001",
  "title": "Tiêu đề",
  "content": "Nội dung hoặc đoạn văn",
  "source": "Tên nguồn",
  "url": "https://example.com",
  "topic": "Chủ đề"
}
```

Yêu cầu xử lý dữ liệu:

- Loại bản ghi thiếu nội dung.
- Loại tài liệu trùng lặp.
- Chia tài liệu dài thành các đoạn khoảng 150–300 từ.
- Giữ liên kết từ đoạn văn về tài liệu gốc.
- Không đưa evidence của tập test vào kho huấn luyện theo cách gây rò rỉ nhãn.

### 6.4. Truy xuất bằng chứng

Triển khai theo hai mức:

#### Mức tối thiểu

- BM25 trên toàn bộ các đoạn văn.
- Trả về top-3 hoặc top-5 kết quả.

#### Mức mở rộng

- Sinh embedding cho các đoạn văn.
- Lưu embedding bằng FAISS hoặc ChromaDB.
- Truy vấn theo cosine similarity.
- So sánh BM25 và vector search bằng Recall@k.

Nếu còn thời gian, kết hợp hai điểm số:

```text
hybrid_score = alpha * bm25_score + (1 - alpha) * vector_score
```

### 6.5. Kiểm chứng bằng RAG

Đầu vào của mô-đun kiểm chứng gồm:

- Phát biểu cần kiểm chứng.
- Top-k đoạn bằng chứng.
- ID và nguồn của từng bằng chứng.

Prompt mẫu:

```text
Bạn là hệ thống hỗ trợ kiểm chứng thông tin tiếng Việt.
Chỉ được sử dụng các bằng chứng được cung cấp.

Phát biểu:
{claim}

Bằng chứng:
[E1] {evidence_1}
[E2] {evidence_2}
[E3] {evidence_3}

Hãy trả về JSON gồm:
- label: SUPPORTED, REFUTED hoặc NOT_ENOUGH_INFO
- confidence: số từ 0 đến 1
- evidence_ids: danh sách ID bằng chứng đã sử dụng
- explanation: giải thích ngắn gọn bằng tiếng Việt

Nếu bằng chứng không đủ hoặc không liên quan, phải chọn NOT_ENOUGH_INFO.
Không được tạo thêm số liệu, URL hoặc sự kiện không có trong bằng chứng.
```

Đầu ra phải được kiểm tra lại để bảo đảm:

- JSON hợp lệ.
- Nhãn nằm trong tập cho phép.
- ID bằng chứng thực sự tồn tại.
- Confidence nằm trong khoảng 0–1.

### 6.6. Tổng hợp kết quả

Phiên bản MVP sử dụng luật đơn giản:

| Phân loại nội dung | Kết quả RAG | Kết luận chung |
|---|---|---|
| Đáng tin | SUPPORTED | Đáng tin |
| Không đáng tin | REFUTED | Không đáng tin |
| Bất kỳ | NOT_ENOUGH_INFO | Chưa đủ bằng chứng |
| Hai nhánh mâu thuẫn | SUPPORTED/REFUTED | Cảnh báo cần xem xét thủ công |

Giao diện phải hiển thị kết quả của từng nhánh, tránh che giấu trường hợp hai mô hình không đồng thuận.

## 7. Công nghệ đề xuất

| Thành phần | Công nghệ |
|---|---|
| Ngôn ngữ | Python 3.10+ |
| Xử lý dữ liệu | pandas, NumPy |
| Baseline | scikit-learn |
| Transformer | PyTorch, Transformers |
| Mô hình tiếng Việt | PhoBERT |
| BM25 | rank-bm25 |
| Vector search | sentence-transformers, FAISS hoặc ChromaDB |
| API tùy chọn | FastAPI |
| Giao diện | Streamlit |
| Trực quan hóa | matplotlib, seaborn |
| Quản lý cấu hình | YAML hoặc biến môi trường |

## 8. Cấu trúc thư mục dự kiến

```text
xlnntn/
├── README.md
├── KE_HOACH_TRIEN_KHAI.md
├── requirements.txt
├── .env.example
├── configs/
│   └── config.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   └── evidence/
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_baseline.ipynb
│   └── 03_evaluation.ipynb
├── src/
│   ├── preprocessing.py
│   ├── train_classifier.py
│   ├── predict_classifier.py
│   ├── build_index.py
│   ├── retriever.py
│   ├── fact_checker.py
│   ├── pipeline.py
│   └── evaluation.py
├── models/
├── indexes/
├── outputs/
│   ├── metrics/
│   ├── figures/
│   └── predictions/
├── tests/
│   ├── test_preprocessing.py
│   ├── test_retriever.py
│   └── test_pipeline.py
└── app.py
```

Không đưa model checkpoint, dữ liệu lớn, API key hoặc vector index lớn lên Git. Các thư mục này cần được cấu hình trong `.gitignore`.

## 9. Kế hoạch triển khai theo tuần

### Tuần 1: Dữ liệu và baseline

**Mục tiêu:** Có dữ liệu sạch, báo cáo khám phá dữ liệu và baseline đầu tiên.

- [ ] Tải và khảo sát ViFactCheck.
- [ ] Thống kê số mẫu, độ dài và phân bố nhãn.
- [ ] Kiểm tra dữ liệu thiếu và trùng lặp.
- [ ] Chia train/validation/test.
- [ ] Xây dựng pipeline tiền xử lý.
- [ ] Huấn luyện TF-IDF + SVM/Logistic Regression.
- [ ] Báo cáo Accuracy, Precision, Recall và Macro-F1.
- [ ] Lưu confusion matrix.

**Đầu ra tuần 1:**

- Bộ dữ liệu đã chuẩn hóa.
- Notebook EDA.
- Baseline chạy được và có số liệu đánh giá.

### Tuần 2: Mô hình nội dung và truy xuất

**Mục tiêu:** Có mô hình phân loại nâng cao và bộ máy tìm kiếm bằng chứng.

- [ ] Fine-tune PhoBERT hoặc xác nhận sử dụng baseline nếu thiếu GPU.
- [ ] Chia context thành các đoạn bằng chứng.
- [ ] Xây dựng BM25 index.
- [ ] Truy xuất top-3/top-5 theo claim.
- [ ] Đánh giá Recall@3 và Recall@5.
- [ ] Thử vector search nếu còn thời gian.
- [ ] So sánh BM25 với vector search.

**Đầu ra tuần 2:**

- Model phân loại tốt nhất.
- Evidence index.
- Module retriever.
- Bảng so sánh các phương pháp truy xuất.

### Tuần 3: RAG và tích hợp pipeline

**Mục tiêu:** Hoàn thành luồng kiểm chứng end-to-end.

- [ ] Viết prompt kiểm chứng có cấu trúc.
- [ ] Tích hợp LLM hoặc mô hình NLI.
- [ ] Kiểm tra và chuẩn hóa JSON đầu ra.
- [ ] Xử lý trường hợp không tìm thấy bằng chứng.
- [ ] Xử lý trường hợp hai nhánh mâu thuẫn.
- [ ] Tích hợp classifier, retriever và fact-checker.
- [ ] Viết test cho các chức năng chính.

**Đầu ra tuần 3:**

- Pipeline chạy từ văn bản đầu vào đến kết luận.
- Kết quả có trích dẫn bằng chứng.
- Bộ ví dụ kiểm thử đúng, sai và thiếu thông tin.

### Tuần 4: Giao diện, đánh giá và báo cáo

**Mục tiêu:** Hoàn thiện sản phẩm trình diễn và tài liệu nộp bài.

- [ ] Xây dựng giao diện Streamlit.
- [ ] Hiển thị kết quả từng nhánh.
- [ ] Hiển thị top-k bằng chứng và nguồn.
- [ ] Chạy đánh giá trên tập test.
- [ ] Phân tích ít nhất 10 trường hợp đúng và sai.
- [ ] Hoàn thiện README và hướng dẫn chạy.
- [ ] Viết báo cáo.
- [ ] Chuẩn bị slide và kịch bản demo.
- [ ] Kiểm thử lại trên máy dùng để thuyết trình.

**Đầu ra tuần 4:**

- Ứng dụng demo hoàn chỉnh.
- Báo cáo kết quả.
- Slide thuyết trình.
- Mã nguồn có thể chạy lại.

## 10. Phân công công việc mẫu

Nếu nhóm có ba thành viên:

| Thành viên | Nhiệm vụ chính | Nhiệm vụ hỗ trợ |
|---|---|---|
| Thành viên 1 | Dữ liệu, tiền xử lý, baseline | Viết phần dữ liệu trong báo cáo |
| Thành viên 2 | PhoBERT, đánh giá mô hình | Phân tích kết quả thực nghiệm |
| Thành viên 3 | Retrieval, RAG, Streamlit | Tích hợp và chuẩn bị demo |

Mọi thành viên cùng chịu trách nhiệm kiểm thử, báo cáo và thuyết trình. Nếu làm cá nhân, thực hiện tuần tự theo kế hoạch ở mục 9.

## 11. Kế hoạch đánh giá

### 11.1. Phân loại nội dung

- Accuracy.
- Precision, Recall, F1 theo từng nhãn.
- Macro-F1.
- Confusion matrix.

### 11.2. Truy xuất bằng chứng

- Recall@3.
- Recall@5.
- MRR nếu xác định được vị trí evidence đúng.
- Thời gian truy xuất trung bình.

### 11.3. Kiểm chứng end-to-end

- Macro-F1 của ba nhãn.
- Tỷ lệ dự đoán có trích dẫn hợp lệ.
- Tỷ lệ dự đoán đúng cả nhãn và bằng chứng.
- Tỷ lệ chọn đúng `NOT_ENOUGH_INFO`.
- Đánh giá thủ công chất lượng giải thích.

### 11.4. Các cấu hình cần so sánh

| Mã | Cấu hình |
|---|---|
| E1 | TF-IDF + SVM |
| E2 | PhoBERT |
| E3 | BM25 + bộ kiểm chứng |
| E4 | Vector search + bộ kiểm chứng, nếu có |
| E5 | Phân loại nội dung + RAG |

## 12. Tiêu chí hoàn thành

### MVP bắt buộc

- [ ] Đọc và tiền xử lý được dữ liệu.
- [ ] Có ít nhất một mô hình phân loại nội dung.
- [ ] Có truy xuất top-k bằng chứng.
- [ ] Có ba nhãn kiểm chứng.
- [ ] Có giải thích và ID nguồn bằng chứng.
- [ ] Có giao diện nhập liệu và xem kết quả.
- [ ] Có báo cáo chỉ số trên tập test.
- [ ] Có README hướng dẫn chạy.

### Chức năng cộng điểm

- [ ] So sánh BM25 và vector search.
- [ ] Fine-tune PhoBERT.
- [ ] Kết hợp điểm của hai nhánh.
- [ ] Có chế độ xem chi tiết từng đoạn bằng chứng.
- [ ] Có biểu đồ confidence và confusion matrix.
- [ ] Có Dockerfile hoặc script cài đặt tự động.
- [ ] Có test tự động cho pipeline.

## 13. Rủi ro và phương án xử lý

| Rủi ro | Ảnh hưởng | Phương án |
|---|---|---|
| Không có GPU | Không fine-tune được PhoBERT | Dùng TF-IDF + SVM hoặc huấn luyện trên Colab |
| Dataset mất cân bằng | Accuracy cao nhưng F1 thấp | Dùng Macro-F1, class weight và stratified split |
| Retrieval không tìm đúng evidence | RAG kết luận sai | Đánh giá Recall@k riêng, tăng k và cải thiện chunking |
| LLM tạo thông tin ngoài evidence | Giải thích không đáng tin | Prompt ràng buộc, kiểm tra evidence ID và dùng nhãn NEI |
| API LLM không ổn định hoặc tốn phí | Demo có thể thất bại | Cache kết quả, chuẩn bị mô hình local hoặc ví dụ dự phòng |
| Rò rỉ dữ liệu | Kết quả đánh giá cao giả tạo | Chia dữ liệu theo tài liệu và loại bản ghi trùng |
| Phạm vi quá lớn | Không hoàn thành đúng hạn | Ưu tiên MVP, bỏ vector search hoặc PhoBERT khi cần |

## 14. Kịch bản demo

Chuẩn bị tối thiểu ba trường hợp:

1. **Tin được ủng hộ:** hệ thống tìm thấy bằng chứng xác nhận.
2. **Tin bị bác bỏ:** bằng chứng chứa thông tin hoặc số liệu trái ngược.
3. **Tin chưa đủ dữ kiện:** tài liệu truy xuất không đủ để kết luận.

Luồng trình bày:

1. Nhập phát biểu.
2. Hiển thị dự đoán từ mô hình nội dung.
3. Hiển thị các bằng chứng được truy xuất.
4. Hiển thị kết luận của bộ kiểm chứng.
5. Giải thích trường hợp hai nhánh đồng thuận hoặc mâu thuẫn.

## 15. Dàn ý báo cáo

1. Giới thiệu bài toán và động lực.
2. Cơ sở lý thuyết: fake news detection, PhoBERT, information retrieval và RAG.
3. Các nghiên cứu và bộ dữ liệu liên quan.
4. Dữ liệu và tiền xử lý.
5. Kiến trúc và phương pháp đề xuất.
6. Thiết lập thực nghiệm.
7. Kết quả và thảo luận.
8. Phân tích lỗi và giới hạn.
9. Kết luận và hướng phát triển.

## 16. Tài liệu tham khảo khởi đầu

- ViFactCheck: <https://ojs.aaai.org/index.php/AAAI/article/view/32008>
- ViFactCheck Dataset: <https://huggingface.co/datasets/tranthaihoa/vifactcheck>
- FEVER: <https://aclanthology.org/N18-1074/>
- ReINTEL Challenge 2020: <https://aclanthology.org/2020.vlsp-1.1/>
- PhoBERT: <https://aclanthology.org/2020.findings-emnlp.92/>

## 17. Quyết định triển khai khuyến nghị

Để bảo đảm hoàn thành đúng hạn, phiên bản đầu tiên nên chọn:

- **Classifier:** TF-IDF + Linear SVM.
- **Retriever:** BM25, top-3.
- **Fact-checker:** LLM với đầu ra JSON hoặc mô hình NLI có sẵn.
- **Dataset:** ViFactCheck.
- **Giao diện:** Streamlit.

Sau khi MVP chạy ổn định, lần lượt bổ sung PhoBERT, vector search và cơ chế kết hợp điểm. Thứ tự này giúp dự án luôn có một phiên bản có thể trình diễn ngay cả khi các phần nâng cao chưa hoàn tất.
