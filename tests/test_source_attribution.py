from src.hybrid_retriever import FusedRetriever, HybridSourceRetriever, SparseBM25, build_windows, reciprocal_rank_fusion
from src.query_generation import generate_queries
from src.schemas import Evidence, RetrievedEvidence
from src.source_attribution import (
    AttributionThresholds, SourceAttributionPipeline, build_source_output, check_facets,
)
import pytest

from src.source_reranker import LexicalSourceScorer
from src.vi_text import (
    extract_dates, extract_entities, extract_numbers, sentence_windows, split_sentences, tokenize_bm25,
)


def evidence(passage_id: str, content: str, url: str = "https://vnexpress.net/a", domain: str = "vnexpress.net") -> Evidence:
    return Evidence(document_id=passage_id.split("-")[0], passage_id=passage_id, content=content,
                    source="VnExpress", url=url, domain=domain, source_type="news")


CORPUS = [
    evidence("d1-p1", "Bộ Y tế cho biết ngày 15/3/2023 cả nước ghi nhận 120 ca mắc mới. "
                      "Tỷ lệ tiêm chủng đạt 95%. Hà Nội có số ca cao nhất."),
    evidence("d2-p1", "Giá xăng RON 95 giảm 500 đồng mỗi lít từ chiều nay. Liên Bộ Công Thương - Tài chính điều hành.",
             "https://tuoitre.vn/b", "tuoitre.vn"),
    evidence("d3-p1", "Đội tuyển Việt Nam thắng Thái Lan 2-0 tại Mỹ Đình. Huấn luyện viên hài lòng với kết quả.",
             "https://thanhnien.vn/c", "thanhnien.vn"),
]


def test_sentence_split_and_windows_keep_overlap():
    text = "Câu một nói về A. Câu hai nói về B. Câu ba nói về C."
    assert len(split_sentences(text)) == 3
    assert sentence_windows(text, window=2, stride=1) == [
        "Câu một nói về A. Câu hai nói về B.", "Câu hai nói về B. Câu ba nói về C.",
    ]


def test_tokenizer_drops_stopwords_but_keeps_negation_and_bigrams():
    tokens = tokenize_bm25("Bộ Y tế không cho phép việc này")
    assert "của" not in tokens and "này" not in tokens
    assert "không" in tokens
    assert "y_tế" in tokens


def test_number_date_entity_extraction():
    assert extract_numbers("tăng 12,5% so với 3 triệu người, khoảng 1.200 ca") == {"12.5%", "3000000", "1200"}
    assert "15/03/2023" in extract_dates("ngày 15/3/2023")
    assert "03/2023" in extract_dates("trong tháng 3 năm 2023")
    assert "Bộ Y" in " ".join(extract_entities("Theo Bộ Y tế Hà Nội")) or "Hà Nội" in extract_entities("Theo Bộ Y tế Hà Nội")


def test_generate_queries_adds_keyword_query():
    queries = generate_queries("Theo Bộ Y tế, ngày 15/3/2023 cả nước có 120 ca mắc mới")
    kinds = [query.kind for query in queries]
    assert kinds[0] == "claim"
    assert "keywords" in kinds
    assert "120" in queries[1].text


def test_keyword_query_keeps_numbers_and_dates_as_written():
    """Truy vấn web phải dùng số/ngày như báo viết – không phải dạng chuẩn hóa 162400000000000 hay 01/01/2028."""
    claim = "Từ ngày 1/1/2028, Quốc hội chi gần 162.400 tỷ đồng cho 3 tuyến dài 430,5 km, tăng 15%."
    keywords = generate_queries(claim)[1].text
    for written in ("1/1/2028", "162.400 tỷ", "430,5", "15%"):
        assert written in keywords
    for normalized in ("162400000000000", "01/01/2028", "430.5"):
        assert normalized not in keywords
    assert keywords.split().count("2028") == 0 and keywords.count("162.400") == 1


def test_sparse_bm25_ignores_stopword_only_matches_and_rrf_orders():
    index = SparseBM25([["y_tế", "ca"], ["xăng"]])
    assert index.search(["xăng"], 5) == [(1, index.search(["xăng"], 5)[0][1])]
    assert index.search(["không_có"], 5) == []
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    assert fused[0][0] == "b"


