"""Kiểm chứng ĐỘ CHÍNH XÁC NHÃN của challenge set (scripts/challenge_set.py).

Phép đo chỉ đáng tin nếu nhãn vàng đúng. Các test này khẳng định mỗi claim thực sự
được tạo bằng đúng phép biến đổi đã khai báo, và loại trừ các bẫy làm sai nhãn đã
phát hiện khi soát tay (cụm giới hạn "chưa đến 50%", số là mã/tên "COP27", tháng vô
nghĩa "tháng 16", câu sai ngữ pháp "tăng xuống", câu hỏi...).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from scripts.challenge_set import (
    ANY_NUMBER, FABRICATED_CLAUSES, FICTIONAL_CLAIMS, build_challenge_set, load_passages,
    negate_da, normalize, perturb_number, swap_direction,
)

CORPUS = Path(__file__).resolve().parents[1] / "data/evidence/vifactcheck_passages.jsonl"
PER_CATEGORY = 60


# --------------------------------------------------------------------------- helpers

@pytest.mark.parametrize("sentence", [
    "lợi nhuận chỉ chưa đến 50% trong năm qua theo báo cáo của tập đoàn lớn",
    "cuộc gọi phải có độ dài 2 phút trở lên để tránh kẻ xấu mạo danh lừa đảo",
    "Hội nghị COP27 sẽ đóng một vai trò quan trọng đối với các nước đang phát triển",
    "Đội U20 Indonesia đã mơ về giải đấu lớn từ rất lâu trước khi bị tước quyền",
    "Sự kiện được tổ chức tại Ả Rập Xê Út vào tháng 12 năm ngoái với nhiều khách mời",
    "Lực lượng Quân khu 9 đã phối hợp chặt chẽ cùng chính quyền địa phương ở miền Tây",
    "Nhà thờ được xây dựng từ những năm 1160 và hoàn thành sau nhiều thế kỷ thi công",
    "Hai anh em vi vu trên chiếc Honda 50 của tôi qua cầu Sài Gòn mỗi tối cuối tuần",
])
def test_perturb_number_rejects_ambiguous_or_id_numbers(sentence):
    assert perturb_number(sentence, sentence) is None


def test_perturb_number_changes_exactly_one_quantity_and_keeps_vietnamese_format():
    s = "Lúa mì Úc được giao dịch ở mức 8.100 đồng/kg tại cảng phía Bắc trong tuần qua"
    claim, old, new = perturb_number(s, s)
    assert old == "8.100" and new not in s and re.fullmatch(r"\d{1,3}(\.\d{3})+", new)
    assert claim.replace(new, old) == s


def test_swap_direction_keeps_grammatical_pairs():
    assert "tăng lên" in swap_direction("Năm 2021 con số này giảm xuống còn 2,2 triệu bảng theo báo cáo")
    assert "giảm xuống" in swap_direction("Lãi suất cho vay và tiền gửi đều tăng lên, lần lượt ở mức 3%")
    assert swap_direction("Doanh thu tăng 12% nhưng lợi nhuận giảm 5% so với cùng kỳ năm trước") is None


def test_negate_da_skips_ungrammatical_and_already_negated():
    assert negate_da("Và tôi đã rất cố gắng giành cơ hội cuối trước khi giải đấu khép lại") is None
    assert negate_da("Ông ấy đã không tham dự cuộc họp quan trọng của hội đồng sáng nay") is None
    assert "chưa ký" in negate_da("Hai bên đã ký kết thỏa thuận hợp tác chiến lược trong lĩnh vực năng lượng")


# --------------------------------------------------------------------------- full set

@pytest.fixture(scope="module")
def corpus():
    if not CORPUS.exists():
        pytest.skip(f"Không có corpus: {CORPUS}")
    return load_passages(CORPUS)


@pytest.fixture(scope="module")
def items(corpus):
    return build_challenge_set(corpus, per_category=PER_CATEGORY, seed=42)


@pytest.fixture(scope="module")
def by_pid(corpus):
    return {p["passage_id"]: p["content"] for p in corpus}


def _cat(items, name):
    return [i for i in items if i.category == name]


def test_category_sizes_and_determinism(corpus, items):
    sizes = Counter(i.category for i in items)
    for cat in ("SUP_VERBATIM", "SUP_FORMAT", "REF_NUMBER", "REF_DIRECTION", "REF_NEGATION", "NEI_PARTIAL"):
        assert sizes[cat] == PER_CATEGORY, f"{cat} chỉ có {sizes[cat]}"
    again = build_challenge_set(corpus, per_category=PER_CATEGORY, seed=42)
    assert [i.claim for i in again] == [i.claim for i in items]


def test_no_source_sentence_reused(items):
    sources = [i.source_sentence for i in items if i.source_sentence]
    assert len(sources) == len(set(sources))


def test_supported_claims_are_verbatim_in_source(items, by_pid):
    for it in _cat(items, "SUP_VERBATIM"):
        assert it.claim in normalize(by_pid[it.source_passage_id]), it.id


def test_format_claims_only_change_whitespace_and_final_punctuation(items):
    for it in _cat(items, "SUP_FORMAT"):
        assert normalize(it.claim) == it.source_sentence.rstrip(".!?…"), it.id


def test_supported_claims_are_statements_not_questions(items):
    for it in _cat(items, "SUP_VERBATIM") + _cat(items, "SUP_FORMAT"):
        assert not it.source_sentence.rstrip().endswith("?"), it.id


def test_number_claims_change_exactly_one_number(items, by_pid):
    for it in _cat(items, "REF_NUMBER"):
        old, new = it.note.split(" -> ")
        assert ANY_NUMBER.findall(it.source_sentence) == [old], it.id
        assert ANY_NUMBER.findall(it.claim) == [new], it.id
        assert it.claim.replace(new, old, 1) == it.source_sentence, it.id
        assert new not in by_pid[it.source_passage_id], it.id       # số mới không có trong nguồn
        assert not re.search(r"tháng\s+(1[3-9]|[2-9]\d)\b", it.claim), it.id


def test_direction_claims_swap_exactly_one_direction_word(items):
    for it in _cat(items, "REF_DIRECTION"):
        src_dirs = re.findall(r"\b(tăng|giảm)\b", it.source_sentence)
        clm_dirs = re.findall(r"\b(tăng|giảm)\b", it.claim)
        assert len(src_dirs) == len(clm_dirs) == 1 and src_dirs != clm_dirs, it.id
        assert not re.search(r"\btăng xuống\b|\bgiảm lên\b", it.claim), it.id


def test_negation_claims_flip_exactly_one_da(items):
    for it in _cat(items, "REF_NEGATION"):
        assert it.claim == re.sub(r"\bđã\b", "chưa", it.source_sentence, count=1), it.id
        assert not re.search(r"\bchưa\s+(rất|quá|khá)\b", it.claim), it.id


def test_partial_claims_add_only_unsupported_fabricated_detail(items, corpus):
    blob = " ".join(p["content"] for p in corpus)
    for clause in FABRICATED_CLAUSES:
        assert clause not in blob                                  # chi tiết bịa không có trong kho
    for it in _cat(items, "NEI_PARTIAL"):
        assert it.claim.startswith(it.source_sentence.rstrip(" .!?…")), it.id
        assert any(clause in it.claim for clause in FABRICATED_CLAUSES), it.id


def test_fictional_claims_have_no_close_match_in_corpus(corpus):
    """Không passage nào chứa >= 1/3 số CẶP ÂM TIẾT ĐẶC TRƯNG của một claim bịa.

    Dùng cặp âm tiết (gần với từ tiếng Việt) và chỉ tính cặp hiếm (xuất hiện trong < 1%
    passage) để thước đo không bị nhiễu bởi cụm phổ biến như "việt nam", "thành công".
    """
    from collections import Counter

    def bigrams(text):
        syl = re.findall(r"\w+", text.casefold())
        return set(zip(syl, syl[1:]))

    passage_bigrams = [bigrams(p["content"]) for p in corpus]
    df = Counter(b for pb in passage_bigrams for b in pb)
    n = len(corpus)
    for claim in FICTIONAL_CLAIMS:
        distinct = {b for b in bigrams(claim) if df[b] / n < 0.01}
        assert len(distinct) >= 5, f"Claim bịa quá chung chung: {claim}"
        best = max(len(distinct & pb) / len(distinct) for pb in passage_bigrams)
        assert best < 0.34, f"Claim bịa có thể chạm chủ đề có thật trong kho: {claim} ({best:.0%})"
