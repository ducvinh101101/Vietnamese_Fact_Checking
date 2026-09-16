# Fine-tune PhoBERT với passage đã AI-review — RT-V1

## 1. Mục tiêu và tình trạng

RT-V1 tiếp tục fine-tune checkpoint E2 để verifier quen với passage BM25 truy xuất thay vì chỉ evidence annotation. Đây là **thí nghiệm với nhãn AI silver**, chưa được người duyệt toàn bộ, chưa bảo đảm tăng accuracy và không chứng minh đạt 80% ngoài thực tế.

Đã review đủ 540 cặp: 487 có nhãn AI đề xuất (44 SUPPORTED, 42 REFUTED, 401 NEI); 53 chưa chắc đã tách ra, không đưa vào bundle. Xem [báo cáo review](REVIEW_TRAIN_PAIRS_AI_V1.md).

Bundle đã được tạo tại `kaggle/retrieval_finetune_v1.zip` (khoảng 3,35 MB):

| File | Dùng làm gì |
| --- | --- |
| `train.parquet` | 5.562 cặp: 5.075 gold gốc đã khử trùng + 487 AI silver |
| `gold_train.parquet` | 5.075 cặp gold cho chạy đối chứng |
| `dev.parquet` | 1.080 cặp annotation gốc, chỉ chọn checkpoint/đánh giá phát triển |
| `MANIFEST.json` | Hash, nguồn gốc, số lượng, trọng số |
| `excluded_silver_conflicts.csv` | Cặp silver xung đột gold; hiện không có |

ZIP **không chứa test**. Không sửa train/dev gốc. Tệp silver có trọng số 0,5, gold có trọng số 1,0. Không nhân bản nhóm NEI. Trọng số này là cấu hình khởi đầu, chưa được chứng minh tối ưu.

## 2. Chạy trực tiếp trên Kaggle — một cell fine-tune

Chỉ cần thêm ZIP dữ liệu RT-V1 và thư mục model E2 vào Kaggle. **Không cần upload script Python, không dùng `subprocess`, `%run` hoặc đọc file code để thực thi.**

Cài thư viện một lần ở cell riêng; nếu đã cài thì bỏ qua:

```python
%pip install -q "transformers==4.46.3" "datasets>=3,<4" "accelerate>=0.34,<2" "pandas>=2.2,<3" "scikit-learn>=1.5,<2" pyarrow py_vncorenlp
```

Bật GPU và Internet để tải VnCoreNLP lần đầu; cần Java. Nếu vừa đổi thư viện đã import, restart kernel trước khi chạy. Không thay PyTorch GPU sẵn có bằng bản CPU.

### Cell fine-tune — dán toàn bộ đoạn dưới vào một cell

Sửa `DATA_INPUT`, `MODEL_DIR`, `OUTPUT_DIR` ở đầu cell. `DATA_INPUT` nhận ZIP đã đóng gói hoặc thư mục chứa các parquet và manifest. `MODEL_DIR` là thư mục E2, không phải file trọng số hay checkpoint E10.

