"""Normalize evidence text to NFC and remove unsafe invisible/control characters.

The script preserves every JSON record and identifier. It writes atomically, so a
failed transformation leaves the existing corpus unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path


CONTROL_PATTERN = re.compile(r"[\u200B-\u200D\uFEFF]|[\x00-\x08\x0B\x0C\x0E-\x1F]")
TEXT_FIELDS = ("content", "title", "source")


def configure_utf8_console() -> None:
    """Keep Vietnamese progress messages safe in legacy Windows terminals."""
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")


def clean_text(value: object) -> str:
    return CONTROL_PATTERN.sub("", unicodedata.normalize("NFC", str(value))).strip()


def clean_corpus(path: Path) -> tuple[int, int]:
    """Clean a JSONL corpus in place and return (records, changed_records)."""
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy corpus: {path}")
    changed = 0
    records = 0
    with path.open(encoding="utf-8") as source, tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False, dir=path.parent, suffix=".tmp"
    ) as destination:
        temporary_path = Path(destination.name)
        try:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    raise ValueError(f"Corpus có dòng trống tại dòng {line_number}")
                row = json.loads(line)
                before = dict(row)
                for field in TEXT_FIELDS:
                    if row.get(field) is not None:
                        row[field] = clean_text(row[field])
                destination.write(json.dumps(row, ensure_ascii=False) + "\n")
                records += 1
                changed += row != before
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    os.replace(temporary_path, path)
    return records, changed


def main() -> None:
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Đường dẫn JSONL corpus cần làm sạch")
    args = parser.parse_args()
    records, changed = clean_corpus(args.path)
    print(f"Đã làm sạch {changed}/{records} bản ghi: NFC + loại bỏ ký tự điều khiển/ẩn.")


if __name__ == "__main__":
    main()
