"""RT-V1: continue E2 on gold train + optional AI silver; evaluate DEV only."""
import argparse
import hashlib
import json
import os
from pathlib import Path

LABELS = ["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


def checksum(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True, help="Extracted RT-V1 bundle directory")
    parser.add_argument("--model-dir", type=Path, required=True, help="Local E2 best_model folder, not a model ID")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--experiment", default="RT-V1")
    parser.add_argument("--train-file", choices=["train.parquet", "gold_train.parquet"], default="train.parquet")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=-1, help="Positive value is a smoke run, not a completed experiment")
    args = parser.parse_args()
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


if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    main()