def test_hybrid_retriever_returns_sentence_windows_with_parent_metadata():
    retriever = HybridSourceRetriever(CORPUS, window=1)
    results = retriever.search("giá xăng RON 95 giảm 500 đồng", 3)
    assert results[0].evidence.url == "https://tuoitre.vn/b"
    assert results[0].evidence.passage_id.startswith("d2-p1")
    assert all(results[i].score >= results[i + 1].score for i in range(len(results) - 1))
    assert len(build_windows(CORPUS, window=1)) > len(CORPUS)


def test_document_scope_windows_cross_passage_boundary():
    parts = [
        Evidence(document_id="d9", passage_id="d9_p002", content="Câu ba nói về giá điện. Câu bốn kết thúc bài."),
        Evidence(document_id="d9", passage_id="d9_p001", content="Câu một mở đầu. Câu hai nói về EVN tăng giá."),
    ]
    per_passage = build_windows(parts, window=2, stride=1, max_chars=600)
    per_document = build_windows(parts, window=2, stride=1, max_chars=600, scope="document")
    bridge = "Câu hai nói về EVN tăng giá. Câu ba nói về giá điện."
    assert bridge not in [item.content for item in per_passage]
    assert bridge in [item.content for item in per_document]
    assert per_document[0].content.startswith("Câu một")  # passage được xếp đúng thứ tự
    assert all(item.document_id == "d9" for item in per_document)


def test_fused_retriever_survives_failing_source():
    class Broken:
        def search(self, claim, top_k=3):
            raise RuntimeError("network down")

    fused = FusedRetriever([HybridSourceRetriever(CORPUS), Broken()])
    assert fused.search("Việt Nam thắng Thái Lan", 2)
    assert fused.last_errors


def test_facet_check_detects_number_conflict():
    passage = CORPUS[0].content
    assert check_facets("cả nước ghi nhận 120 ca mắc mới", passage).matched == ["số 120"]
    conflict = check_facets("cả nước ghi nhận 150 ca mắc mới", passage)
    assert conflict.conflicting == ["số 150"]
    assert check_facets("ngày 16/3/2023 có ca mắc", passage).has_conflict


@pytest.mark.parametrize("claim, passage, conflict", [
    # từ xấp xỉ: số gần đúng theo nghĩa của từ thì khớp
    ("Hơn 3.000 người tham dự.", "Có 3.200 người tham dự lễ hội.", False),
    ("Gần 5 triệu khách quốc tế.", "Đạt 4,8 triệu lượt khách quốc tế.", False),
    ("Khoảng 200 hộ dân bị ảnh hưởng.", "Có 215 hộ dân bị ảnh hưởng.", False),
    ("Trên 40% số hộ có điện mặt trời.", "Tỷ lệ này là 43%.", False),
    # ...nhưng lệch xa vẫn là lệch
    ("Hơn 3.000 người tham dự.", "Có 9.000 người tham dự lễ hội.", True),
    ("Gần 5 triệu khách quốc tế.", "Đạt 2,1 triệu lượt khách quốc tế.", True),
    ("Có 3.000 người tham dự.", "Có 3.200 người tham dự lễ hội.", True),  # không có từ xấp xỉ: so chính xác
    # ngày: chỉ so cùng loại (tháng ≠ năm, ngày/tháng ≠ tháng/năm)
    ("Tháng 11/2026 xuất khẩu tăng.", "Trong tháng 11 xuất khẩu tăng mạnh.", False),
    ("Ngày 21/11 khai mạc.", "Tháng 11/2026 có nhiều sự kiện.", False),
    ("Ngày 21/11 khai mạc.", "Ngày 22/11 khai mạc.", True),
    ("Năm 2025 xuất khẩu tăng.", "Năm 2024 xuất khẩu tăng.", True),
    # số trong đoạn đã khớp một số khác của claim thì không làm số còn lại thành "lệch"
    ("Quốc hội thông qua 3 luật, cấm lấy mô của người dưới 18 tuổi.", "Luật cấm lấy mô của người dưới 18 tuổi.", False),
    ("Có 150 ca mắc, 18 ca nặng.", "Ghi nhận 120 ca mắc, 18 ca nặng.", True),  # 120 không khớp số nào → lệch
    # số dính đơn vị ("1km") vẫn là số
    ("Kênh dài khoảng 4,7 km, chia 3 giai đoạn.", "Chỉ khoảng 1km kênh được làm xong; dự án chia 3 giai đoạn.", True),
])
def test_facet_check_number_qualifiers_and_date_kinds(claim, passage, conflict):
    assert check_facets(claim, passage).has_conflict is conflict


