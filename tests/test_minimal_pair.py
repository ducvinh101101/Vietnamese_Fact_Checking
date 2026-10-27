"""Test luật cặp-tối-thiểu (src/minimal_pair.py) và chọn câu bằng chứng (src/evidence_focus.py).

Deterministic, không cần PhoBERT. Mỗi test ghi rõ HÀNH VI mong muốn, gồm cả các ca
luật phải IM LẶNG (để chứng minh không bác bỏ bừa).
"""

from __future__ import annotations

import pytest

from src.evidence_focus import (
    SINGLE_VIEWS, VIEWS, average_probabilities, best_sentence_index, ensemble_texts, focus_text, split_sentences,
)
from src.minimal_pair import MinimalPairVerifier, analyse, refine, tokenize
from src.pipeline import FactCheckingPipeline
from src.schemas import Evidence, RetrievedEvidence, VerificationResult


def item(pid: str, content: str, score: float = 1.0) -> RetrievedEvidence:
    return RetrievedEvidence(Evidence(document_id=pid, passage_id=pid, content=content), score)


def verdict(label: str, cited: str = "p1", conf: float = 0.95) -> VerificationResult:
    return VerificationResult(label, conf, [cited] if label != "NOT_ENOUGH_INFO" else [], "fixed")


class Fixed:
    def __init__(self, label): self.label = label
    def verify(self, claim, items):
        return verdict(self.label, items[0].evidence.passage_id) if items else verdict("NOT_ENOUGH_INFO")


class Static:
    def __init__(self, items): self.items = items
    def search(self, claim, top_k=3): return self.items[:top_k]


SRC = "Doanh thu của tập đoàn đã tăng lên 12% so với năm trước nhờ thị trường nội địa phục hồi mạnh"


# ----------------------------------------------------------------------------- tokenize

def test_numbers_are_canonicalised_across_vietnamese_formats():
    assert tokenize("giá 1.500 đồng") == tokenize("giá 1500 đồng")
    assert tokenize("tăng 2,5%") == tokenize("tăng 2.5%")
    assert tokenize("giá 8.100") != tokenize("giá 9.200")


# ----------------------------------------------------------------------------- contradiction

@pytest.mark.parametrize("claim, kind", [
    (SRC.replace("tăng lên", "giảm xuống"), "direction"),
    (SRC.replace("đã tăng", "chưa tăng"), "negation"),
    (SRC.replace("12%", "21%"), "number"),
    (SRC.replace("đã tăng", "không tăng"), "negation"),
    (SRC.replace("phục hồi mạnh", "phục hồi mạnh").replace("Doanh thu", "Doanh thu"), None),   # y hệt: không phải mâu thuẫn
])
def test_single_flip_is_detected_with_the_right_kind(claim, kind):
    analysis = analyse(claim, SRC)
    if kind is None:
        assert analysis is not None and not analysis.contradiction and analysis.near_exact
    else:
        assert analysis is not None and analysis.contradiction and kind in analysis.kinds


def test_inserting_a_negation_word_is_a_contradiction():
    src = "Bộ Giáo dục cho biết có nhận được ý kiến của cử tri về vấn đề sách giáo khoa"
    claim = "Bộ Giáo dục cho biết không có nhận được ý kiến của cử tri về vấn đề sách giáo khoa"
    assert analyse(claim, src).contradiction


def test_khong_inside_compound_words_is_not_negation():
    src = "Chuyến bay của hãng hàng không này đã hạ cánh an toàn xuống sân bay quốc tế Nội Bài"
    claim = "Chuyến bay của hãng này đã hạ cánh an toàn xuống sân bay quốc tế Nội Bài"
    analysis = analyse(claim, src)
    assert analysis is None or not analysis.contradiction


def test_same_number_in_different_format_is_not_a_contradiction():
    src = "Giá lúa mì được giao dịch ở mức 1.500 đồng một kg tại cảng phía Bắc trong tuần qua"
    claim = "Giá lúa mì được giao dịch ở mức 1500 đồng một kg tại cảng phía Bắc trong tuần qua"
    assert not analyse(claim, src).contradiction


