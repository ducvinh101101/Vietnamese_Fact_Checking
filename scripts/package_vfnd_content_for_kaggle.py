"""Đóng gói VFND article-only đã chuẩn hóa để chạy E10 trên Kaggle riêng tư."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed" / "vfnd_content" / "articles.parquet"
AUDIT = ROOT / "outputs" / "metrics" / "vfnd_content_audit.json"
OUTPUT = ROOT / "kaggle" / "vfnd_content.zip"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not INPUT.is_file() or not AUDIT.is_file():
        raise FileNotFoundError("Chạy scripts/prepare_vfnd_content.py trước khi đóng gói")
    metadata = json.loads(AUDIT.read_text(encoding="utf-8"))
    metadata["files"] = {INPUT.name: {"sha256": sha256(INPUT), "bytes": INPUT.stat().st_size}}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(INPUT, arcname=INPUT.name)
        archive.writestr("METADATA.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"{OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
