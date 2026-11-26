"""Bản tóm tắt cả bài: gom các câu của MỘT bài khớp từng ý của claim thành một đoạn ngắn.

Vì sao: claim của người dùng thường gộp thông tin từ nhiều câu của cùng bài ("màn hình 13 inch, pin 10.100 mAh,
giá 12,99 triệu"), trong khi pipeline chấm từng cửa sổ ~3 câu – cửa sổ nào cũng thiếu một phần nên verifier đánh
"thiếu"/"mâu thuẫn" dù cả bài xác nhận. Bản tóm tắt được chấm như một đoạn bình thường (verifier + facet + ngưỡng),
nên claim bị sửa chi tiết vẫn ra mâu thuẫn: câu chứa chi tiết thật được chọn vào bản tóm tắt.
"""

from __future__ import annotations

import re
from typing import Sequence

from src.vi_text import content_syllables, extract_dates, extract_numbers, split_sentences

# Ranh giới ý trong câu tin tức: dấu phẩy/chấm phẩy và các liên từ nối mệnh đề.
# Dấu phẩy thập phân ("12,99") không phải ranh giới.
UNIT_BOUNDARY = re.compile(r"\s*(?:,(?!\d)|;|\bvà\b|\btrong đó\b|\bkhiến\b|\bsau khi\b|\bvới\b)\s*")
MIN_UNIT_SYLLABLES = 4


def claim_units(claim: str) -> list[str]:
    """Tách claim thành các ý; ý quá ngắn (< 4 âm tiết nội dung) nhập vào ý trước."""
    units: list[str] = []
    for part in (p for p in UNIT_BOUNDARY.split(claim) if p and p.strip()):
        if units and len(content_syllables(part)) < MIN_UNIT_SYLLABLES:
            units[-1] = f"{units[-1]} {part}"
        else:
            units.append(part)
    return units


def _coverage(terms: set[str], sentence_terms: set[str]) -> float:
    return len(terms & sentence_terms) / len(terms) if terms else 0.0


def build_digest(claim: str, passages: Sequence[str], max_sentences: int = 4, max_chars: int = 700,
                 min_unit_coverage: float = 0.4) -> str:
    """Chọn câu phủ tốt nhất cho từng ý + câu chứa số/ngày của claim, giữ thứ tự trong bài.

    Trả "" nếu không chọn được câu nào. Câu trùng (cửa sổ chồng lấn) chỉ tính một lần.
    """
    sentences: list[str] = []
    seen: set[str] = set()
    for passage in passages:
        for sentence in split_sentences(passage):
            key = " ".join(sentence.casefold().split())
            if key not in seen:
                seen.add(key)
                sentences.append(sentence)
    if not sentences:
        return ""
    terms = [set(content_syllables(sentence)) for sentence in sentences]
    picked: list[int] = []

    def pick(index: int) -> None:
        if index not in picked:
            picked.append(index)

    for unit in claim_units(claim):
        unit_terms = set(content_syllables(unit))
        if not unit_terms:
            continue
        best = max(range(len(sentences)), key=lambda i: (_coverage(unit_terms, terms[i]), -i))
        if _coverage(unit_terms, terms[best]) >= min_unit_coverage:
            pick(best)
    # Câu chứa số/ngày của claim (báo hay tách số ra câu riêng) – cả khi số đó khác (để verifier thấy lệch).
    for number in sorted(extract_numbers(claim)):
        hit = next((i for i, s in enumerate(sentences) if number in extract_numbers(s)), None)
        if hit is not None:
            pick(hit)
    for date in sorted(extract_dates(claim)):
        hit = next((i for i, s in enumerate(sentences) if date in extract_dates(s)), None)
        if hit is not None:
            pick(hit)
    # Ưu tiên câu được chọn sớm (theo ý của claim) khi phải cắt; xuất theo thứ tự trong bài.
    chosen = picked[:max_sentences]
    while len(chosen) > 1 and len(" ".join(sentences[i] for i in sorted(chosen))) > max_chars:
        chosen = chosen[:-1]
    return " ".join(sentences[i] for i in sorted(chosen))