def test_two_flips_cancel_out():
    src = "Công ty đã tăng giá bán sản phẩm chủ lực trong quý này tại thị trường trong nước"
    claim = "Công ty chưa giảm giá bán sản phẩm chủ lực trong quý này tại thị trường trong nước"
    assert not analyse(claim, src).contradiction


def test_extra_fabricated_detail_is_not_a_contradiction():
    claim = SRC + " và đạt kỷ lục chưa từng có trong lịch sử 50 năm của công ty"
    analysis = analyse(claim, SRC)
    assert analysis is None or not analysis.contradiction


def test_unrelated_sentence_and_short_claim_are_ignored():
    assert analyse("Giá xăng tăng", "Giá xăng giảm") is None                      # quá ngắn
    assert analyse(SRC, "Đội tuyển bóng đá quốc gia thi đấu giao hữu tại sân Mỹ Đình tối qua") is None


def test_unexplained_synonym_substitution_is_not_flagged():
    claim = SRC.replace("thị trường nội địa", "thị trường trong nước")
    analysis = analyse(claim, SRC)
    assert analysis is None or not analysis.contradiction


# ----------------------------------------------------------------------------- refine()

def test_refine_overrides_supported_to_refuted_on_direction_swap():
    claim = SRC.replace("tăng lên", "giảm xuống")
    new, why = refine(claim, verdict("SUPPORTED"), [item("p1", SRC + ". Câu khác không liên quan.")])
    assert new.label == "REFUTED" and new.evidence_ids == ["p1"] and why.startswith("contradiction")


def test_refine_overrides_nei_too():
    claim = SRC.replace("đã tăng", "chưa tăng")
    assert refine(claim, verdict("NOT_ENOUGH_INFO"), [item("p1", SRC)])[0].label == "REFUTED"


def test_refine_keeps_models_own_refuted():
    claim = SRC.replace("tăng lên", "giảm xuống")
    original = verdict("REFUTED", "p9")
    new, why = refine(claim, original, [item("p1", SRC), item("p9", "Nội dung khác.")])
    assert new is original and why is None


def test_verbatim_claim_upgrades_wrong_refuted_to_supported():
    passage = "Câu mở đầu không liên quan gì tới chủ đề này cả. " + SRC + ". Câu kết thúc bài viết."
    new, why = refine(SRC, verdict("REFUTED"), [item("p1", passage)])
    assert new.label == "SUPPORTED" and why == "exact_support"


def test_exact_support_in_one_passage_beats_contradiction_in_another():
    claim = SRC.replace("tăng lên", "giảm xuống")
    old_article = claim.replace("giảm xuống", "tăng lên")          # bài cũ nói ngược lại
    new, _ = refine(claim, verdict("NOT_ENOUGH_INFO"), [item("old", old_article), item("new", claim)])
    assert new.label == "SUPPORTED" and new.evidence_ids == ["new"]


def test_refine_never_touches_unrelated_claims():
    original = verdict("SUPPORTED")
    new, why = refine("Hà Nội là thủ đô của nước Cộng hòa xã hội chủ nghĩa Việt Nam từ năm 1976",
                      original, [item("p1", SRC)])
    assert new is original and why is None


def test_disabled_wrapper_is_transparent():
    claim = SRC.replace("tăng lên", "giảm xuống")
    wrapper = MinimalPairVerifier(Fixed("SUPPORTED"), enabled=False)
    assert wrapper.verify(claim, [item("p1", SRC)]).label == "SUPPORTED"
    assert MinimalPairVerifier(Fixed("SUPPORTED")).verify(claim, [item("p1", SRC)]).label == "REFUTED"


def test_pipeline_flag_wires_minimal_pair_and_keeps_citation_valid():
    claim = SRC.replace("tăng lên", "giảm xuống")
    pipeline = FactCheckingPipeline(retriever=Static([item("p1", SRC)]), checker=Fixed("SUPPORTED"),
                                    minimal_pair=True)
    result, retrieved = pipeline.run(claim)
    assert result.label == "REFUTED" and set(result.evidence_ids) <= {i.evidence.passage_id for i in retrieved}
    plain = FactCheckingPipeline(retriever=Static([item("p1", SRC)]), checker=Fixed("SUPPORTED"))
    assert plain.run(claim)[0].label == "SUPPORTED"                  # mặc định giữ nguyên hành vi cũ


