"""Xử lý văn bản tiếng Việt cho bài toán kiểm tra nguồn (source attribution).

Module này gom các bước NLP nhẹ, không cần model, dùng chung cho retrieval,
sinh truy vấn và kiểm tra khớp chi tiết:

* tách câu và cắt cửa sổ câu (sentence window) có chồng lấn;
* token hóa cho BM25: unigram âm tiết + bigram âm tiết (xấp xỉ từ ghép tiếng
  Việt) và bỏ stopword; có thể thay bằng VnCoreNLP word segmentation;
* rút số, phần trăm, ngày tháng và cụm tên riêng để kiểm tra chi tiết.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable, Iterable

from src.preprocessing import normalize_text


# Stopword âm tiết phổ biến. KHÔNG chứa từ phủ định ("không", "chưa", "chẳng")
# vì chúng đổi nghĩa phát biểu và cần được giữ cho bước so khớp.
VIETNAMESE_STOPWORDS = frozenset(
    """
    à ạ ai anh bị bởi các cái cần càng cho chỉ cũng có của cùng cứ dù đã đang đây để đến đều đi điều do
    đó được gì hay hơn hết khi khác là lại lên lúc mà mỗi một mình nào này nên nếu người nhiều như những
    nơi nữa ở ông qua ra rằng rất rồi sau sẽ so sự tại theo thì thế trên trong từ từng và vẫn vào vậy về
    vì việc với vừa bà chị em họ ta tôi chúng thôi nhé nhỉ vâng ạ ấy kia kìa nọ đấy thật luôn cả ngay
    hiện nay hôm năm tháng ngày
    """.split()
)
# "năm/tháng/ngày" bị loại khỏi token BM25 (quá phổ biến) nhưng con số đi kèm
# vẫn được giữ, và bước kiểm tra chi tiết dùng extract_dates() riêng.

# Tập chữ HOA tiếng Việt sinh bằng code: dải "À-Ỹ" trong Unicode lẫn cả chữ thường.
UPPER = "".join(ch for ch in map(chr, range(0x41, 0x1EFA)) if ch.isalpha() and ch.isupper())
_UPPER_CLASS = "[" + re.escape(UPPER) + "]"
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])[\"'”’\)\]]*\s+(?=[\"'“‘\(\[]?(?:" + _UPPER_CLASS + r"|[0-9]))")
TOKEN = re.compile(r"[0-9]+(?:[.,][0-9]+)*%?|[^\W_]+", re.UNICODE)

# Số có thể dính đơn vị phía sau ("1km", "50.000m²", "3ha"); chữ dính phía TRƯỚC (H2O, U23) thì không phải số đo.
NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(\s*%)?(?!\d|[.,]\d)")
NUMBER_UNITS = {
    "nghìn": 1e3, "ngàn": 1e3, "vạn": 1e4, "triệu": 1e6, "tỷ": 1e9, "tỉ": 1e9,
}
NUMBER_WITH_UNIT = re.compile(
    r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(nghìn|ngàn|vạn|triệu|tỷ|tỉ)(?![\w])", re.IGNORECASE
)
# Không bắt khoảng phần trăm "8-10%" / "15-35%" (là số, không phải ngày).
DATE_DMY = re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?(?!\d|\s*%)")


def _valid_dmy(match: re.Match) -> bool:
    return 1 <= int(match.group(1)) <= 31 and 1 <= int(match.group(2)) <= 12
DATE_WORDS = re.compile(
    r"ngày\s+(\d{1,2})(?:\s*(?:tháng|/)\s*(\d{1,2}))?(?:\s*(?:năm|/)\s*(\d{4}))?"
    r"|tháng\s+(\d{1,2})(?:\s*(?:năm|/)\s*(\d{4}))?"
    r"|năm\s+(\d{4})",
    re.IGNORECASE,
)
# Từ hay đứng đầu câu viết hoa nhưng không thuộc tên riêng.
ENTITY_LEADING_NOISE = frozenset("theo tại trong ngày sáng chiều tối đêm hôm sau trước khi ông bà anh chị các những một".split())


def split_sentences(text: str) -> list[str]:
    """Tách câu bảo thủ: chỉ ngắt sau dấu kết câu và trước chữ hoa/số."""
    text = normalize_text(text)
    if not text:
        return []
    return [sentence.strip() for sentence in SENTENCE_BOUNDARY.split(text) if sentence.strip()]


def sentence_windows(text: str, window: int = 2, stride: int = 1, max_chars: int = 600) -> list[str]:
    """Cắt văn bản thành cửa sổ ``window`` câu, bước ``stride`` câu.

    Cửa sổ ngắn giữ được câu chứa thông tin trong giới hạn 256 token của
    PhoBERT; chồng lấn tránh mất thông tin nằm vắt qua ranh giới hai câu.
    Câu đơn quá dài vẫn được giữ (cắt ở ``max_chars``).
    """
    if window < 1 or stride < 1:
        raise ValueError("window và stride phải lớn hơn 0")
    sentences = split_sentences(text)
    if not sentences:
        return []
    if len(sentences) <= window:
        return [" ".join(sentences)[:max_chars]]
    windows: list[str] = []
    seen: set[str] = set()
    for start in range(0, len(sentences), stride):
        chunk = " ".join(sentences[start:start + window])[:max_chars]
        if chunk and chunk not in seen:
            seen.add(chunk)
            windows.append(chunk)
        if start + window >= len(sentences):
            break
    return windows


def syllables(text: str) -> list[str]:
    return TOKEN.findall(normalize_text(text).lower())


def content_syllables(text: str) -> list[str]:
    return [token for token in syllables(text) if token not in VIETNAMESE_STOPWORDS]


def tokenize_bm25(text: str, segmenter: Callable[[str], list[str]] | None = None) -> list[str]:
    """Token cho BM25: âm tiết nội dung + bigram âm tiết liền kề.

    Bigram được tạo trên chuỗi âm tiết GỐC (trước khi bỏ stopword) nhưng bỏ
    các bigram toàn stopword, nên "Bộ Y tế" sinh "bộ_y", "y_tế" – xấp xỉ
    tách từ mà không cần Java. Khi truyền ``segmenter`` (VnCoreNLP), các từ
    ghép từ segmenter được dùng thay cho bigram.
    """
    raw = syllables(text)
    tokens = [token for token in raw if token not in VIETNAMESE_STOPWORDS]
    if segmenter is not None:
        words = [word.lower() for word in segmenter(normalize_text(text)) if "_" in word]
        return tokens + [word for word in words if not all(part in VIETNAMESE_STOPWORDS for part in word.split("_"))]
    for left, right in zip(raw, raw[1:]):
        if left in VIETNAMESE_STOPWORDS and right in VIETNAMESE_STOPWORDS:
            continue
        tokens.append(f"{left}_{right}")
    return tokens


def _parse_number(raw: str) -> float | None:
    value = raw.strip()
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", value):
        # Dấu phân cách hàng nghìn kiểu Việt (1.234.567) hoặc Anh (1,234,567).
        return float(re.sub(r"[.,]", "", value))
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def extract_numbers(text: str) -> set[str]:
    """Rút giá trị số đã chuẩn hóa (bỏ năm 4 chữ số, ngày/tháng — xử lý riêng).

    Trả chuỗi chuẩn: "12.5", "12.5%", "3000000". "3 triệu" và "3.000.000" cho
    cùng một giá trị để tránh báo lệch giả.
    """
    text = normalize_text(text)
    # Chỉ bỏ qua vùng là ngày HỢP LỆ – "15-35" (tháng 35) vẫn là hai con số.
    date_spans = ([match.span() for match in DATE_DMY.finditer(text) if _valid_dmy(match)]
                  + [match.span() for match in DATE_WORDS.finditer(text)])
    values: set[str] = set()
    unit_spans: list[tuple[int, int]] = []
    for match in NUMBER_WITH_UNIT.finditer(text):
        number = _parse_number(match.group(1))
        if number is not None:
            values.add(_format_number(number * NUMBER_UNITS[match.group(2).lower()]))
            unit_spans.append(match.span())
    for match in NUMBER.finditer(text):
        start, end = match.span()
        if any(s <= start < e for s, e in date_spans + unit_spans):
            continue
        number = _parse_number(match.group(1))
        if number is None:
            continue
        if match.group(2):
            values.add(_format_number(number) + "%")
        elif not (1900 <= number <= 2100 and float(number).is_integer() and len(match.group(1)) == 4):
            values.add(_format_number(number))
    return values


# Từ xấp xỉ đứng trước số → khoảng giá trị (bội số của số trong claim) mà nguồn ghi vẫn coi là khớp.
# "hơn 3.000" khớp 3.200; "gần 5 triệu" khớp 4,8 triệu. Ngoài khoảng vẫn so như số chính xác.
APPROXIMATE_QUALIFIERS = {
    "hơn": (1.0, 1.5), "trên": (1.0, 1.5), "vượt": (1.0, 1.5), "ngoài": (1.0, 1.5),
    "gần": (0.8, 1.0), "dưới": (0.67, 1.0),
    "khoảng": (0.8, 1.2), "chừng": (0.8, 1.2), "xấp xỉ": (0.8, 1.2), "ước tính": (0.8, 1.2), "ước": (0.8, 1.2),
}
APPROXIMATE_NUMBER = re.compile(
    r"(?<![\w])(" + "|".join(sorted(APPROXIMATE_QUALIFIERS, key=len, reverse=True)) + r")\s+(?:như\s+|khoảng\s+)?"
    r"(\d[\d.,]*(?:\s*%|\s*(?:nghìn|ngàn|vạn|triệu|tỷ|tỉ)(?![\w]))?)",
    re.IGNORECASE,
)


def approximate_numbers(text: str) -> dict[str, tuple[float, float]]:
    """Số đi sau từ xấp xỉ → khoảng [thấp, cao] chấp nhận được, theo chuỗi chuẩn của ``extract_numbers``."""
    ranges: dict[str, tuple[float, float]] = {}
    for match in APPROXIMATE_NUMBER.finditer(normalize_text(text)):
        low, high = APPROXIMATE_QUALIFIERS[match.group(1).lower()]
        for value in extract_numbers(match.group(2)):
            number = float(value.rstrip("%"))
            ranges[value] = (number * low, number * high)
    return ranges


def number_matches(number: str, passage_numbers: set[str], approximate: dict[str, tuple[float, float]]) -> bool:
    """Số của claim có trong đoạn: trùng khít, hoặc (nếu claim ghi "hơn/gần/khoảng") nằm trong khoảng cho phép."""
    if number in passage_numbers:
        return True
    if number not in approximate:
        return False
    low, high = approximate[number]
    percent = number.endswith("%")
    return any(low <= float(value.rstrip("%")) <= high for value in passage_numbers if value.endswith("%") == percent)


def surface_numbers_dates(text: str) -> list[str]:
    """Số và ngày **như được viết** trong câu ("162.400 tỷ", "1/1/2028", "15%", "tháng 11"), theo thứ tự xuất
    hiện – dùng cho truy vấn tìm kiếm (dạng chuẩn hóa của extract_numbers/extract_dates chỉ để so khớp)."""
    text = normalize_text(text)
    spans: list[tuple[int, int]] = []
    for pattern in (DATE_DMY, DATE_WORDS, NUMBER_WITH_UNIT, NUMBER):
        for match in pattern.finditer(text):
            start, end = match.span()
            if not any(s < end and start < e for s, e in spans):
                spans.append((start, end))
    return [text[start:end].strip() for start, end in sorted(spans)]


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def extract_dates(text: str) -> set[str]:
    """Rút ngày/tháng/năm ở dạng chuẩn ``YYYY``, ``MM/YYYY``, ``DD/MM`` hoặc ``DD/MM/YYYY``."""
    text = normalize_text(text)
    dates: set[str] = set()
    for match in DATE_WORDS.finditer(text):
        day, month, year, month_only, month_year, year_only = match.groups()
        if day:
            parts = [f"{int(day):02d}"]
            if month:
                parts.append(f"{int(month):02d}")
            if year:
                parts.append(year)
            if len(parts) > 1:
                dates.add("/".join(parts))
        elif month_only:
            dates.add(f"{int(month_only):02d}/{month_year}" if month_year else f"{int(month_only):02d}")
        elif year_only:
            dates.add(year_only)
    for match in DATE_DMY.finditer(text):
        day, month, year = match.groups()
        if 1 <= int(day) <= 31 and 1 <= int(month) <= 12:
            if year:
                year = year if len(year) == 4 else f"20{year}"
                dates.add(f"{int(day):02d}/{int(month):02d}/{year}")
            else:
                dates.add(f"{int(day):02d}/{int(month):02d}")
    for match in re.finditer(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", text):
        dates.add(match.group(1))
    return dates


def extract_entities(text: str) -> set[str]:
    """Cụm tên riêng: ≥2 âm tiết viết hoa liên tiếp (Hà Nội, Bộ Y) hoặc từ viết tắt (WHO, RON).

    Bỏ từ đầu câu kiểu "Theo", "Tại" khỏi cụm. Đây là heuristic; có thể thay bằng
    VnCoreNLP NER qua tham số ``ner`` của ``generate_queries``.
    """
    entities: set[str] = set()
    run: list[str] = []

    def flush() -> None:
        while run and run[0].casefold() in ENTITY_LEADING_NOISE:
            run.pop(0)
        if len(run) >= 2:
            entities.add(" ".join(run))
        run.clear()

    for raw in normalize_text(text).split():
        token = raw.strip(".,;:!?\"'“”‘’()[]…")
        if token and token[0].isupper() and token.isalpha():
            run.append(token)
            if len(token) >= 2 and token.isupper():
                entities.add(token)
            if raw != token and raw[-1:] in ".,;:!?)”’…":
                flush()
        else:
            flush()
    flush()
    return entities


def fold(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text).casefold()).strip()


@dataclass(frozen=True)
class ClaimFacets:
    """Các chi tiết "cứng" của claim cần có trong nguồn."""

    numbers: frozenset[str] = field(default_factory=frozenset)
    dates: frozenset[str] = field(default_factory=frozenset)
    entities: frozenset[str] = field(default_factory=frozenset)
    keywords: tuple[str, ...] = ()

    @classmethod
    def from_text(cls, text: str) -> "ClaimFacets":
        keywords = tuple(dict.fromkeys(content_syllables(text)))
        return cls(
            frozenset(extract_numbers(text)), frozenset(extract_dates(text)),
            frozenset(extract_entities(text)), keywords,
        )


def unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
