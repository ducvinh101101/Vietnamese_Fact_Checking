"""BE-V1: fine-tune bi-encoder tiếng Việt cho dense retrieval (thay E5-small của W2-04).

Dùng chung bundle ``reranker_v1.zip``: cặp dương (claim, Evidence gold) và âm
khó (cửa sổ bài khác do BM25 tìm). Hàm mất mát MultipleNegativesRankingLoss
(in-batch negatives + 1 hard negative mỗi claim).

Base mặc định là PhoBERT (cần tách từ VnCoreNLP, dùng mean pooling). Có thể
thay bằng ``bkai-foundation-models/vietnamese-bi-encoder`` (cũng PhoBERT) hoặc
``BAAI/bge-m3`` (không cần tách từ: thêm --no-segment).

Kaggle:
    !pip install -q py_vncorenlp sentence-transformers==3.3.1
    !python finetune_bi_encoder.py --data-dir /kaggle/working/data --output-dir /kaggle/working/be_v1

Dùng: chép ``best_model`` về ``models/bi_encoder_v1`` và đặt trong config
    local.dense: {model: models/bi_encoder_v1, segment: true}
"""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--base-model", default="vinai/phobert-base-v2")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--vncorenlp-dir", type=Path, default=None, help="Dùng VnCoreNLP có sẵn thay vì tải về")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-seq-length", type=int, default=256)
    parser.add_argument("--no-segment", action="store_true")
    args = parser.parse_args()
    # py_vncorenlp đổi thư mục làm việc khi khởi tạo → mọi đường dẫn phải tuyệt đối.
    args.data_dir, args.output_dir = args.data_dir.resolve(), args.output_dir.resolve()
    if Path(args.base_model).exists():
        args.base_model = str(Path(args.base_model).resolve())
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Dùng thư mục output mới")

    import numpy as np
    import pandas as pd
    import torch
    from datasets import Dataset
    from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments, losses
    from sentence_transformers.training_args import BatchSamplers

    train = pd.read_parquet(args.data_dir / "train.parquet")
    dev = pd.read_parquet(args.data_dir / "dev.parquet")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    segment = lambda text: text  # noqa: E731
    if not args.no_segment:
        import py_vncorenlp

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

    def triplets(frame):
        rows = []
        for query, group in frame.groupby("query"):
            positives = group[group.label == 1].passage.tolist()
            hard = group[(group.label == 0) & (group.kind == "hard_other_article")].passage.tolist()
            for positive in positives:
                if hard:
                    rows.append({"anchor": segment(query), "positive": segment(positive), "negative": segment(hard[0])})
        return Dataset.from_list(rows)

    train_data = triplets(train)
    model = SentenceTransformer(args.base_model)
    model.max_seq_length = args.max_seq_length
    training_args = SentenceTransformerTrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"), num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size, learning_rate=args.lr, warmup_ratio=0.1,
        fp16=torch.cuda.is_available(), batch_sampler=BatchSamplers.NO_DUPLICATES,
        save_strategy="epoch", save_total_limit=1, logging_steps=50, seed=42, report_to="none",
    )
    trainer = SentenceTransformerTrainer(model=model, args=training_args, train_dataset=train_data,
                                         loss=losses.MultipleNegativesRankingLoss(model))
    trainer.train()
    destination = args.output_dir / "best_model"
    model.save(str(destination))

    # Đánh giá nhanh trên dev: gold có đứng đầu trong nhóm ứng viên của claim không.
    top1, reciprocal = [], []
    for query, group in dev.groupby("query"):
        if not (group.label == 1).any():
            continue
        q = model.encode([segment(query)], normalize_embeddings=True)
        p = model.encode([segment(text) for text in group.passage], normalize_embeddings=True)
        order = np.argsort(-(p @ q[0]))
        labels = group.label.to_numpy()[order]
        first = int(np.argmax(labels == 1))
        top1.append(first == 0)
        reciprocal.append(1 / (first + 1))
    report = {"experiment": "BE-V1 bi-encoder", "base_model": args.base_model, "train_triplets": len(train_data),
              "dev_top1": float(np.mean(top1)), "dev_mrr": float(np.mean(reciprocal)), "segmented": not args.no_segment}
    (args.output_dir / "finetune_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    main()
