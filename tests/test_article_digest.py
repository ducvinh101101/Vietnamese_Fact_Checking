from src.article_digest import build_digest, claim_units
from src.schemas import Evidence, RetrievedEvidence
from src.source_attribution import AttributionThresholds, SourceAttributionPipeline

ARTICLE = [
    "Honor vừa giới thiệu mẫu máy tính bảng Pad X9b Max. Máy có màn hình 13 inch, độ phân giải cao.",
    "Thiết bị dùng viên pin 10.100 mAh, hỗ trợ sạc nhanh 35W. Thời lượng dùng khoảng hai ngày.",
    "Pad X9b Max được bán tại Việt Nam với giá 12,99 triệu đồng cho phiên bản 128 GB.",
]
CLAIM = "Pad X9b Max của Honor có màn hình 13 inch, pin 10.100 mAh và giá 12,99 triệu đồng cho bản 128 GB."


def test_claim_units_split_on_commas_and_conjunctions():
    units = claim_units(CLAIM)
    assert len(units) >= 2
    assert any("13 inch" in u for u in units) and any("12,99 triệu" in u for u in units)  # không tách "12,99"


def test_digest_collects_sentences_for_each_unit_in_article_order():
    digest = build_digest(CLAIM, ARTICLE)
    assert "13 inch" in digest and "10.100 mAh" in digest and "12,99 triệu" in digest
    assert digest.index("13 inch") < digest.index("10.100") < digest.index("12,99")
    assert "hai ngày" not in digest


def test_digest_keeps_sentence_with_conflicting_number():
    """Claim sửa số vẫn kéo câu chứa số thật vào bản tóm tắt (để verifier thấy lệch)."""
    digest = build_digest("Pad X9b Max có giá 15,99 triệu đồng cho bản 128 GB.", ARTICLE)
    assert "12,99 triệu" in digest


def test_digest_respects_limits_and_empty_input():
    assert build_digest(CLAIM, []) == ""
    assert len(build_digest(CLAIM, ARTICLE, max_sentences=1)) < 120


class _Retriever:
    def __init__(self, items, article):
        self.items, self.article = items, article

    def search(self, claim, top_k=3):
        return self.items[:top_k]

    def article_passages(self, document_id):
        return self.article if document_id == "web-honor" else []


class _Scorer:
    def score(self, claim, passages):
        return [0.9 if "12,99" in p and "13 inch" in p else 0.6 for p in passages]


class _Verifier:
    """SUPPORTED chỉ khi đoạn có đủ cả ba chi tiết."""

    def predict_probabilities_batch(self, claim, evidences):
        return [[0.9, 0.05, 0.05] if all(k in e for k in ("13 inch", "10.100", "12,99")) else [0.05, 0.9, 0.05]
                for e in evidences]


def _evidence(pid, text):
    return Evidence(document_id="web-honor", passage_id=pid, content=text, source="VnExpress",
                    url="https://vnexpress.net/honor-1.html", domain="vnexpress.net")


def test_pipeline_digest_turns_partial_windows_into_found():
    items = [RetrievedEvidence(_evidence(f"web-honor-p0{i}", text), 0.5) for i, text in enumerate(ARTICLE, 1)]
    thresholds = AttributionThresholds(relevance=0.55, support=0.6)
    plain = SourceAttributionPipeline(_Retriever(items, ARTICLE), _Scorer(), _Verifier(), thresholds)
    digest = SourceAttributionPipeline(_Retriever(items, ARTICLE), _Scorer(), _Verifier(), thresholds,
                                       article_digest={"max_articles": 3})
    assert plain.run(CLAIM).label == "SOURCE_CONFLICT"
    result = digest.run(CLAIM)
    assert result.label == "SOURCE_FOUND"
    assert result.citations[0].item.evidence.passage_id.endswith("-digest")