```python
# CHỈ SỬA ĐƯỜNG DẪN VÀ TÙY CHỌN Ở ĐÂY, SAU ĐÓ CHẠY CẢ CELL.
import os
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # đặt trước khi import torch
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ZIP RT-V1 hoặc thư mục đã giải nén chứa MANIFEST.json và các parquet.
DATA_INPUT = Path("/kaggle/input/TEN_DATASET_DU_LIEU/retrieval_finetune_v1.zip")
# THƯ MỤC model E2 chứa config.json, trọng số và tokenizer.
MODEL_DIR = Path("/kaggle/input/TEN_DATASET_MODEL/best_model")
OUTPUT_DIR = Path("/kaggle/working/rt_v1_silver")

TRAIN_FILE = "train.parquet"  # đối chứng: "gold_train.parquet"
EXPERIMENT_NAME = "RT-V1"  # Ví dụ: "RT-V2-balanced" cho ZIP cân bằng nhãn.
EPOCHS = 2
MAX_STEPS = -1  # -1: chạy đầy đủ; 2: chỉ smoke test

"""RT-V1: continue E2 on gold train + optional AI silver; evaluate DEV only."""
from types import SimpleNamespace
import zipfile
import hashlib
import json
import os
from pathlib import Path

LABELS = ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


def checksum(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run_finetune():
    args = SimpleNamespace(
        data_dir=DATA_INPUT, model_dir=MODEL_DIR, output_dir=OUTPUT_DIR,
        train_file=TRAIN_FILE, experiment=EXPERIMENT_NAME, epochs=EPOCHS, max_steps=MAX_STEPS,
    )
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Use a fresh output directory to preserve prior results")
    if args.epochs < 1 or args.max_steps == 0 or args.max_steps < -1:
        raise ValueError("Invalid epochs/max-steps")

    import numpy as np
    import pandas as pd
    import py_vncorenlp
    import torch
    import torch.nn.functional as F
    import transformers
    from datasets import Dataset
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding, EarlyStoppingCallback, Trainer, TrainingArguments, set_seed

    if not torch.cuda.is_available():
        raise RuntimeError("Enable a Kaggle GPU before training")
    if args.data_dir.suffix.lower() == ".zip":
        extraction = args.output_dir / "input_data"
        with zipfile.ZipFile(args.data_dir) as archive:
            for member in archive.namelist():
                if not (extraction / member).resolve().is_relative_to(extraction.resolve()):
                    raise ValueError("Unsafe ZIP member")
            extraction.mkdir(parents=True, exist_ok=False)
            archive.extractall(extraction)
        args.data_dir = extraction
    manifest_path = args.data_dir / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest["files"].items():
        path = (args.data_dir / name).resolve()
        if path.parent != args.data_dir.resolve() or checksum(path) != expected:
            raise ValueError(f"Input checksum/path mismatch: {name}")
    train = pd.read_parquet(args.data_dir / args.train_file)
    dev = pd.read_parquet(args.data_dir / "dev.parquet")
    if set(train.Url) & set(dev.Url):
        raise ValueError("Train/dev URL overlap")
    if not train.sample_weight.isin([0.5, 1.0]).all() or not train.labels.isin([0, 1, 2]).all() or not dev.labels.isin([0, 1, 2]).all():
        raise ValueError("Invalid labels or weights")
    expected_mapping = {str(i): label for i, label in enumerate(LABELS)}
    model_config = json.loads((args.model_dir / "config.json").read_text())
    checkpoint_label_mapping = model_config.get("id2label")
    if checkpoint_label_mapping != expected_mapping:
        print(
            "Warning: checkpoint id2label metadata differs. "
            "Training will use the fixed label order: "
            "0=SUPPORTED, 1=REFUTED, 2=NOT_ENOUGH_INFO."
        )
    set_seed(42)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    segment_dir = (args.output_dir / "vncorenlp").resolve()
    segment_dir.mkdir(exist_ok=True)
    if not (segment_dir / "VnCoreNLP-1.2.jar").exists():
        py_vncorenlp.download_model(save_dir=str(segment_dir))
    segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(segment_dir))
    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), use_fast=False, local_files_only=True)
    truncation = {}

    def encode(frame, name):
        claims = [" ".join(segmenter.word_segment(str(s))) for s in frame.Statement]
        passages = [" ".join(segmenter.word_segment(str(s))) for s in frame.Evidence]
        full = tokenizer(claims, passages, truncation=False)
        truncation[name] = sum(len(ids) > 256 for ids in full["input_ids"])
        encoded = tokenizer(claims, passages, truncation=True, max_length=256)
        encoded["labels"] = frame.labels.astype(int).tolist()
        encoded["sample_weight"] = frame.sample_weight.tolist() if "sample_weight" in frame else [1.0] * len(frame)
        return Dataset.from_dict(encoded)

    train_data, dev_data = encode(train, "train"), encode(dev, "dev")
    model = AutoModelForSequenceClassification.from_pretrained(str(args.model_dir), local_files_only=True)
    model.config.id2label = dict(enumerate(LABELS))
    model.config.label2id = {label: idx for idx, label in enumerate(LABELS)}
    padding = DataCollatorWithPadding(tokenizer)

    def collate(features):
        weights = [f["sample_weight"] for f in features]
        batch = padding([{k: v for k, v in f.items() if k != "sample_weight"} for f in features])
        batch["sample_weight"] = torch.tensor(weights, dtype=torch.float32)
        return batch

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            inputs = dict(inputs)
            weights = inputs.pop("sample_weight")
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            losses = F.cross_entropy(outputs.logits.float(), labels, reduction="none")
            loss = (losses * weights).sum() / weights.sum()
            return (loss, outputs) if return_outputs else loss

    def metrics(pred):
        guesses = np.argmax(pred.predictions, axis=-1)
        return {"accuracy": float(accuracy_score(pred.label_ids, guesses)),
                "macro_f1": float(f1_score(pred.label_ids, guesses, labels=[0, 1, 2], average="macro", zero_division=0))}

    training_args = TrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"), learning_rate=1e-5,
        per_device_train_batch_size=8, per_device_eval_batch_size=16, gradient_accumulation_steps=2,
        num_train_epochs=args.epochs, max_steps=args.max_steps, weight_decay=0.01, warmup_ratio=0.1,
        fp16=True, eval_strategy="epoch", save_strategy="epoch", logging_steps=25,
        load_best_model_at_end=True, metric_for_best_model="macro_f1", greater_is_better=True,
        save_total_limit=2, seed=42, data_seed=42, report_to="none", remove_unused_columns=False,
    )
    trainer = WeightedTrainer(model=model, args=training_args, train_dataset=train_data, eval_dataset=dev_data,
                              data_collator=collate, compute_metrics=metrics,
                              callbacks=[EarlyStoppingCallback(early_stopping_patience=1)])
    before = trainer.evaluate(metric_key_prefix="before_dev")
    trainer.train()
    predicted = trainer.predict(dev_data, metric_key_prefix="dev")
    guesses = np.argmax(predicted.predictions, axis=-1)
    destination = args.output_dir / "best_model"
    trainer.save_model(str(destination))
    tokenizer.save_pretrained(str(destination))
    rows = dev[["Statement", "Evidence", "Url", "labels"]].copy()
    rows["prediction"] = guesses
    for i, name in enumerate(LABELS):
        rows[f"logit_{name}"] = predicted.predictions[:, i]
    rows.to_csv(args.output_dir / "dev_predictions.csv", index=False)
    model_files = sorted(p for p in args.model_dir.iterdir() if p.is_file())
    report = {"experiment": args.experiment, "train_file": args.train_file, "smoke_only": args.max_steps > 0,
              "train_rows": len(train), "dev_rows": len(dev), "before_dev": before, "after_dev": predicted.metrics,
              "dev_per_label": classification_report(dev.labels, guesses, labels=[0, 1, 2], target_names=LABELS, output_dict=True, zero_division=0),
              "truncated_pairs": truncation, "selection": "gold-evidence DEV Macro-F1; end-to-end promotion NOT evaluated",
              "training": {"lr": 1e-5, "epochs_max": args.epochs, "batch": 8, "gradient_accumulation": 2, "max_length": 256, "seed": 42, "ai_weight": 0.5},
              "versions": {"torch": torch.__version__, "transformers": transformers.__version__},
              "bundle_manifest_sha256": checksum(manifest_path), "initial_model_files": {p.name: checksum(p) for p in model_files},
              "best_model_files": {p.name: checksum(p) for p in destination.iterdir() if p.is_file()},
              "warning": "AI silver is not human gold; no test read, no claim of real-world 80%; recalibrate and rebuild aggregator for new logits"}
    (args.output_dir / "finetune_metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


run_finetune()
```

