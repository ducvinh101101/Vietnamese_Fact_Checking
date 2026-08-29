import pytest

from src.preprocessing import normalize_text, tokenize_for_retrieval


def test_normalize_text_preserves_negation_and_number():
    assert normalize_text("  Không  có  123! ") == "Không có 123!"


def test_tokenizer_removes_url_but_keeps_vietnamese_words():
    assert tokenize_for_retrieval("Tin ở https://example.com không đúng") == ["tin", "ở", "không", "đúng"]


def test_normalize_requires_string():
    with pytest.raises(TypeError):
        normalize_text(None)  # type: ignore[arg-type]