def test_require_claim_numbers_blocks_support_when_passage_omits_a_number():
    """Đoạn không nhắc tới số của claim (vd. tin bị sửa '1,7 → 4,7 km') thì chưa đủ để 'xác nhận'."""
    from src.source_attribution import FacetCheck

    facets = FacetCheck(matched=["số 3"], missing=["số 4.7"])
    probabilities = [0.95, 0.03, 0.02]
    lenient = SourceAttributionPipeline(object(), verifier=object(), thresholds=AttributionThresholds(0.5, 0.8))
    strict = SourceAttributionPipeline(object(), verifier=object(), thresholds=AttributionThresholds(0.5, 0.8),
                                       require_claim_numbers=True)
    assert lenient._status(0.9, probabilities, facets) == "supports"
    assert strict._status(0.9, probabilities, facets) == "related"
    assert strict._status(0.9, probabilities, FacetCheck(matched=["số 3"], missing=["tên riêng Hà Nội"])) == "supports"
    # số nằm ở đoạn khác của CÙNG bài thì không tính là thiếu
    assert strict._status(0.9, probabilities, facets, article_numbers={"số 4.7"}) == "supports"


def test_assign_statuses_pools_numbers_per_article():
    from src.source_attribution import FacetCheck, PassageAssessment

    def assessment(url, matched, missing):
        item = RetrievedEvidence(Evidence(url, url + "-p", "nội dung", url=url), 0.9)
        return PassageAssessment(item, 0.9, [0.95, 0.03, 0.02], FacetCheck(matched=matched, missing=missing), "")

    strict = SourceAttributionPipeline(object(), verifier=object(), thresholds=AttributionThresholds(0.5, 0.8),
                                       require_claim_numbers=True)
    statuses = [a.status for a in strict.assign_statuses([
        assessment("https://a.vn/1", ["số 3"], ["số 107"]),
        assessment("https://a.vn/1", ["số 107"], ["số 3"]),
        assessment("https://b.vn/2", ["số 3"], ["số 107"]),  # bài khác không có 107 → chưa xác nhận
    ])]
    assert statuses == ["supports", "supports", "related"]


def test_percent_ranges_are_numbers_not_dates():
    """'8-10%' không phải ngày 08/10; '15-35%' giữ được 35% (trước đây bị bỏ vì regex ngày bắt nhầm)."""
    assert extract_dates("giảm 8-10% tổng tiêu thụ") == set()
    assert {"10%", "35%"} <= extract_numbers("tiết kiệm 8-10%, giảm thải 15-35%")
    assert extract_dates("ngày 21-11") == {"21/11"} and extract_numbers("ngày 21-11") == set()


def test_extract_numbers_reads_numbers_with_attached_units():
    assert {"1", "50000", "3", "4.7"} <= extract_numbers("Chỉ 1km kênh, kho 50.000m², 3ha đất, dài 4,7km.")
    assert "19" in extract_numbers("COVID-19") and "2" not in extract_numbers("H2O")  # chữ dính TRƯỚC số: không phải số đo


def test_lexical_scorer_counts_approximate_numbers_like_facets():
    """Điểm liên quan không được phạt số mà facet coi là khớp ("hơn 430 km" ↔ "430,5 km")."""
    claim = "Ba tuyến cao tốc dài hơn 430 km với tổng vốn gần 162.400 tỷ đồng."
    approx = "Ba tuyến cao tốc dài khoảng 430,5 km, tổng mức đầu tư sơ bộ 162.393 tỷ đồng."
    exact = "Ba tuyến cao tốc dài khoảng 430 km, tổng mức đầu tư sơ bộ 162.400 tỷ đồng."
    far = "Ba tuyến cao tốc dài khoảng 900 km, tổng mức đầu tư sơ bộ 90.000 tỷ đồng."
    scorer = LexicalSourceScorer()
    s_approx, s_exact, s_far = scorer.score(claim, [approx, exact, far])
    # phần chi tiết cứng (0,30) như nhau; chỉ còn khác ở âm tiết "430,5"/"162.393" của phần độ phủ từ
    assert s_far < s_approx <= s_exact
    old = LexicalSourceScorer(approximate=False).score(claim, [approx])[0]
    assert s_approx - old == pytest.approx(0.30 * 2 / 2)  # 2 số khớp gần đúng / 2 chi tiết cứng