Cell tự đọc dữ liệu, tách từ, fine-tune, đánh giá dev và lưu kết quả. Không tự dò đường dẫn. Kiểm tra hash dữ liệu, URL train/dev, nhãn model và chống ghi đè kết quả được giữ lại.

### Chạy thử và chạy đối chứng bằng chính cell trên

- Chạy thử: đặt `MAX_STEPS = 2`, `OUTPUT_DIR = Path("/kaggle/working/rt_v1_smoke")`. Vẫn tiền xử lý và đánh giá dev đầy đủ, nhưng chỉ hai bước optimizer. Không dùng kết quả smoke làm kết quả nghiên cứu.
- Chạy đầy đủ: đặt lại `MAX_STEPS = -1`, giữ `TRAIN_FILE = "train.parquet"`, dùng output mới.
- Đối chứng: đổi `TRAIN_FILE = "gold_train.parquet"`, `OUTPUT_DIR = Path("/kaggle/working/rt_v1_gold_control")`, rồi chạy lại cell. **Giữ cùng MODEL_DIR E2**, không bắt đầu từ model vừa fine-tune.

Để chạy lại notebook, dùng output mới; không xóa hoặc ghi đè kết quả cũ. VnCoreNLP dùng JVM trong kernel: nếu gặp lỗi khởi tạo JVM khi chạy lại cell, restart kernel rồi chạy cell với đường dẫn output mới.

Cấu hình giữ nguyên: seed 42, learning rate 1e-5, tối đa 2 epoch, batch 8, tích lũy 2; silver trọng số 0,5. Hai lượt so cùng số epoch, không cùng tổng số bước vì kích thước train khác. Nếu hết VRAM, đổi batch thành 4 và tích lũy thành 4 trong cả hai lượt, ghi lại cấu hình thực chạy.

