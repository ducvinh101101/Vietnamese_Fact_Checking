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
                    article_id=str(raw.get("article_id", raw["document_id"])),
                    title=_optional_text(raw.get("title")),
                    published_at=_optional_text(raw.get("published_at")),
                    retrieved_at=_optional_text(raw.get("retrieved_at")),
                    source_type=str(raw.get("source_type", "unknown")),
                    authority_score=_optional_score(raw.get("authority_score")),
                )
            )
    if not records:
        raise ValueError("Kho evidence không có bản ghi hợp lệ")
    return records


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_score(value: object) -> float | None:
    if value is None or value == "":
        return None
    score = float(value)
    if not 0 <= score <= 1:
        raise ValueError("authority_score phải nằm trong khoảng 0 đến 1")
    return score
