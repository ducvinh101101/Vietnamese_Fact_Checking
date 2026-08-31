"""Download the minimal VnCoreNLP word-segmentation assets on Windows."""
from pathlib import Path

import requests


BASE = "https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/master/"
FILES = {
    "VnCoreNLP-1.2.jar": "VnCoreNLP-1.2.jar",
    "models/wordsegmenter/vi-vocab": "models/wordsegmenter/vi-vocab",
    "models/wordsegmenter/wordsegmenter.rdr": "models/wordsegmenter/wordsegmenter.rdr",
}


def main() -> None:
    root = Path("models/vncorenlp")
    for relative, remote in FILES.items():
        target = root / relative
        if target.exists() and target.stat().st_size > 0:
            print(f"Exists: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(BASE + remote, timeout=120)
        response.raise_for_status()
        target.write_bytes(response.content)
        print(f"Downloaded: {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
