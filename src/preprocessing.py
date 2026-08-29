"""Tiền xử lý tối thiểu, bảo toàn phủ định, số và tên riêng."""

import html
import re
import unicodedata

URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode, HTML, URL và khoảng trắng mà không bỏ stopword."""
    if not isinstance(text, str):
        raise TypeError("text phải là chuỗi")
    text = unicodedata.normalize("NFC", html.unescape(text))
    text = URL_PATTERN.sub(" ", text)
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def tokenize_for_retrieval(text: str) -> list[str]:
    """Token hóa đơn giản, ổn định để làm baseline BM25."""
    normalized = normalize_text(text).lower()
    return re.findall(r"[\wÀ-ỹ]+", normalized, flags=re.UNICODE)
