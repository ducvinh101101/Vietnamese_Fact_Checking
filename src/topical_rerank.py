"""Gộp bằng chứng theo URL và xếp lại theo độ khớp chủ đề của claim.

Hai vấn đề quan sát được khi chạy thật:
1) Nhiều đoạn của CÙNG một bài (p01/p02/p03) chiếm hết top-k, nhìn lặp và làm
   verifier thấy toàn một nguồn. -> Gộp mỗi URL còn MỘT đoạn khớp nhất.
2) Bài "giá dầu thế giới" (WTI/Brent, USD/thùng) bị xếp trên bài "giá xăng bán lẻ
   trong nước" dù claim hỏi về giá bán lẻ. -> Xếp lại theo độ khớp với claim.

Cách tính độ khớp (cố ý GIỮ TỔNG QUÁT, không phải hack riêng xăng dầu):
- Chính: số từ nội dung của claim xuất hiện trong đoạn (bỏ stopword tiếng Việt).
  Claim "giá xăng tăng chiều nay" khớp đoạn bán lẻ ("giá xăng ... tăng ... đồng/lít")
  nhiều hơn đoạn thế giới ("giá dầu WTI ... USD/thùng") một cách tự nhiên.
- Phụ (chỉ bật khi claim nói về GIÁ): cộng nhẹ nếu đoạn có dấu hiệu GIÁ BÁN LẺ /
  KỲ ĐIỀU HÀNH trong nước, trừ nhẹ nếu đoạn chỉ nói GIÁ DẦU THẾ GIỚI. Trọng số nhỏ
  nên chỉ nghiêng cán cân khi độ khớp xấp xỉ nhau, không bẻ cong verifier.

Lớp này chỉ XẾP LẠI + GỘP; không tạo/sửa nội dung bằng chứng, không đụng verifier.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.contracts import Retriever
from src.schemas import RetrievedEvidence
from src.verbatim import verbatim_span

_SPACE = re.compile(r"\s+")
_TERM = re.compile(r"\d+(?:[.,]\d+)*|\w+", re.UNICODE)
_MONEY_CLAIM = re.compile(r"\d\s*(?:đồng|vnd|vnđ|nghìn|ngàn|triệu|tỷ)\b")
_TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "zarsrc", "ref", "source", "mc_", "igshid")

# Stopword tiếng Việt tối thiểu (từ chức năng + mốc thời gian tương đối) để độ khớp
# phản ánh từ NỘI DUNG, không bị nhiễu bởi "từ, các, đã, chiều, nay"...
_STOPWORDS = frozenset("""
và của có là các một những được cho với từ đã đang sẽ trong ngoài trên dưới khi về
thì mà nếu nên hay hoặc tại theo đến ra vào này đó kia ấy rất quá cũng chỉ vẫn còn
chiều sáng trưa tối đêm nay mai qua hôm hiện bây giờ gần đây mới đây vừa tuần tháng
năm ngày số
""".split())

# Dấu hiệu GIÁ BÁN LẺ / KỲ ĐIỀU HÀNH trong nước (claim giá cả thường nhắm vào đây).
_RETAIL_HINTS = (
    "bán lẻ", "đồng/lít", "đồng một lít", "kỳ điều hành", "điều hành giá",
    "liên bộ", "ron 95", "ron95", "ron 92", "xăng e5", "e5 ron", "trong nước",
    "niêm yết", "bình ổn", "quỹ bình ổn",
)
# Dấu hiệu GIÁ DẦU THẾ GIỚI (nền thị trường, không phải giá bán lẻ VN).
_WORLD_HINTS = (
    "wti", "brent", "usd/thùng", "usd một thùng", "thị trường thế giới",
    "dầu thô", "opec",
)
# Claim có nói về giá không? (để bật phần phụ). So khớp THEO TỪ, không theo chuỗi con
# ('đồng' trong 'hội đồng' không phải tiền); tiền tệ chỉ tính khi đứng sau con số.
_PRICE_WORDS = frozenset({"giá", "xăng", "dầu"})

_RETAIL_BONUS = 0.6   # nhỏ: chỉ nghiêng khi độ khớp xấp xỉ
_WORLD_PENALTY = 0.6


def _tokens(text: str) -> set[str]:
    """Từ nội dung (bỏ dấu câu bám vào từ: 'tăng.' == 'tăng', 'xăng,' == 'xăng')."""
    return {t for t in _TERM.findall(text.casefold()) if t not in _STOPWORDS}


def _is_price_claim(claim: str) -> bool:
    low = claim.casefold()
    return bool(_PRICE_WORDS & set(_TERM.findall(low))) or _MONEY_CLAIM.search(low) is not None


def _hint_count(text: str, hints: tuple[str, ...]) -> int:
    low = text.casefold()
    return sum(1 for h in hints if h in low)


def relevance(claim: str, passage: str) -> float:
    """Điểm khớp chủ đề giữa claim và một đoạn bằng chứng (càng cao càng đúng chủ đề)."""
    claim_terms = _tokens(claim)
    if not claim_terms:
        return 0.0
    overlap = len(claim_terms & _tokens(passage))
    score = float(overlap)
    # Phần phụ chỉ áp dụng cho claim về giá cả.
    if _is_price_claim(claim):
        retail = min(_hint_count(passage, _RETAIL_HINTS), 3)
        world = min(_hint_count(passage, _WORLD_HINTS), 3)
        score += _RETAIL_BONUS * retail - _WORLD_PENALTY * world
    return score


def eligible(claim: str, passage: str, minimum_coverage: float = 0.35) -> bool:
    terms = _tokens(claim)
    overlap = terms & _tokens(passage)
    if not terms or len(overlap) < min(2, len(terms)) or len(overlap) / len(terms) < minimum_coverage:
        return False
    # Generic accident/death vocabulary must not substitute for the named
    # institution in a claim (e.g. a school fire versus a different fatality).
    institutions = re.findall(
        r'(?i:trường|bệnh viện|công ty|tập đoàn)\s+(?:(?:THCS|THPT|TNHH|CP)\s+)?'
        r'([A-ZĐ][^\W\d_]+(?:\s+[A-ZĐ][^\W\d_]+){1,3})', claim)
    passage_words = ' '.join(_TERM.findall(passage.casefold()))
    if any(' '.join(_TERM.findall(name.casefold())) not in passage_words for name in institutions):
        return False
    # Require complete multi-word proper names rather than accepting a different
    # person who happens to share a surname. Numbers may differ in REFUTED evidence.
    names = re.findall(r"\b[A-ZĐ][a-zà-ỹ]+(?:\s+[A-ZĐ][a-zà-ỹ]+){2,}\b", claim)
    for name in names:
        words = name.casefold().split()
        prefix = " ".join(words[:2])
        if prefix in passage.casefold() and name.casefold() not in passage.casefold():
            return False
    return True


def canonical_url(url: str) -> str:
    """Chuẩn hóa URL để gộp CÙNG một bài: bỏ #fragment, tham số theo dõi (utm_*, fbclid...),
    'www.' và '/' cuối. Tham số khác (vd ?id=123) được giữ vì có thể định danh bài."""
    url = url.strip()
    if not url:
        return ""
    parts = urlsplit(url)
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.casefold().startswith(_TRACKING_PARAMS)]
    host = parts.netloc.casefold().removeprefix("www.")
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.casefold(), host, path, urlencode(sorted(kept)), "")).casefold()


class RelevanceFilteredRetriever:
    """Abstain on weak candidates while preserving the baseline ranking."""

    def __init__(self, inner: Retriever, candidate_k: int = 20) -> None:
        self.inner = inner
        self.candidate_k = candidate_k

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        return [item for item in self.inner.search(claim, max(top_k, self.candidate_k))
                if eligible(claim, item.evidence.content)][:top_k]


class TopicalRerankRetriever:
    """Bọc một retriever: gộp theo URL (giữ đoạn khớp nhất) rồi xếp theo độ khớp claim.

    ``inner`` thường là TemporalGateRetriever. Lấy dư ứng viên (``candidate_k``),
    gộp mỗi URL một đoạn, xếp lại và trả ``top_k`` bài RIÊNG BIỆT.
    """

    def __init__(self, inner: Retriever, candidate_k: int = 20, enabled: bool = True) -> None:
        if candidate_k < 1:
            raise ValueError("candidate_k phải lớn hơn 0")
        self.inner = inner
        self.candidate_k = candidate_k
        self.enabled = enabled

    def _url_key(self, item: RetrievedEvidence) -> str:
        url = canonical_url(item.evidence.url or "")
        return url or f"doc::{item.evidence.document_id}"

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        if not self.enabled:
            return self.inner.search(claim, top_k)

        candidates = self.inner.search(claim, max(top_k, self.candidate_k))

        # Gộp theo URL: mỗi bài giữ đoạn có độ khớp cao nhất (hòa thì theo score gốc).
        best: dict[str, tuple[float, RetrievedEvidence]] = {}
        for item in candidates:
            rel = relevance(claim, item.evidence.content)
            # A passage with no topical overlap cannot be promoted into top 1
            # merely by its upstream provider/BM25 rank.
            if rel <= 0 or not eligible(claim, item.evidence.content):
                continue
            key = self._url_key(item)
            current = best.get(key)
            if current is None or (verbatim_span(claim, item.evidence.content) is not None, rel, item.score) > (
                    verbatim_span(claim, current[1].evidence.content) is not None, current[0], current[1].score):
                best[key] = (rel, item)

        # Xếp bài theo (độ khớp, score gốc) giảm dần. Gán lại score = độ khớp để
        # pipeline thấy thứ tự giảm dần (pipeline yêu cầu score không tăng dần).
        scale = max((abs(pair[1].score) for pair in best.values()), default=1.0) or 1.0
        def combined(pair):
            rel, item = pair
            coverage = min(1.0, rel / max(1, len(_tokens(claim))))
            return 0.6 * item.score / scale + 0.4 * coverage

        ranked = sorted(
            best.values(),
            key=lambda pair: (verbatim_span(claim, pair[1].evidence.content) is None,
                              -combined(pair), pair[1].evidence.passage_id),
        )
        result: list[RetrievedEvidence] = []
        for order, (rel, item) in enumerate(ranked[:top_k]):
            # Score giảm dần nghiêm ngặt theo thứ hạng để không phá kiểm tra của pipeline,
            # vẫn giữ quan hệ hơn-kém theo độ khớp.
            result.append(RetrievedEvidence(item.evidence, float(len(ranked) - order)))
        return result
