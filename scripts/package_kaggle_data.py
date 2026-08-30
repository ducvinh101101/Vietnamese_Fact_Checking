"""Đóng gói split ViFactCheck chống rò rỉ để upload lên Kaggle."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed" / "vifactcheck_group_split"
REPORT = ROOT / "outputs" / "metrics" / "vifactcheck_group_split_report.json"
OUTPUT = ROOT / "kaggle" / "vifactcheck_group_split.zip"


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files = [DATA_DIR / f"{name}.parquet" for name in ("train", "dev", "test")]
    missing = [str(path) for path in files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Thiếu các tệp split: {missing}")
    metadata = json.loads(REPORT.read_text(encoding="utf-8"))
    metadata["files"] = {path.name: {"sha256": checksum(path), "bytes": path.stat().st_size} for path in files}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
        archive.writestr("METADATA.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"{OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
