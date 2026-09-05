"""E10 — PhoBERT content-risk trên VFND article-only bằng nested group CV.

Chạy trên Kaggle GPU; E10 là article-level risk classification, tách hoàn toàn
khỏi claim verification/RAG. Dữ liệu được upload riêng tư dưới dạng vfnd_content.zip.
"""

from __future__ import annotations

import json
import os
import zipfile
from hashlib import sha256
from inspect import signature
from pathlib import Path

import numpy as np
import pandas as pd
import py_vncorenlp
import torch
from datasets import Dataset
from sklearn.metrics import classification_report, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding, EarlyStoppingCallback, Trainer, TrainingArguments


INPUT_DIR = Path("/kaggle/input/vfnd-content")
WORK_DIR = Path("/kaggle/working/phobert_e10")
MODEL_NAME = "vinai/phobert-base"
MAX_LENGTH = 256
SEED = 42


def prepare_data() -> pd.DataFrame:
    matches = list(INPUT_DIR.rglob("articles.parquet"))
    if not matches:
        archives = list(INPUT_DIR.rglob("*.zip"))
        if not archives:
            raise FileNotFoundError("Không tìm thấy articles.parquet hoặc vfnd_content.zip trong Kaggle input")
        unpacked = WORK_DIR / "input"
        unpacked.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archives[0]) as archive:
            archive.extractall(unpacked)
        matches = list(unpacked.rglob("articles.parquet"))
    frame = pd.read_parquet(matches[0]).reset_index(drop=True)
    required = {"title", "body", "source_domain", "label"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Dữ liệu E10 thiếu cột: {sorted(missing)}")
    return frame


def setup_segmenter() -> py_vncorenlp.VnCoreNLP:
    directory = WORK_DIR / "vncorenlp"
    if not directory.exists():
        py_vncorenlp.download_model(save_dir=str(directory))
    return py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(directory))


def encode(frame: pd.DataFrame, segmenter: py_vncorenlp.VnCoreNLP, tokenizer: AutoTokenizer) -> Dataset:
    text = [f"[TITLE] {title} [BODY] {body}" for title, body in zip(frame["title"], frame["body"])]
    segmented = [" ".join(segmenter.word_segment(value)) for value in text]
    encoded = tokenizer(segmented, truncation=True, max_length=MAX_LENGTH)
    encoded["labels"] = frame["label"].astype(int).tolist()
    return Dataset.from_dict(encoded)


def metrics(prediction) -> dict[str, float]:
    labels = prediction.label_ids
    predicted = np.argmax(prediction.predictions, axis=-1)
    return {"macro_f1": float(f1_score(labels, predicted, average="macro", zero_division=0))}