def test_lexical_scorer_is_absolute_and_ranks_relevant_higher():
    scores = LexicalSourceScorer().score("giá xăng RON 95 giảm 500 đồng", [CORPUS[1].content, CORPUS[2].content])
    assert 0 <= scores[1] < scores[0] <= 1


class FakeVerifier:
    def __init__(self, probabilities):
        self.probabilities = probabilities

    def predict_probabilities_batch(self, claim, evidences):
        return [self.probabilities for _ in evidences]


def pipeline(verifier=None):
    return SourceAttributionPipeline(HybridSourceRetriever(CORPUS, window=1), LexicalSourceScorer(), verifier,
                                     AttributionThresholds(relevance=0.4, lexical_support=0.6))


def test_pipeline_found_conflict_and_no_source():
    found = pipeline().run("Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert found.label == "SOURCE_FOUND"
    assert found.citations[0].item.evidence.domain == "tuoitre.vn"
    conflict = pipeline().run("Giá xăng RON 95 giảm 900 đồng mỗi lít")
    assert conflict.label == "SOURCE_CONFLICT"
    none = pipeline().run("Sao Hỏa có hồ nước ngọt khổng lồ được NASA công bố")
    assert none.label == "NO_SOURCE" and not none.citations


def test_pipeline_uses_trained_verifier_probabilities():
    refuted = pipeline(FakeVerifier([0.1, 0.8, 0.1])).run("Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert refuted.label == "SOURCE_CONFLICT"
    unsure = pipeline(FakeVerifier([0.2, 0.2, 0.6])).run("Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert unsure.label == "NO_SOURCE"
    supported = pipeline(FakeVerifier([0.9, 0.05, 0.05])).run("Giá xăng RON 95 giảm 500 đồng mỗi lít")
    assert supported.label == "SOURCE_FOUND"


def test_source_output_contract():
    output = build_source_output(pipeline().run("Giá xăng RON 95 giảm 500 đồng mỗi lít"))
    assert output["schema_version"] == "source-attribution/v1"
    assert output["verdict"]["label_text"] == "Có nguồn xác nhận"
    assert output["verdict"]["independent_sources"] == ["tuoitre.vn"]
    assert output["citations"][0]["url"].startswith("https://")
    assert output["queries"][0].startswith("Giá xăng")


def test_verifier_relevance_scorer_uses_non_nei_mass_and_blend():
    from src.source_reranker import VerifierRelevanceScorer

    scorer = VerifierRelevanceScorer(FakeVerifier([0.5, 0.3, 0.2]))
    assert scorer.score("claim", ["a", "b"]) == [0.8, 0.8]
    blended = VerifierRelevanceScorer(FakeVerifier([0.0, 0.0, 1.0]), blend=0.5)
    assert blended.score("giá xăng giảm", ["giá xăng giảm"])[0] > 0


def test_output_reports_web_status():
    """web_status: None khi không có web; trạng thái của WebRetriever; "error" khi nó ném ngoại lệ."""
    assert build_source_output(pipeline().run("Giá xăng RON 95 giảm 500 đồng mỗi lít"))["retrieval"]["web_status"] is None

    class WebRetriever:  # cùng tên lớp với retriever web thật
        def __init__(self, status=None, fail=False):
            self.last_status, self.fail = status, fail

        def search(self, claim, top_k=3):
            if self.fail:
                raise RuntimeError("boom")
            return []

    def run_with(web):
        fused = FusedRetriever([HybridSourceRetriever(CORPUS, window=1), web])
        source = SourceAttributionPipeline(fused, LexicalSourceScorer(), None,
                                           AttributionThresholds(relevance=0.4, lexical_support=0.6))
        return build_source_output(source.run("Giá xăng RON 95 giảm 500 đồng mỗi lít"))

    assert run_with(WebRetriever("pages_unreachable"))["retrieval"]["web_status"] == "pages_unreachable"
    assert run_with(WebRetriever("ok"))["retrieval"]["web_status"] == "ok"
    failed = run_with(WebRetriever(fail=True))
    assert failed["retrieval"]["web_status"] == "error"
    assert failed["verdict"]["label"] == "SOURCE_FOUND"  # kho cục bộ vẫn chạy
