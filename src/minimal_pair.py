"""Phát hiện 'cặp tối thiểu' giữa claim và một câu trong bằng chứng.

Vấn đề (challenge set, PhoBERT RT-V2): khi claim GẦN GIỐNG HỆT một câu trong nguồn
nhưng đổi một yếu tố then chốt, verifier thường vẫn trả SUPPORTED:
  * đổi chiều  tăng<->giảm  : đúng 48% (46,7% bị SUPPORTED)
  * đổi phủ định đã<->chưa  : đúng 63% (36,7% bị SUPPORTED)
  * đổi một con số          : 95%

Cách làm: căn hàng claim với từng câu của các passage đã truy xuất (SequenceMatcher
trên âm tiết). Nếu hai bên khớp gần hết và MỌI chỗ khác biệt đều giải thích được bằng
đúng các loại lật nghĩa sau, thì đó là bằng chứng bác bỏ trực tiếp:

  * số liệu khác giá trị   ('8.100' vs '9.200'; '1.500' == '1500')
  * chiều ngược nhau       (tăng/lên/cao/nhiều/mở/thắng  <->  giảm/xuống/thấp/ít/đóng/thua)
  * phủ định bật/tắt       (đã<->chưa, có<->không, thêm/bớt 'không|chưa|chẳng|chả|hề')

Ngược lại, nếu claim nằm trọn (gần nguyên văn) trong một câu của nguồn thì đó là bằng
chứng ủng hộ trực tiếp, kể cả khi mô hình trả REFUTED/NEI.

Đây là luật xác định, KHÔNG phải mô hình: chính xác trên cặp gần giống, nhưng chỉ phủ
các từ vựng nêu trên. Với biến đổi khác (thắng/thua ngầm, từ trái nghĩa hiếm...) nó
im lặng (trả None) chứ không đoán. Luôn đánh giá lại trên tập giữ riêng (held-out)
trước khi bật mặc định.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from src.contracts import Verifier
from src.evidence_focus import split_sentences
from src.schemas import RetrievedEvidence, VerificationResult
from src.verbatim import verbatim_span

MIN_CLAIM_TOKENS = 6
MIN_COVERAGE = 0.8          # tỉ lệ âm tiết của claim phải khớp với câu nguồn
MAX_UNEXPLAINED = 2         # số âm tiết khác biệt không phân loại được (đồng nghĩa, từ đệm)
NEAR_EXACT_SLACK = 1.25     # câu nguồn dài tối đa ~125% claim (+2) mới coi là 'nguyên văn'

_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|\w+", re.UNICODE)
_THOUSANDS = re.compile(r"\d{1,3}(?:\.\d{3})+")

UP = frozenset({"tăng", "lên", "cao", "nhiều", "mở", "thắng", "nhanh"})
DOWN = frozenset({"giảm", "xuống", "thấp", "ít", "đóng", "thua", "chậm"})
PARTICLES = frozenset({"hơn", "mạnh", "đáng", "kể", "nhẹ", "thêm", "còn", "rất", "khá"})
NEG = frozenset({"không", "chưa", "chẳng", "chả", "hề"})
AFFIRM = frozenset({"đã", "có", "đang", "từng", "sẽ", "được"})
# 'không' trong thành ngữ/từ ghép không phải phủ định mệnh đề.
_NEG_IDIOM_NEXT = frozenset({"gian", "khí", "quân", "chỉ", "những", "ngừng", "hạn", "gì"})
_NEG_IDIOM_PREV = frozenset({"hàng", "bay", "phòng", "sân"})


def _canon(token: str) -> str:
    """Số được chuẩn hóa thành '#<giá trị>' để '1.500' == '1500' và '2,5' == '2.5'."""
    low = token.casefold()
    if not low[0].isdigit():
        return low
    if _THOUSANDS.fullmatch(low):
        low = low.replace(".", "")
    low = low.replace(",", ".")
    try:
        return f"#{float(low):g}"
    except ValueError:
        return low


def tokenize(text: str) -> list[str]:
    return [_canon(t) for t in _TOKEN.findall(text)]


@dataclass(frozen=True)
class PairAnalysis:
    coverage: float
    exact: bool                 # mọi âm tiết của claim đều nằm trong câu nguồn
    near_exact: bool            # exact và câu nguồn không dài hơn nhiều so với claim
    contradiction: bool
    kinds: tuple[str, ...]      # 'number' | 'direction' | 'negation'
    detail: str


def _neg_is_idiom(tag: str, ct: list[str], a0: int, a1: int, st: list[str], b0: int, b1: int) -> bool:
    seq, lo, hi = (ct, a0, a1) if tag == "delete" else (st, b0, b1)
    prev_tok = seq[lo - 1] if lo > 0 else ""
    next_tok = seq[hi] if hi < len(seq) else ""
    return next_tok in _NEG_IDIOM_NEXT or prev_tok in _NEG_IDIOM_PREV


def _classify(tag: str, a: list[str], b: list[str]) -> str | None:
    if tag == "replace":
        na, nb = {t for t in a if t.startswith("#")}, {t for t in b if t.startswith("#")}
        if na and nb and na != nb:
            return "number"
        ca, cb = {t for t in a if t not in PARTICLES}, {t for t in b if t not in PARTICLES}
        if ca and cb:
            if (ca <= UP and cb <= DOWN) or (ca <= DOWN and cb <= UP):
                return "direction"
            if (ca <= NEG and cb <= AFFIRM) or (ca <= AFFIRM and cb <= NEG):
                return "negation"
    return None


def analyse(claim: str, sentence: str) -> PairAnalysis | None:
    ct, st = tokenize(claim), tokenize(sentence)
    if len(ct) < MIN_CLAIM_TOKENS or not st:
        return None
    matcher = SequenceMatcher(None, ct, st, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    coverage = matched / len(ct)
    if coverage < MIN_COVERAGE:
        return None
    ops = matcher.get_opcodes()
    equal_ids = [i for i, op in enumerate(ops) if op[0] == "equal"]
    if not equal_ids:
        return None
    first, last = equal_ids[0], equal_ids[-1]

    kinds: list[str] = []
    details: list[str] = []
    unexplained = 0
    for index, (tag, a0, a1, b0, b1) in enumerate(ops):
        if tag == "equal":
            continue
        a, b = ct[a0:a1], st[b0:b1]
        kind = _classify(tag, a, b)
        if kind is None and tag in ("insert", "delete") and set(a or b) <= NEG:
            if not _neg_is_idiom(tag, ct, a0, a1, st, b0, b1):
                kind = "negation"
        if kind is not None:
            kinds.append(kind)
            details.append(f"{kind}: claim '{' '.join(a) or '∅'}' ≠ nguồn '{' '.join(b) or '∅'}'")
        elif first < index < last:
            unexplained += max(len(a), len(b))      # lệch ở GIỮA câu: phải giải thích được
        # lệch ở đầu/cuối: phần ngữ cảnh thừa của câu nguồn, đã bị giới hạn bởi coverage

    flips = sum(1 for k in kinds if k in ("direction", "negation"))
    has_number = "number" in kinds
    contradiction = bool(kinds) and unexplained <= MAX_UNEXPLAINED and (has_number or flips % 2 == 1)
    exact = matched == len(ct)
    near_exact = exact and len(st) <= NEAR_EXACT_SLACK * len(ct) + 2
    return PairAnalysis(coverage, exact, near_exact, contradiction, tuple(kinds), "; ".join(details))


@dataclass(frozen=True)
class PairHit:
    passage_id: str
    sentence: str
    analysis: PairAnalysis


def scan(claim: str, passages: list[tuple[str, str]]) -> tuple[list[PairHit], list[PairHit]]:
    """Trả (các câu ủng hộ nguyên văn, các câu mâu thuẫn tối thiểu)."""
    supports: list[PairHit] = []
    contradictions: list[PairHit] = []
    for passage_id, text in passages:
        for sentence in split_sentences(text):
            analysis = analyse(claim, sentence)
            if analysis is None:
                continue
            if analysis.near_exact:
                supports.append(PairHit(passage_id, sentence, analysis))
            elif analysis.contradiction:
                contradictions.append(PairHit(passage_id, sentence, analysis))
    contradictions.sort(key=lambda h: -h.analysis.coverage)
    return supports, contradictions


def refine(claim: str, result: VerificationResult, evidence_items: list[RetrievedEvidence],
           upgrade_exact: bool = True) -> tuple[VerificationResult, str | None]:
    """Áp luật cặp-tối-thiểu lên verdict của mô hình. Trả (verdict mới, lý do hoặc None).

    Thứ tự ưu tiên: câu nguồn nguyên văn (ủng hộ) thắng mâu thuẫn ở passage khác.
    """
    passages = [(it.evidence.passage_id, it.evidence.content) for it in evidence_items]
    supports, contradictions = scan(claim, passages)
    if supports:
        if upgrade_exact and result.label != "SUPPORTED":
            hit = supports[0]
            return VerificationResult(
                "SUPPORTED", 0.9, [hit.passage_id],
                f"[minimal-pair] Claim trùng gần nguyên văn một câu trong nguồn (trước đó: {result.label}).",
            ), "exact_support"
        return result, None
    if contradictions and result.label != "REFUTED":
        hit = contradictions[0]
        return VerificationResult(
            "REFUTED", 0.85, [hit.passage_id],
            f"[minimal-pair] Claim gần như trùng một câu trong nguồn nhưng khác yếu tố then chốt "
            f"({hit.analysis.detail}) (trước đó: {result.label}).",
        ), "contradiction:" + "+".join(hit.analysis.kinds)
    return result, None


class MinimalPairVerifier:
    """Bọc một Verifier: sau khi verifier trả verdict, áp luật cặp-tối-thiểu."""

    def __init__(self, inner: Verifier, enabled: bool = True, upgrade_exact: bool = True,
                 complete_web_span: bool = False) -> None:
        self.inner = inner
        self.enabled = enabled
        self.upgrade_exact = upgrade_exact
        self.last_reason: str | None = None
        self.complete_web_span = complete_web_span
        self.last_base_result: VerificationResult | None = None

    def verify(self, claim: str, evidence_items: list[RetrievedEvidence]) -> VerificationResult:
        result = self.inner.verify(claim, evidence_items)
        self.last_base_result = result
        self.last_reason = None
        if not self.enabled:
            return result
        if self.complete_web_span and self.upgrade_exact and result.label == 'NOT_ENOUGH_INFO':
            for item in evidence_items:
                e = item.evidence
                if e.passage_id.startswith('web-') and verbatim_span(claim, e.content) is not None:
                    self.last_reason = 'complete_verbatim_support'
                    return VerificationResult('SUPPORTED', 0.9, [e.passage_id],
                        'Toàn bộ phát biểu trùng nguyên văn một câu hoặc các câu liên tiếp trong nguồn đã truy xuất. '
                        'Kết luận dựa trên đoạn nguồn được trích dẫn.')
        refined, reason = refine(claim, result, evidence_items,
                                 self.upgrade_exact and not self.complete_web_span)
        self.last_reason = reason
        return refined
