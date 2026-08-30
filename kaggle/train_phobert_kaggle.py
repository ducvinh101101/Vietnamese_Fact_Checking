"""E2 — Fine-tune PhoBERT-base trên Kaggle GPU.

Yêu cầu: upload vifactcheck_group_split.zip thành Kaggle Dataset, bật Internet
để tải PhoBERT/VnCoreNLP lần đầu, rồi chạy script trong Kaggle Notebook.
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import py_vncorenlp
import torch
from datasets import Dataset
from sklearn.metrics import accuracy_score, classification_report, f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)


# Đổi nếu bạn đặt Kaggle Dataset với slug khác.
INPUT_DIR = Path("/kaggle/input/vifactcheck-group-split")
WORK_DIR = Path("/kaggle/working/phobert_e2")
MODEL_NAME = "vinai/phobert-base"
MAX_LENGTH = 256
SEED = 42
LABEL_NAMES = ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


def prepare_input_dir() -> Path:
    """Dùng parquet trực tiếp hoặc tự giải nén ZIP upload lên Kaggle."""
    if list(INPUT_DIR.rglob("train.parquet")):
        return INPUT_DIR
    archives = list(INPUT_DIR.rglob("*.zip"))
    if not archives:
        raise FileNotFoundError(f"Không tìm thấy parquet hoặc ZIP dữ liệu bên dưới {INPUT_DIR}")
    extract_dir = WORK_DIR / "input_data"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archives[0]) as archive:
        archive.extractall(extract_dir)
    return extract_dir


def resolve_data_file(data_dir: Path, name: str) -> Path:
    matches = list(data_dir.rglob(f"{name}.parquet"))
    if not matches:
        raise FileNotFoundError(f"Không tìm thấy {name}.parquet bên dưới {data_dir}")
    return matches[0]


def setup_segmenter() -> py_vncorenlp.VnCoreNLP:
    vncorenlp_dir = WORK_DIR / "vncorenlp"
    if not vncorenlp_dir.exists():
        py_vncorenlp.download_model(save_dir=str(vncorenlp_dir))
    return py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(vncorenlp_dir))


def to_dataset(frame: pd.DataFrame, segmenter: py_vncorenlp.VnCoreNLP, tokenizer: AutoTokenizer) -> Dataset:
    claims = [" ".join(segmenter.word_segment(str(value))) for value in frame["Statement"]]
    evidence = [" ".join(segmenter.word_segment(str(value))) for value in frame["Evidence"]]
    encoded = tokenizer(claims, evidence, truncation=True, max_length=MAX_LENGTH)
    encoded["labels"] = frame["labels"].astype(int).tolist()
    return Dataset.from_dict(encoded)


def compute_metrics(prediction) -> dict[str, float]:
    labels = prediction.label_ids
    predicted = np.argmax(prediction.predictions, axis=-1)
    return {
        "accuracy": float(accuracy_score(labels, predicted)),
        "macro_f1": float(f1_score(labels, predicted, average="macro")),
    }


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("Kaggle GPU chưa được bật. Vào Settings → Accelerator → GPU rồi chạy lại.")
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    data_dir = prepare_input_dir()
    frames = {name: pd.read_parquet(resolve_data_file(data_dir, name)) for name in ("train", "dev", "test")}
    print({name: len(frame) for name, frame in frames.items()})
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)
    segmenter = setup_segmenter()
    datasets = {name: to_dataset(frame, segmenter, tokenizer) for name, frame in frames.items()}

    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=3)
    training_args = TrainingArguments(
        output_dir=str(WORK_DIR / "checkpoints"),
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        gradient_accumulation_steps=1,
        num_train_epochs=8,
        weight_decay=0.01,
        warmup_ratio=0.1,
        fp16=True,
        logging_steps=25,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=2,
        seed=SEED,
        report_to="none",
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=datasets["train"],
        eval_dataset=datasets["dev"],
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )
    trainer.train()
    dev_metrics = trainer.evaluate(datasets["dev"], metric_key_prefix="dev")
    test_output = trainer.predict(datasets["test"], metric_key_prefix="test")
    test_predictions = np.argmax(test_output.predictions, axis=-1)
    report = classification_report(
        frames["test"]["labels"], test_predictions,
        labels=[0, 1, 2], target_names=LABEL_NAMES, output_dict=True, zero_division=0,
    )
    metrics = {
        "experiment": "E2",
        "model": MODEL_NAME,
        "input": "word-segmented claim + gold evidence",
        "split": "grouped by normalized URL; seed=42; 70/15/15",
        "training": {
            "max_length": MAX_LENGTH,
            "learning_rate": 2e-5,
            "train_batch_size": 16,
            "epochs_max": 8,
            "early_stopping_patience": 2,
        },
        "dev_metrics": dev_metrics,
        "test_metrics": {key: value for key, value in test_output.metrics.items()},
        "test_per_label": {
            label: {
                "precision": float(report[label]["precision"]),
                "recall": float(report[label]["recall"]),
                "f1": float(report[label]["f1-score"]),
                "support": int(report[label]["support"]),
            }
            for label in LABEL_NAMES
        },
    }
    (WORK_DIR / "e2_phobert_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    output = frames["test"][["Statement", "Evidence", "Url", "labels"]].copy()
    output["prediction"] = test_predictions
    output.to_csv(WORK_DIR / "e2_phobert_test_predictions.csv", index=False, encoding="utf-8")
    trainer.save_model(str(WORK_DIR / "best_model"))
    tokenizer.save_pretrained(str(WORK_DIR / "best_model"))
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Hoàn thành. Tải toàn bộ kết quả từ: {WORK_DIR}")


if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    main()
