import json
from pathlib import Path

from src.schemas import Evidence


def load_evidence_jsonl(path: str | Path) -> list[Evidence]:
    """Đọc kho evidence JSONL và kiểm tra các trường bắt buộc."""
    records: list[Evidence] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            required = {"document_id", "passage_id", "content"}
            missing = required - raw.keys()
            if missing:
                raise ValueError(f"Dòng {line_number} thiếu trường: {sorted(missing)}")
            records.append(
                Evidence(
                    document_id=str(raw["document_id"]),
                    passage_id=str(raw["passage_id"]),
                    content=str(raw["content"]),
                    source=str(raw.get("source", "Không rõ nguồn")),
                    url=str(raw.get("url", "")),
                )
            )
    if not records:
        raise ValueError("Kho evidence không có bản ghi hợp lệ")
    return records