# ----------------------------------------------------------------------------- evidence_focus

PASSAGE = ("Phần mở đầu nói về bối cảnh chung của thị trường. Giá xăng RON 95 giảm 780 đồng một lít từ 15h hôm nay. "
           "Các mặt hàng dầu cũng điều chỉnh theo. Bộ Tài chính sẽ công bố thêm chi tiết.")


def test_split_sentences_keeps_abbreviations_and_decimals():
    parts = split_sentences("Họp tại TP. HCM vào sáng nay. Giá tăng 2.5 lần. Kết thúc.")
    assert parts == ["Họp tại TP. HCM vào sáng nay.", "Giá tăng 2.5 lần.", "Kết thúc."]


def test_best_sentence_is_the_one_covering_the_claim():
    sentences = split_sentences(PASSAGE)
    assert "RON 95" in sentences[best_sentence_index("Giá xăng RON 95 tăng 780 đồng một lít", sentences)]


def test_focus_views():
    claim = "Giá xăng RON 95 tăng 780 đồng một lít từ 15h hôm nay"
    assert focus_text(claim, PASSAGE, "passage") == PASSAGE
    first = focus_text(claim, PASSAGE, "focus_first")
    assert first.startswith("Giá xăng RON 95") and len(first.split()) == len(PASSAGE.split())
    only = focus_text(claim, PASSAGE, "focus_only")
    assert only.startswith("Giá xăng RON 95") and "mở đầu" not in only
    assert focus_text(claim, "Một câu duy nhất.", "focus_only") == "Một câu duy nhất."


def test_unknown_view_is_rejected_early():
    assert set(VIEWS) == {"passage", "focus_first", "focus_only", "ensemble"}
    with pytest.raises(ValueError):
        focus_text("a", "b", "bogus")
    with pytest.raises(ValueError):
        focus_text("a", "b", "ensemble")      # ensemble do verifier xử lý
    with pytest.raises(ValueError):
        FactCheckingPipeline(retriever=Static([]), checker=Fixed("NOT_ENOUGH_INFO"), evidence_view="bogus")


# ----------------------------------------------------------------------------- ensemble

def test_ensemble_texts_are_view_major_and_average_inverts_them():
    claim = "Giá xăng RON 95 tăng 780 đồng một lít từ 15h hôm nay"
    passages = [PASSAGE, "Một đoạn khác hoàn toàn."]
    flat = ensemble_texts(claim, passages)
    assert len(flat) == len(SINGLE_VIEWS) * len(passages)
    assert flat[0] == PASSAGE and flat[len(passages)].startswith("Giá xăng RON 95")      # view 1, passage 0
    probs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0],     # view passage:  p0, p1
             [0.0, 0.0, 1.0], [0.0, 1.0, 0.0],     # view focus_first
             [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]]     # view focus_only
    avg = average_probabilities(probs, len(SINGLE_VIEWS))
    assert all(abs(a - b) < 1e-9 for a, b in zip(avg[0], [1 / 3, 0.0, 2 / 3])) and avg[1] == [0.0, 1.0, 0.0]
    with pytest.raises(ValueError):
        average_probabilities(probs[:5], 3)


def test_pipeline_accepts_ensemble_view_with_non_phobert_checker():
    pipeline = FactCheckingPipeline(retriever=Static([item("p1", SRC)]), checker=Fixed("SUPPORTED"),
                                    evidence_view="ensemble")
    assert pipeline.run(SRC)[0].label == "SUPPORTED"


def test_guard_focus_coverage_is_configurable():
    from src.verdict_guard import guard_reason
    claim = "Ngân hàng Nhà nước điều chỉnh lãi suất điều hành từ ngày mai theo quyết định mới"
    passage = "Ngân hàng Nhà nước vừa công bố quyết định mới. Lãi suất điều hành được điều chỉnh vào tuần sau."
    result = verdict("SUPPORTED")
    strict = guard_reason(claim, result, [item("p1", passage)], 0.0, 0.9)
    loose = guard_reason(claim, result, [item("p1", passage)], 0.0, 0.2)
    assert strict is not None and loose is None
