"""Sinh nhiều truy vấn từ một claim (multi-query) cho retrieval mở.

Một câu claim nguyên văn thường dài và chứa từ chức năng; công cụ tìm kiếm
web và BM25 đều hoạt động tốt hơn khi có thêm một truy vấn ngắn tập trung vào
thực thể, con số và ngày tháng. Kết quả các truy vấn được gộp bằng RRF ở
``src.hybrid_retriever``.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.preprocessing import normalize_text
from src.vi_text import ClaimFacets, VIETNAMESE_STOPWORDS, surface_numbers_dates, syllables, unique


@dataclass(frozen=True)
class GeneratedQuery:
    kind: str  # "claim" | "keywords" | "entities"
    text: str


def generate_queries(claim: str, max_keywords: int = 12, ner: object | None = None) -> list[GeneratedQuery]:
    """Trả 1–3 truy vấn khác nhau, không trùng lặp, theo thứ tự ưu tiên.

    * ``claim``: claim đã chuẩn hóa – luôn có;
    * ``keywords``: thực thể + số/ngày + các âm tiết nội dung đầu tiên;
    * ``entities``: chỉ thực thể và con số (khi đủ đặc trưng) – hữu ích cho web.

    ``ner`` (tùy chọn) là đối tượng có ``extract_entities(text) -> list[str]``,
    ví dụ adapter VnCoreNLP NER; khi không có, dùng heuristic chữ hoa.
    """
    text = normalize_text(claim)
    if not text:
        raise ValueError("claim không được rỗng")
    facets = ClaimFacets.from_text(text)
    entities = list(facets.entities)
    if ner is not None:
        entities = unique([*getattr(ner, "extract_entities")(text), *entities])
    entities.sort(key=text.find)
    # Số/ngày như claim viết (báo cũng viết vậy); dạng chuẩn hóa 162400000000000 làm truy vấn web trượt.
    hard = unique([*entities, *surface_numbers_dates(text)])

    queries = [GeneratedQuery("claim", text)]
    # Bỏ token số: số/ngày đã có trong ``hard`` ở dạng nguyên văn ("1/1/2028" chứ không phải "1 1 2028").
    content = [token for token in syllables(text) if token not in VIETNAMESE_STOPWORDS and not token[0].isdigit()]
    entity_tokens = {token for entity in entities for token in syllables(entity)}
    keyword_terms = unique([*hard, *[token for token in content if token not in entity_tokens]])[:max_keywords]
    keywords = " ".join(keyword_terms)
    if keywords and keywords.casefold() != text.casefold():
        queries.append(GeneratedQuery("keywords", keywords))
    if len(hard) >= 2:
        entity_query = " ".join(hard)
        if entity_query.casefold() not in {query.text.casefold() for query in queries}:
            queries.append(GeneratedQuery("entities", entity_query))
    return queries
