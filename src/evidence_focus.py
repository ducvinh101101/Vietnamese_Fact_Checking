"""Chọn CÂU liên quan nhất trong passage để đưa cho verifier.

Phát hiện từ challenge set (PhoBERT RT-V2): độ chính xác phụ thuộc mạnh vào VỊ TRÍ của
câu liên quan trong passage. Với REF_DIRECTION: câu ở đầu passage đúng 75%, câu nằm sau
200 ký tự chỉ đúng 24%; SUP_VERBATIM: 100% -> 78%. Cả 4 claim nguyên văn bị REFUTED đều
có câu nằm ở nửa sau passage. Verifier bị nhiễu bởi các câu đứng trước.

Module này cung cấp các cách dựng chuỗi evidence (``mode``):

* ``passage``     — nguyên passage (mặc định, giữ nguyên hành vi đã khóa RT-V2).
* ``focus_first`` — câu khớp nhất đứng ĐẦU, các câu còn lại theo thứ tự cũ.
* ``focus_only``  — chỉ câu khớp nhất.
* ``ensemble``    — verifier chấm cả 3 view trên rồi lấy TRUNG BÌNH xác suất (xem
  ``ensemble_texts`` / ``average_probabilities``); do verifier thực hiện, không phải
  ``focus_text``.

Việc chọn mode phải do thực nghiệm quyết định (xem scripts/run_challenge_eval.py
--evidence-view) vì PhoBERT được fine-tune trên passage đầy đủ.
"""

from __future__ import annotations

import re

SINGLE_VIEWS = ("passage", "focus_first", "focus_only")
VIEWS = (*SINGLE_VIEWS, "ensemble")

_WORD = re.compile(r"\w+", re.UNICODE)
_BOUNDARY = re.compile(r"(?<=[.!?…])\s+|\n+")
_ABBREVIATION_END = re.compile(r"(?:^|\s)(?:TP|Tp|Q|P|H|X|TS|PGS|GS|ThS|BS|ĐH|Dr|Mr|Mrs|St|No)\.$")


def split_sentences(text: str) -> list[str]:
    """Tách câu theo dấu kết thúc câu; gộp lại mảnh bắt đầu bằng chữ thường
    hoặc mảnh trước kết thúc bằng viết tắt kiểu 'TP.', 'Q.', 'TS.' để không cắt nhầm."""
    pieces = [p.strip() for p in _BOUNDARY.split(text or "") if p and p.strip()]
    merged: list[str] = []
    for piece in pieces:
        if merged and (piece[0].islower() or _ABBREVIATION_END.search(merged[-1])):
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)
    return merged


def _syllables(text: str) -> list[str]:
    return _WORD.findall(text.casefold())


def sentence_score(claim: str, sentence: str) -> float:
    """Độ phủ của claim trong câu (unigram + bigram), 0..1.5."""
    c, s = _syllables(claim), _syllables(sentence)
    if not c or not s:
        return 0.0
    uni = len(set(c) & set(s)) / len(set(c))
    cb, sb = set(zip(c, c[1:])), set(zip(s, s[1:]))
    bi = (len(cb & sb) / len(cb)) if cb else 0.0
    return uni + 0.5 * bi


def best_sentence_index(claim: str, sentences: list[str]) -> int:
    """Chỉ số câu khớp claim nhất (hòa điểm -> câu đứng trước)."""
    scores = [sentence_score(claim, s) for s in sentences]
    return max(range(len(sentences)), key=lambda i: (scores[i], -i))


def focus_text(claim: str, passage: str, mode: str = "passage") -> str:
    if mode == "ensemble":
        raise ValueError("'ensemble' do verifier xử lý (ensemble_texts); focus_text chỉ nhận " + str(SINGLE_VIEWS))
    if mode not in SINGLE_VIEWS:
        raise ValueError(f"evidence_view không hợp lệ: {mode!r}; chọn một trong {VIEWS}")
    if mode == "passage":
        return passage
    sentences = split_sentences(passage)
    if len(sentences) <= 1:
        return passage
    best = best_sentence_index(claim, sentences)
    if mode == "focus_only":
        return sentences[best]
    return " ".join([sentences[best], *sentences[:best], *sentences[best + 1:]])


def ensemble_texts(claim: str, passages: list[str], views: tuple[str, ...] = SINGLE_VIEWS) -> list[str]:
    """Chuỗi evidence phẳng: view-major, tức [view0: p0..pk-1, view1: p0..pk-1, ...]."""
    return [focus_text(claim, passage, view) for view in views for passage in passages]


def average_probabilities(flat: list[list[float]], n_views: int) -> list[list[float]]:
    """Trung bình xác suất theo view cho từng passage; đảo ngược ``ensemble_texts``."""
    if n_views < 1 or len(flat) % n_views:
        raise ValueError("Số xác suất không chia hết cho số view")
    k = len(flat) // n_views
    return [[sum(flat[v * k + i][c] for v in range(n_views)) / n_views for c in range(len(flat[0]))]
            for i in range(k)]
