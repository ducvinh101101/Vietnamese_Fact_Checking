import json

import pytest

from src.io_utils import load_evidence_jsonl
from src.schemas import Article, Claim


def test_article_and_claim_keep_the_required_linkage():
    article = Article(
        article_id="article_001",
        title="Tiêu đề",
        body="Nội dung",
        url="https://example.com/article",
        retrieved_at="2026-09-03T00:00:00Z",
        source_type="news",
        authority_score=0.8,
    )
    claim = Claim(claim_id="claim_001", article_id=article.article_id, text="Một claim nguyên tử.")

    assert claim.article_id == article.article_id
    assert article.authority_score == 0.8


def test_loader_accepts_contract_metadata_and_rejects_invalid_authority_score(tmp_path):
    path = tmp_path / "evidence.jsonl"
    record = {
        "document_id": "article_001",
        "passage_id": "article_001_p001",
        "content": "Evidence.",
        "source": "Example",
        "url": "https://example.com/article",
        "article_id": "article_001",
        "title": "Tiêu đề",
        "published_at": "2026-09-01T00:00:00Z",
        "retrieved_at": "2026-09-03T00:00:00Z",
        "source_type": "news",
        "authority_score": 0.8,
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    evidence = load_evidence_jsonl(path)
    assert evidence[0].title == "Tiêu đề"
    assert evidence[0].authority_score == 0.8

    record["authority_score"] = 1.1
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="authority_score"):
        load_evidence_jsonl(path)
