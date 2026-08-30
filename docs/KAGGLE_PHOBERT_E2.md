# Chạy E2 PhoBERT-base trên Kaggle

## 1. Upload dữ liệu

1. Tạo Kaggle Dataset mới ở chế độ riêng tư.
2. Upload tệp `vifactcheck_group_split.zip` từ thư mục `kaggle/` của dự án này.
3. Đặt slug Dataset là `vifactcheck-group-split`, hoặc sửa biến `INPUT_DIR` trong script cho đúng slug của bạn.

ZIP chứa ba tệp `train.parquet`, `dev.parquet`, `test.parquet`. Script tự giải nén ZIP này vào `/kaggle/working` khi cần. Đây là split chính thức chống rò rỉ theo URL; không dùng official split để chọn model.

## 2. Tạo Notebook

1. Tạo Kaggle Notebook mới và đính kèm Dataset vừa upload.
2. Trong **Settings**, chọn Accelerator là **GPU T4 x2** hoặc GPU bất kỳ.
3. Bật **Internet** ở lần chạy đầu tiên để tải PhoBERT và VnCoreNLP.
4. Upload hoặc dán `kaggle/train_phobert_kaggle.py` vào notebook.

## 3. Cài và chạy

Cell 1:

```python
!pip install -q -r /kaggle/input/<ten-dataset-code>/requirements.txt
```

Hoặc chạy trực tiếp:

```python
!pip install -q "transformers>=4.41,<4.47" datasets accelerate py_vncorenlp scikit-learn
```

Cell 2: sửa `INPUT_DIR` trong script nếu slug Kaggle khác, sau đó chạy:

```python
!python /kaggle/input/<ten-dataset-code>/train_phobert_kaggle.py
```

Nếu bạn upload script như một Dataset Code riêng, thay đường dẫn tương ứng. Một cách đơn giản hơn là tạo cell notebook và dán toàn bộ nội dung script vào.

## 4. Tải kết quả về dự án

Sau khi chạy, Kaggle tạo:

- `/kaggle/working/phobert_e2/e2_phobert_metrics.json`
- `/kaggle/working/phobert_e2/e2_phobert_test_predictions.csv`
- `/kaggle/working/phobert_e2/best_model/`

Tải hai tệp metrics/predictions về `outputs/`, không đưa checkpoint lớn lên Git. Gửi `e2_phobert_metrics.json` cho mình; mình sẽ so sánh E1/E2, cập nhật Excel và thực hiện phân tích lỗi.

## Điểm kiểm tra trước khi báo cáo

- `test_macro_f1` phải đến từ test set chạy sau cùng.
- `dev_macro_f1` là số liệu để chọn checkpoint/early stopping.
- Kiểm tra `split` trong JSON là `grouped by normalized URL`.
- Không thay đổi dữ liệu hoặc ngưỡng dựa trên kết quả test.
