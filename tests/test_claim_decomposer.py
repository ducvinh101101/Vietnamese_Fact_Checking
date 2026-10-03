import pytest

from src.claim_decomposer import ClaimDecomposer
from src.schemas import Article


def make_article(**overrides):
    fields = {
        "article_id": "article_001",
        "title": "Thành phố công bố kế hoạch mới.",
        "body": (
            "Thành phố công bố kế hoạch mới. Kế hoạch áp dụng từ tháng 10; "
            "người dân có thể góp ý. Liệu chi phí có tăng không?"
        ),
        "url": "https://example.com/article",
        "retrieved_at": "2026-09-05T00:00:00Z",
        "published_at": "2026-09-01T00:00:00Z",
    }
    fields.update(overrides)
    return Article(**fields)


def test_decompose_keeps_article_linkage_and_filters_duplicate_title_and_question():
    claims = ClaimDecomposer().decompose(make_article())

    assert [claim.text for claim in claims] == [
        "Thành phố công bố kế hoạch mới.",
        "Kế hoạch áp dụng từ tháng 10",
        "người dân có thể góp ý.",
    ]
    assert {claim.article_id for claim in claims} == {"article_001"}
    assert {claim.published_at for claim in claims} == {"2026-09-01T00:00:00Z"}
    assert len({claim.claim_id for claim in claims}) == len(claims)


def test_claim_ids_are_deterministic_and_title_is_used_when_body_is_empty():
    article = make_article(title="Bộ Y tế công bố hướng dẫn mới.", body="")
    decomposer = ClaimDecomposer()

    first = decomposer.decompose(article)
    second = decomposer.decompose(article)

    assert [claim.text for claim in first] == ["Bộ Y tế công bố hướng dẫn mới."]
    assert [claim.claim_id for claim in first] == [claim.claim_id for claim in second]


def test_decompose_rejects_blank_article_id():
    with pytest.raises(ValueError, match="article_id"):
        ClaimDecomposer().decompose(make_article(article_id=""))