def calibrate_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    logits_tensor = torch.tensor(logits, dtype=torch.float32)
    labels_tensor = torch.tensor(labels, dtype=torch.long)
    temperature = torch.nn.Parameter(torch.ones(1))
    optimizer = torch.optim.LBFGS([temperature], lr=0.1, max_iter=50)
    loss_fn = torch.nn.CrossEntropyLoss()

    def closure():
        optimizer.zero_grad()
        loss = loss_fn(logits_tensor / temperature.clamp(min=0.05), labels_tensor)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(temperature.detach().clamp(min=0.05).item())


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("E10 yêu cầu Kaggle GPU. Bật Accelerator → GPU rồi chạy lại.")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    frame = prepare_data()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)
    segmenter = setup_segmenter()
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    text_index = np.arange(len(frame))
    oof_probability = np.zeros(len(frame), dtype=float)
    oof_prediction = np.zeros(len(frame), dtype=int)
    oof_fold = np.full(len(frame), -1, dtype=int)
    folds: list[dict[str, object]] = []

    for fold, (outer_train, outer_test) in enumerate(outer.split(text_index, frame["label"], frame["source_domain"])):
        train_frame = frame.iloc[outer_train].reset_index(drop=True)
        inner = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED + fold)
        train_local, dev_local = next(inner.split(np.arange(len(train_frame)), train_frame["label"], train_frame["source_domain"]))
        fit_frame = train_frame.iloc[train_local].reset_index(drop=True)
        dev_frame = train_frame.iloc[dev_local].reset_index(drop=True)
        test_frame = frame.iloc[outer_test].reset_index(drop=True)
        datasets = {name: encode(part, segmenter, tokenizer) for name, part in {"train": fit_frame, "dev": dev_frame, "test": test_frame}.items()}
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
        training_options = {
            "output_dir": str(WORK_DIR / f"fold_{fold}"), "learning_rate": 2e-5,
            "per_device_train_batch_size": 8, "per_device_eval_batch_size": 16,
            "num_train_epochs": 8, "weight_decay": 0.01, "warmup_ratio": 0.1, "fp16": True,
            "save_strategy": "epoch", "load_best_model_at_end": True,
            "metric_for_best_model": "macro_f1", "greater_is_better": True, "save_total_limit": 1,
            "seed": SEED + fold, "report_to": "none",
        }
        # Transformers 5 đổi tên evaluation_strategy thành eval_strategy.
        evaluation_key = "eval_strategy" if "eval_strategy" in signature(TrainingArguments).parameters else "evaluation_strategy"
        training_options[evaluation_key] = "epoch"
        args = TrainingArguments(**training_options)
        trainer_options = {
            "model": model, "args": args, "train_dataset": datasets["train"], "eval_dataset": datasets["dev"],
            "data_collator": DataCollatorWithPadding(tokenizer=tokenizer), "compute_metrics": metrics,
            "callbacks": [EarlyStoppingCallback(early_stopping_patience=2)],
        }
        processing_key = "processing_class" if "processing_class" in signature(Trainer).parameters else "tokenizer"
        trainer_options[processing_key] = tokenizer
        trainer = Trainer(**trainer_options)
        trainer.train()
        dev_output = trainer.predict(datasets["dev"])
        temperature = calibrate_temperature(dev_output.predictions, dev_output.label_ids)
        test_output = trainer.predict(datasets["test"])
        probabilities = torch.softmax(torch.tensor(test_output.predictions) / temperature, dim=-1)[:, 1].numpy()
        oof_probability[outer_test] = probabilities
        oof_prediction[outer_test] = (probabilities >= 0.5).astype(int)
        oof_fold[outer_test] = fold
        test_ids = ",".join(sorted(test_frame["article_id"].astype(str)))
        folds.append({
            "fold": fold,
            "temperature": round(temperature, 4),
            "train_records": len(fit_frame),
            "dev_records": len(dev_frame),
            "test_records": len(test_frame),
            "test_article_ids_sha256": sha256(test_ids.encode("utf-8")).hexdigest(),
        })

    report = classification_report(frame["label"], oof_prediction, labels=[0, 1], target_names=["REAL", "FAKE"], output_dict=True, zero_division=0)
    result = {
        "experiment": "E10", "task": "content-risk only; not claim verification/evidence", "dataset": "VFND article-only v1.1.1",
        "protocol": "5-fold outer + 3-fold inner StratifiedGroupKFold by source_domain; temperature scaling on inner dev; seed=42",
        "metrics": {"macro_f1": float(f1_score(frame["label"], oof_prediction, average="macro", zero_division=0)), "roc_auc": float(roc_auc_score(frame["label"], oof_probability)), "confusion_matrix": confusion_matrix(frame["label"], oof_prediction, labels=[0, 1]).tolist(), "per_label": {label: {key: float(value) for key, value in report[label].items()} for label in ("REAL", "FAKE")}},
        "folds": folds,
    }
    pd.DataFrame({"article_id": frame["article_id"], "url": frame["url"], "source_domain": frame["source_domain"], "fold": oof_fold, "label": frame["label"], "prediction": oof_prediction, "fake_risk_score": oof_probability.round(6)}).to_csv(WORK_DIR / "e10_vfnd_content_oof_predictions.csv", index=False)
    (WORK_DIR / "e10_phobert_content_metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
