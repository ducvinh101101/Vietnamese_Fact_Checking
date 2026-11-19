"""Nạp biến môi trường từ file ``.env`` ở gốc dự án (không cần python-dotenv).

* Chỉ đọc dạng ``TEN=gia_tri`` (bỏ dòng trống và dòng bắt đầu bằng ``#``).
* KHÔNG ghi đè biến đã có trong môi trường (biến đặt bằng ``$env:...`` thắng).
* Bỏ qua giá trị rỗng, để ``TAVILY_API_KEY=`` chưa điền vẫn được coi là "không có key".
* Không bao giờ in hay log giá trị.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: str | Path = ROOT / ".env") -> list[str]:
    """Trả danh sách TÊN biến đã nạp (không trả giá trị)."""
    file = Path(path)
    if not file.is_file():
        return []
    loaded: list[str] = []
    for raw in file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not name.isidentifier() or not value or name in os.environ:
            continue
        os.environ[name] = value
        loaded.append(name)
    return loaded
