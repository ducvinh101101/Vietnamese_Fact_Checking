"""Sinh challenge set có nhãn ĐÚNG THEO CẤU TRÚC từ corpus bằng chứng.

Mỗi claim được tạo từ một câu có thật trong một passage đã biết, bằng một phép biến đổi
mà ta biết chắc tác động lên quan hệ với passage gốc:

    SUP_VERBATIM   câu nguyên văn                                   -> SUPPORTED
    SUP_FORMAT     chỉ đổi khoảng trắng / bỏ dấu câu cuối            -> SUPPORTED
    REF_NUMBER     đổi DUY NHẤT một con số (không phải năm/ngày/số hiệu) -> REFUTED
    REF_DIRECTION  đổi 'tăng' <-> 'giảm' khi có kèm mức độ            -> REFUTED
    REF_NEGATION   đổi 'đã' -> 'chưa' (câu có đúng một 'đã')          -> REFUTED
    NEI_PARTIAL    câu thật + ghép thêm một chi tiết bịa             -> NOT_ENOUGH_INFO
    NEI_FICTIONAL  sự kiện bịa, không có trong kho                   -> NOT_ENOUGH_INFO

Vì biết passage nguồn, ta đo được cả RETRIEVAL (có lấy đúng câu nguồn trong top-k không)
lẫn VERIFIER (có kết luận đúng không), và tách lỗi do retrieval với lỗi do verifier.

Giới hạn cần ghi rõ khi báo cáo: claim lấy từ chính corpus (in-distribution); REF_* là
biến đổi tổng hợp, chưa phải lời đồn tự nhiên; NEI_* theo giả định "kho đóng".
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

# Tách câu: chỉ khi dấu kết câu theo sau bởi khoảng trắng + chữ hoa/ngoặc.
# KHÔNG tách ở dấu chấm hàng nghìn ("1.500") hay số phiên bản ("4.0").
SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-Ỹ\"“(])")
SOURCE_PREFIX = re.compile(r"^\s*\([^)]{2,40}\)\s*[-–—:]\s*")
# Số nguyên hoặc số có dấu chấm hàng nghìn; không dính / - (ngày, khoảng).
NUMBER = re.compile(r"(?<![\d/.,\-])(\d{1,3}(?:\.\d{3})+|\d+)(?![\d/\-]|[.,]\d)")
ANY_NUMBER = re.compile(r"(?<![\d/.,\-])\d+(?:[.,]\d+)*(?![\d/\-])")
ID_CONTEXT = re.compile(
    r"(số|điều|khoản|nghị định|thông tư|quyết định|chỉ thị|lần thứ|khóa|khoá|kỳ họp thứ|"
    r"phiên thứ|quốc lộ|tỉnh lộ|phường|quận|mã|tổ|lớp|cấp|thế kỷ|công nghiệp|giai đoạn)\s*$",
    re.IGNORECASE,
)
# Cụm giới hạn/ước lượng: đổi số ngay sau chúng KHÔNG chắc tạo mâu thuẫn
# ("chưa đến 50%" -> "chưa đến 68%" vẫn đúng) -> loại khỏi REF_NUMBER.
BOUND_BEFORE = re.compile(
    r"(chưa đến|chưa tới|dưới|hơn|trên|ít nhất|tối đa|tối thiểu|không quá|không tới|gần|"
    r"khoảng|xấp xỉ|ước tính|ước|hàng|vài|gấp|tới|đến|lên tới|lên đến)\s*$", re.IGNORECASE)
BOUND_AFTER = re.compile(r"^\S*\s*\S*\s*(trở lên|trở xuống|trở lại)", re.IGNORECASE)
NON_STATEMENT = re.compile(r"\?\s*$|^(mình|tớ|em|anh ơi|chị ơi|hãy|xin|mời)\b", re.IGNORECASE)
DIRECTION = re.compile(r"\b(tăng|giảm)(?=\s+(?:\d|mạnh|nhẹ|thêm|hơn|khoảng|gần|gấp|lên|xuống))")
RELATIVE_TIME = re.compile(
    r"\b(hôm nay|hôm qua|chiều nay|sáng nay|tối nay|trưa nay|ngày mai|hiện nay|hiện tại|"
    r"năm nay|tuần này|tháng này|vừa qua|mới đây|gần đây)\b", re.IGNORECASE)

LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")

# Chi tiết bịa ghép vào câu thật: rất khó có trong kho tin 2023, không suy ra từ câu gốc.
FABRICATED_CLAUSES = (
    "đồng thời công bố kế hoạch xây dựng sân bay quốc tế mới trị giá 9,7 tỷ USD",
    "và cho biết sẽ phát hành tem kỷ niệm có in hình phi hành gia Việt Nam đầu tiên",
    "kèm theo quyết định tặng 1.234 chiếc xe điện cho học sinh vùng cao",
    "đồng thời ký thỏa thuận hợp tác khai thác băng ở Nam Cực với 17 quốc gia",
    "và tuyên bố mở tuyến tàu cao tốc nối Hà Nội với Singapore trong năm sau",
)

FICTIONAL_CLAIMS = (
    "Việt Nam phóng thành công tàu thăm dò lên sao Hỏa từ bãi phóng ở Quảng Ngãi",
    "Nhà khoa học Việt Nam tìm ra vắc xin phòng chống tất cả các loại cúm vĩnh viễn",
    "Hà Nội khai trương tuyến tàu điện ngầm dưới đáy Hồ Gươm dài 12 km",
    "Một chú vẹt ở Bến Tre đọc thuộc lòng 300 bài thơ của Nguyễn Du trước đám đông",
    "Thành phố Đà Lạt ghi nhận tuyết rơi dày 2 mét suốt ba ngày liên tiếp",
    "Làng gốm Bát Tràng nung thành công chiếc bình gốm cao 80 mét trong một lò",
    "Vịnh Hạ Long được công nhận là kỳ quan thứ tám của hệ Mặt Trời",
    "Việt Nam xây dựng thang máy vũ trụ đầu tiên của châu Á tại Cần Thơ",
    "Học sinh Kon Tum được nghỉ học để quan sát nhật thực toàn phần kéo dài 3 tuần",
    "Cá voi xanh dài 40 mét bơi ngược dòng sông Hồng lên tới Lào Cai",
    "Tỉnh Nghệ An phát hiện mỏ kim cương lớn nhất thế giới nặng 9 tấn",
    "Một robot Việt Nam đắc cử chủ tịch xã tại tỉnh Bắc Ninh",
    "Sân bay Long Thành đón chuyến bay thương mại siêu thanh đầu tiên tới Sao Hỏa",
    "Hà Giang trồng thành công cây cà phê cao 50 mét trên đỉnh Fansipan",
    "Việt Nam vô địch giải đua thuyền rồng trên mặt trăng năm 2023",
    "Một giống lúa mới ở An Giang cho thu hoạch 12 vụ mỗi năm trên cùng thửa ruộng",
    "Quảng Ninh xây cầu vượt biển nối thẳng sang đảo Hải Nam dài 300 km",
    "Một con mèo ở Huế được cấp bằng tiến sĩ danh dự ngành vật lý",
    "Phố cổ Hội An được di dời nguyên trạng ra đảo Phú Quốc bằng sà lan khổng lồ",
    "Việt Nam phát hiện loài khủng long còn sống tại vườn quốc gia Cúc Phương",
)


@dataclass(frozen=True)
class ChallengeItem:
    id: str
    category: str
    claim: str
    gold: str
    source_passage_id: str | None
    source_sentence: str | None
    note: str = ""


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def strip_source_prefix(sentence: str) -> str:
    return SOURCE_PREFIX.sub("", sentence).strip()


def candidate_sentences(passage: str) -> list[str]:
    out = []
    for raw in SENTENCE_SPLIT.split(passage):
        s = strip_source_prefix(normalize(raw))
        if 50 <= len(s) <= 220 and not RELATIVE_TIME.search(s) and not NON_STATEMENT.search(s):
            out.append(s)
    return out


def _is_year(token: str) -> bool:
    return token.isdigit() and len(token) == 4 and 1900 <= int(token) <= 2100


# Ngữ cảnh cho thấy con số là MÃ/TÊN/THỨ TỰ/LỊCH, đổi nó không tạo bác bỏ rõ ràng
# (hoặc tạo giá trị vô nghĩa như "tháng 16").
ID_WINDOW = ("sư đoàn", "lữ đoàn", "trung đoàn", "quân khu", "quân đoàn", "vành đai",
             "địa chất", "quốc lộ", "tỉnh lộ", "cao tốc", "tàu", "seagames", "sea games")
ID_WORD_BEFORE = re.compile(r"(tháng|ngày|phút|tập|năm|kỳ|vòng|bảng|hạng|thứ|đợt|khóa|khoá)\s*$",
                            re.IGNORECASE)


def _is_quantity_position(sentence: str, start: int, end: int) -> bool:
    before, after = sentence[:start], sentence[end:]
    if before[-1:].isalpha() or (after[:1].isalpha()):
        return False                        # dính chữ: COP27, U20, 3D, 47C
    if ID_WORD_BEFORE.search(before):
        return False                        # tháng 12, phút 83, tập 44, năm 1160
    window = before[-30:].casefold()
    if any(term in window for term in ID_WINDOW):
        return False                        # Quân khu 9, vành đai 3, Sư đoàn ... 101
    words = before.split()
    if words and words[-1][:1].isupper():
        return False                        # Honda 50, SEA Games 32, tên riêng + số
    return True


def perturb_number(sentence: str, passage: str) -> tuple[str, str, str] | None:
    """Đổi đúng một con số an toàn. Trả (claim, số_cũ, số_mới) hoặc None nếu không đạt."""
    all_numbers = ANY_NUMBER.findall(sentence)
    candidates = list(NUMBER.finditer(sentence))
    if len(all_numbers) != 1 or len(candidates) != 1:
        return None
    m = candidates[0]
    token = m.group(1)
    if _is_year(token) or ID_CONTEXT.search(sentence[: m.start(1)]):
        return None
    if BOUND_BEFORE.search(sentence[: m.start(1)]) or BOUND_AFTER.search(sentence[m.end(1):]):
        return None  # số nằm trong cụm giới hạn/ước lượng -> đổi số chưa chắc là bác bỏ
    if not _is_quantity_position(sentence, m.start(1), m.end(1)):
        return None  # số là mã/tên/thứ tự (COP27, U20, Quân khu 9, tháng 12...) chứ không phải lượng
    value = int(token.replace(".", ""))
    if value < 2:
        return None
    if len(re.findall(rf"(?<![\d.]){re.escape(token)}(?![\d.])", passage)) != 1:
        return None  # số xuất hiện nhiều lần trong passage -> mơ hồ
    new_value = value + max(3, round(value * 0.37))
    # Viết số mới theo quy ước Việt: >= 1000 dùng dấu chấm hàng nghìn (1.028).
    new_token = f"{new_value:,}".replace(",", ".") if ("." in token or new_value >= 1000) else str(new_value)
    if new_token in passage:
        return None  # số mới tình cờ có trong passage -> có thể không còn là bác bỏ
    return sentence[: m.start(1)] + new_token + sentence[m.end(1):], token, new_token


def swap_direction(sentence: str) -> str | None:
    if len(re.findall(r"\b(?:tăng|giảm)\b", sentence)) != 1:
        return None
    m = DIRECTION.search(sentence)
    if not m:
        return None
    new = "giảm" if m.group(1) == "tăng" else "tăng"
    rest = sentence[m.end(1):]
    # Đổi CẶP để câu còn đúng ngữ pháp: "giảm xuống" <-> "tăng lên" (tránh "tăng xuống").
    pair = re.match(r"(\s+)(lên|xuống)\b", rest)
    if pair:
        partner = "xuống" if pair.group(2) == "lên" else "lên"
        rest = pair.group(1) + partner + rest[pair.end():]
    return sentence[: m.start(1)] + new + rest


def negate_da(sentence: str) -> str | None:
    if len(re.findall(r"\bđã\b", sentence)) != 1 or re.search(r"\bchưa\b|\bkhông\b", sentence):
        return None
    if re.search(r"\bđã\s+(rất|quá|khá|hơi|luôn|cực kỳ|vô cùng)\b", sentence):
        return None  # "chưa rất ..." sai ngữ pháp
    return re.sub(r"\bđã\b", "chưa", sentence, count=1)


def add_fabricated_clause(sentence: str, rng: random.Random) -> str:
    base = sentence.rstrip(" .!?…")
    return f"{base}, {rng.choice(FABRICATED_CLAUSES)}."


def build_challenge_set(passages: list[dict], per_category: int = 60, seed: int = 42) -> list[ChallengeItem]:
    rng = random.Random(seed)
    order = list(range(len(passages)))
    rng.shuffle(order)
    buckets: dict[str, list[ChallengeItem]] = {k: [] for k in (
        "SUP_VERBATIM", "SUP_FORMAT", "REF_NUMBER", "REF_DIRECTION", "REF_NEGATION", "NEI_PARTIAL")}
    used_sentences: set[str] = set()

    def full(cat: str) -> bool:
        return len(buckets[cat]) >= per_category

    for idx in order:
        p = passages[idx]
        pid, content = p["passage_id"], p["content"]
        for sent in candidate_sentences(content):
            if sent in used_sentences:
                continue
            made = False
            if not full("REF_NUMBER") and (pert := perturb_number(sent, content)):
                claim, old, new = pert
                buckets["REF_NUMBER"].append(ChallengeItem(
                    f"REF_NUMBER-{len(buckets['REF_NUMBER']):03d}", "REF_NUMBER", claim, "REFUTED",
                    pid, sent, f"{old} -> {new}"))
                made = True
            elif not full("REF_DIRECTION") and (sw := swap_direction(sent)):
                buckets["REF_DIRECTION"].append(ChallengeItem(
                    f"REF_DIRECTION-{len(buckets['REF_DIRECTION']):03d}", "REF_DIRECTION", sw, "REFUTED",
                    pid, sent))
                made = True
            elif not full("REF_NEGATION") and (ng := negate_da(sent)):
                buckets["REF_NEGATION"].append(ChallengeItem(
                    f"REF_NEGATION-{len(buckets['REF_NEGATION']):03d}", "REF_NEGATION", ng, "REFUTED",
                    pid, sent))
                made = True
            elif not full("SUP_VERBATIM"):
                buckets["SUP_VERBATIM"].append(ChallengeItem(
                    f"SUP_VERBATIM-{len(buckets['SUP_VERBATIM']):03d}", "SUP_VERBATIM", sent, "SUPPORTED",
                    pid, sent))
                made = True
            elif not full("SUP_FORMAT"):
                variant = "  " + re.sub(r"\s+", "  ", sent).rstrip(".!?…") + "  "
                buckets["SUP_FORMAT"].append(ChallengeItem(
                    f"SUP_FORMAT-{len(buckets['SUP_FORMAT']):03d}", "SUP_FORMAT", variant, "SUPPORTED",
                    pid, sent))
                made = True
            elif not full("NEI_PARTIAL"):
                buckets["NEI_PARTIAL"].append(ChallengeItem(
                    f"NEI_PARTIAL-{len(buckets['NEI_PARTIAL']):03d}", "NEI_PARTIAL",
                    add_fabricated_clause(sent, rng), "NOT_ENOUGH_INFO", pid, sent))
                made = True
            if made:
                used_sentences.add(sent)
                break  # tối đa một claim mỗi passage -> đa dạng nguồn
        if all(full(c) for c in buckets):
            break

    items = [it for cat in buckets for it in buckets[cat]]
    items += [ChallengeItem(f"NEI_FICTIONAL-{i:03d}", "NEI_FICTIONAL", c, "NOT_ENOUGH_INFO", None, None)
              for i, c in enumerate(FICTIONAL_CLAIMS)]
    return items


def load_passages(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def save_items(items: list[ChallengeItem], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for it in items:
            handle.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


def load_items(path: str | Path) -> list[ChallengeItem]:
    with open(path, encoding="utf-8") as handle:
        return [ChallengeItem(**json.loads(line)) for line in handle if line.strip()]
