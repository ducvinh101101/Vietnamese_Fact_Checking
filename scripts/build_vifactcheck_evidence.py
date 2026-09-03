"""Build a local passage corpus from the official ViFactCheck parquet splits.

The source parquet files and generated JSONL are intentionally ignored by Git.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "vifactcheck"
DEFAULT_OUTPUT = ROOT / "data" / "evidence" / "vifactcheck_passages.jsonl"
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+(?=[\"“'A-ZÀ-ỴĐ])")
WHITESPACE = re.compile(r"\s+")


def normalise(text: object) -> str:
    return WHITESPACE.sub(" ", str(text or "")).strip()


def split_long_text(text: str, max_chars: int) -> list[str]:
    """Split oversized text at a whitespace boundary when possible."""
    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        boundary = remaining.rfind(" ", 0, max_chars + 1)
        boundary = boundary if boundary > 0 else max_chars
        pieces.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def split_passages(context: str, max_chars: int) -> list[str]:
    sentences = [normalise(sentence) for sentence in SENTENCE_BOUNDARY.split(context)]
    sentences = [sentence for sentence in sentences if sentence]
    passages: list[str] = []
    current = ""
    for sentence in sentences:
        for piece in split_long_text(sentence, max_chars):
            if current and len(current) + len(piece) + 1 > max_chars:
                passages.append(current)
                current = piece
            elif current:
                current = f"{current} {piece}"
            else:
                current = piece
    if current:
        passages.append(current)
    return passages


def iter_source_rows(input_dir: Path) -> Iterator[tuple[object, object, object]]:
    """Read the official splits saved either as Parquet or Hugging Face Arrow."""
    parquet_paths = [input_dir / f"{split}-00000-of-00001.parquet" for split in ("train", "dev", "test")]
    if all(path.is_file() for path in parquet_paths):
        for path in parquet_paths:
            for row in pd.read_parquet(path, columns=["Context", "Author", "Url"]).itertuples(index=False):
                yield row
        return

    from datasets import load_from_disk

    try:
        dataset = load_from_disk(str(input_dir))
    except (FileNotFoundError, ValueError) as error:
        missing = [str(path) for path in parquet_paths if not path.is_file()]
        raise FileNotFoundError(
            "Không tìm thấy ViFactCheck dạng Parquet hoặc dataset Arrow đã lưu: "
            f"{input_dir}. Thiếu Parquet: {missing}"
        ) from error

    for split in ("train", "dev", "test"):
        if split not in dataset:
            raise ValueError(f"Dataset ViFactCheck thiếu split: {split}")
        rows = dataset[split]
        required = {"Context", "Author", "Url"}
        missing_columns = required - set(rows.column_names)
        if missing_columns:
            raise ValueError(f"Split {split} thiếu cột: {sorted(missing_columns)}")
        for row in rows:
            yield row["Context"], row["Author"], row["Url"]


def write_corpus(documents: dict[str, dict[str, str]], output: Path, max_chars: int) -> tuple[int, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    records = 0
    with output.open("w", encoding="utf-8", newline="\n") as file:
        for document_number, (url, document) in enumerate(sorted(documents.items()), start=1):
            document_id = f"vifactcheck_{document_number:05d}"
            for passage_number, content in enumerate(split_passages(document["content"], max_chars), start=1):
                json.dump(
                    {
                        "document_id": document_id,
                        "passage_id": f"{document_id}_p{passage_number:03d}",
                        "content": content,
                        "source": document["source"],
                        "url": url,
                    },
                    file,
                    ensure_ascii=False,
                )
                file.write("\n")
                records += 1
    return len(documents), records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-chars", type=int, default=700)
    args = parser.parse_args()

    if args.max_chars < 100:
        raise ValueError("--max-chars phải ít nhất là 100")

    documents: dict[str, dict[str, str]] = {}
    for row in iter_source_rows(args.input_dir):
        context, author, url = map(normalise, row)
        if not context or not url:
            continue
        documents.setdefault(url, {"content": context, "source": author or urlparse(url).netloc})

    document_count, records = write_corpus(documents, args.output, args.max_chars)
    print(f"documents={document_count} passages={records} output={args.output}")


if __name__ == "__main__":
    main()