Giữ max_length 256 và tách từ VnCoreNLP theo [model card PhoBERT](https://huggingface.co/vinai/phobert-base); cell có ghi số cặp bị cắt token. Chọn checkpoint bằng dev Macro-F1 qua [Trainer 4.46.3](https://huggingface.co/docs/transformers/v4.46.3/en/main_classes/trainer), không phải đánh giá accuracy ngoài thực tế.

### Kết quả cần tải

Trong OUTPUT_DIR có `finetune_metrics.json`, `dev_predictions.csv` và toàn bộ thư mục `best_model/`. Giữ riêng kết quả đối chứng và silver. Không dùng gold-evidence dev accuracy thay cho độ chính xác toàn pipeline.

## 3. Sau khi tải về: chưa bật ngay model mới

Đặt model đối chứng tại `models/rt_v1_gold_control/best_model/` và ứng viên tại `models/rt_v1_silver/best_model/`. Không ghi đè `models/e2_phobert/best_model` và chưa đổi `configs/config.yaml` đang chạy.

Tạo hai **bản sao** config thử nghiệm, ví dụ `configs/rt_v1_gold_control.yaml` và `configs/rt_v1_silver.yaml`. Giữ corpus/BM25/top_k/max_length như config gốc, chỉ thay:

```yaml
verification:
  # Các khóa khác giữ nguyên từ bản sao configs/config.yaml
  model_path: models/rt_v1_silver/best_model
  temperature: 1.0
  decisive_min_confidence: 0.6
  retrieval_rank_bias: 1.0
  aggregation_model_path: null
```

Bản control dùng `models/rt_v1_gold_control/best_model`. Đoạn YAML trên **không phải file config đầy đủ**. `temperature=1.0` là chưa calibration; ngưỡng 0,6 là mức khởi đầu cố định cho cả hai lượt, chưa tối ưu cho checkpoint mới.

Không tái dùng AGG-V1 và temperature của E2 để khẳng định chất lượng checkpoint mới: chúng được fit trên logits cũ. Trước hết so sánh hai model với cùng policy fallback cố định trên dev:

```powershell
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v1_gold_control.yaml --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v1_gold_control_e2e_dev.json --predictions outputs/predictions/rt_v1_gold_control_e2e_dev.csv
py -3.13 scripts/evaluate_local_end_to_end.py --config configs/rt_v1_silver.yaml --split data/processed/vifactcheck_group_split/dev.parquet --metrics outputs/metrics/rt_v1_silver_e2e_dev.json --predictions outputs/predictions/rt_v1_silver_e2e_dev.csv
```

**Luôn truyền `--split .../dev.parquet`** vì mặc định script cũ là test. Dùng đường dẫn output mới cho mỗi lượt; evaluator hiện có thể ghi đè output nếu trùng tên.

Đối chiếu accuracy, Macro-F1, recall REFUTED, nhầm SUPPORTED↔REFUTED, tỷ lệ NEI và citation. Không chọn ứng viên chỉ vì gold-evidence accuracy tăng trong khi end-to-end giảm. Citation đúng URL không đồng nghĩa passage đủ chứng minh; cần đọc mẫu citation.

Nếu ứng viên tốt hơn: tạo cache dự đoán dev mới, hiệu chỉnh temperature/ngưỡng và fit lại aggregator theo quy trình tách nhóm URL. **Chưa có bước đó trong cell fine-tune này**. Không chạy thẳng `audit_accuracy_gap.py`/`calibrate_aggregation_guard.py` để đánh giá RT-V1: hiện hai script đó đọc cache E2 cũ và có thể ghi đè AGG đang dùng.

Chỉ sau khi hoàn tất đánh giá, khóa cả verifier lẫn policy mới xét thay config chạy. Test cũ đã được xem nhiều lần không đủ xác nhận chất lượng độc lập; muốn công bố ≥80% thực tế vẫn cần gold mới, có người duyệt và tách sự kiện.

## 4. Kiểm tra đã làm trên máy này

- Đọc và nhận xét đủ 540 cặp; giữ riêng 53 cặp không chắc.
- Xuất 487 silver, kiểm tra nguồn train/corpus và chống lẫn URL dev/test.
- Gộp train, kiểm tra nhãn xung đột, tạo ZIP chỉ có train/dev và manifest.
- Bộ test trước chuyển cell: 82 pass. Bản cell được kiểm tra cú pháp riêng, chưa xác minh chạy Trainer trên GPU.
- **Chưa chạy huấn luyện GPU trên Kaggle**; cell smoke là bước cần làm để kiểm tra môi trường và luồng Trainer thực tế trước hai lượt đầy đủ.

Các artifact phiên bản v1 đã tồn tại, không cần chạy lại script đóng gói. Để tái lập trong một checkout sạch, thứ tự là `materialize_train_pair_ai_review.py` → `export_reviewed_training_pairs.py --reviews data/evaluation/train_retrieved_pair_ai_review_v1.csv --allow-ai-reviewed --output data/processed/reviewed_retrieval/ai_silver_v1.parquet` → `build_retrieval_finetune_bundle.py`. Các script từ chối ghi đè phiên bản cũ để bảo toàn review và kết quả.
