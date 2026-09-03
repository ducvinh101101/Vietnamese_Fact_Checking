"""Build a local passage corpus from the official ViFactCheck parquet splits.

The source parquet files and generated JSONL are intentionally ignored by Git.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "vifactcheck"
DEFAULT_OUTPUT = ROOT / "data" / "evidence" / "vifactcheck_passages.jsonl"
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+(?=[\"“'A-ZÀ-ỴĐ])")
WHITESPACE = re.compile(r"\s+")


def normalise(text: object) -> str:
    return WHITESPACE.sub(" ", str(text or "")).strip()


def split_passages(context: str, max_chars: int) -> list[str]:
    sentences = [normalise(sentence) for sentence in SENTENCE_BOUNDARY.split(context)]
    sentences = [sentence for sentence in sentences if sentence]
    passages: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_chars:
            passages.append(current)
            current = sentence
        elif current:
            current = f"{current} {sentence}"
        else:
            current = sentence
    if current:
        passages.append(current)
    return passages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-chars", type=int, default=700)
    args = parser.parse_args()

    source_files = [args.input_dir / f"{split}-00000-of-00001.parquet" for split in ("train", "dev", "test")]
    missing = [str(path) for path in source_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Thiếu parquet ViFactCheck: {missing}")
    if args.max_chars < 100:
        raise ValueError("--max-chars phải ít nhất là 100")

    documents: dict[str, dict[str, str]] = {}
    for path in source_files:
        for row in pd.read_parquet(path, columns=["Context", "Author", "Url"]).itertuples(index=False):
            context, author, url = map(normalise, row)
            if not context or not url:
                continue
            documents.setdefault(url, {"content": context, "source": author or urlparse(url).netloc})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    records = 0
    with args.output.open("w", encoding="utf-8", newline="\n") as file:
        for document_number, (url, document) in enumerate(sorted(documents.items()), start=1):
            document_id = f"vifactcheck_{document_number:05d}"
            for passage_number, content in enumerate(split_passages(document["content"], args.max_chars), start=1):
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
    print(f"documents={len(documents)} passages={records} output={args.output}")


if __name__ == "__main__":
    main()
