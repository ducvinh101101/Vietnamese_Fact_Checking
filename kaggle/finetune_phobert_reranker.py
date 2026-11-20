"""RR-V2: fine-tune PhoBERT thành cross-encoder reranker (liên quan / không liên quan).

Khởi tạo mặc định từ checkpoint RT-V2 của nhóm (đã học cặp claim–evidence
tiếng Việt), thay đầu phân loại 3 lớp bằng 2 lớp. Có thể khởi tạo từ
``vinai/phobert-base-v2`` để làm ablation.

Kaggle (GPU T4/P100):
    !pip install -q py_vncorenlp
    !unzip -q /kaggle/input/reranker-v2/reranker_v2.zip -d /kaggle/working/data
    !python finetune_phobert_reranker.py --data-dir /kaggle/working/data \
        --model-dir /kaggle/input/rt-v2-balanced/best_model --output-dir /kaggle/working/rr_v2

Đầu ra ``best_model/`` chép về ``models/phobert_reranker_v2/best_model`` rồi đặt
trong ``configs/source_attribution.yaml``:
    reranker: {model: models/phobert_reranker_v2/best_model, segment: true}
Sau đó chạy lại ``scripts/evaluate_source_attribution.py --sweep`` để chọn ngưỡng mới.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path


LABELS = ["UNRELATED", "RELATED"]


def checksum(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--model-dir", required=True, help="Thư mục RT-V2 best_model hoặc vinai/phobert-base-v2")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--vncorenlp-dir", type=Path, default=None, help="Dùng VnCoreNLP có sẵn thay vì tải về")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--max-steps", type=int, default=-1, help="Giá trị dương = chạy thử, không phải thí nghiệm")
    parser.add_argument("--allow-cpu", action="store_true", help="Chỉ dùng cho smoke test cục bộ")
    args = parser.parse_args()
    # py_vncorenlp đổi thư mục làm việc khi khởi tạo → mọi đường dẫn phải tuyệt đối.
    args.data_dir, args.output_dir = args.data_dir.resolve(), args.output_dir.resolve()
    if Path(args.model_dir).exists():
        args.model_dir = str(Path(args.model_dir).resolve())
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Dùng thư mục output mới để không ghi đè kết quả cũ")

    import numpy as np
    import pandas as pd
    import py_vncorenlp
    import torch
    import transformers
    from datasets import Dataset
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding,
                              EarlyStoppingCallback, Trainer, TrainingArguments, set_seed)

    if not torch.cuda.is_available() and not args.allow_cpu:
        raise RuntimeError("Bật GPU Kaggle trước khi train (hoặc --allow-cpu cho smoke test)")
    manifest = json.loads((args.data_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if checksum(args.data_dir / name) != expected:
            raise ValueError(f"Checksum không khớp: {name}")
    train = pd.read_parquet(args.data_dir / "train.parquet")
    dev = pd.read_parquet(args.data_dir / "dev.parquet")
    if set(train.Url) & set(dev.Url):
        raise ValueError("Train/dev trùng URL")

    set_seed(42)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    segment_dir = (args.vncorenlp_dir or args.output_dir / "vncorenlp").resolve()
    segment_dir.mkdir(exist_ok=True)
    if not (segment_dir / "VnCoreNLP-1.2.jar").exists():
        py_vncorenlp.download_model(save_dir=str(segment_dir))
    segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(segment_dir))
    cache = {}

    def segment(text):
        if text not in cache:
            cache[text] = " ".join(segmenter.word_segment(str(text)))
        return cache[text]

    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), use_fast=False)

    def encode(frame):
        encoded = tokenizer([segment(q) for q in frame["query"]], [segment(p) for p in frame["passage"]],
                            truncation=True, max_length=args.max_length)
        encoded["labels"] = frame.label.astype(int).tolist()
        return Dataset.from_dict(encoded)

    train_data, dev_data = encode(train), encode(dev)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(args.model_dir), num_labels=2, ignore_mismatched_sizes=True,
        id2label=dict(enumerate(LABELS)), label2id={label: i for i, label in enumerate(LABELS)},
    )

    def metrics(prediction):
        logits = prediction.predictions
        probabilities = torch.softmax(torch.tensor(logits), dim=-1)[:, 1].numpy()
        guesses = np.argmax(logits, axis=-1)
        return {"accuracy": float(accuracy_score(prediction.label_ids, guesses)),
                "f1_related": float(f1_score(prediction.label_ids, guesses, zero_division=0)),
                "auc": float(roc_auc_score(prediction.label_ids, probabilities))}

    training_args = TrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"), learning_rate=args.lr,
        per_device_train_batch_size=16, per_device_eval_batch_size=32, num_train_epochs=args.epochs,
        max_steps=args.max_steps, weight_decay=0.01, warmup_ratio=0.1, fp16=torch.cuda.is_available(),
        eval_strategy="epoch", save_strategy="epoch", logging_steps=50, load_best_model_at_end=True,
        metric_for_best_model="auc", greater_is_better=True, save_total_limit=1, seed=42, data_seed=42,
        report_to="none",
    )
    trainer = Trainer(model=model, args=training_args, train_dataset=train_data, eval_dataset=dev_data,
                      data_collator=DataCollatorWithPadding(tokenizer), compute_metrics=metrics,
                      callbacks=[EarlyStoppingCallback(early_stopping_patience=1)])
    before = trainer.evaluate(metric_key_prefix="before_dev")
    trainer.train()
    predicted = trainer.predict(dev_data, metric_key_prefix="dev")
    destination = args.output_dir / "best_model"
    trainer.save_model(str(destination))
    tokenizer.save_pretrained(str(destination))

    # Chỉ số xếp hạng: với mỗi claim, đoạn gold có đứng đầu các ứng viên không?
    dev = dev.copy()
    dev["related_probability"] = torch.softmax(torch.tensor(predicted.predictions), dim=-1)[:, 1].numpy()
    reciprocal_ranks, top1 = [], []
    for _, group in dev.groupby("query"):
        ordered = group.sort_values("related_probability", ascending=False).reset_index(drop=True)
        positives = ordered.index[ordered.label == 1].tolist()
        if positives:
            reciprocal_ranks.append(1 / (positives[0] + 1))
            top1.append(positives[0] == 0)
    dev.to_csv(args.output_dir / "dev_predictions.csv", index=False)
    report = {
        "experiment": "RR-V1 PhoBERT reranker", "init_model": str(args.model_dir), "smoke_only": args.max_steps > 0,
        "train_rows": len(train), "dev_rows": len(dev), "before_dev": before, "after_dev": predicted.metrics,
        "dev_mrr": float(np.mean(reciprocal_ranks)), "dev_top1": float(np.mean(top1)),
        "training": {"lr": args.lr, "epochs_max": args.epochs, "batch": 16, "max_length": args.max_length, "seed": 42},
        "versions": {"torch": torch.__version__, "transformers": transformers.__version__},
        "data_manifest": manifest["counts"],
        "note": "Chọn checkpoint theo AUC dev mức cặp; ngưỡng NO_SOURCE phải chọn lại bằng evaluate_source_attribution --sweep",
    }
    (args.output_dir / "finetune_metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    main()
