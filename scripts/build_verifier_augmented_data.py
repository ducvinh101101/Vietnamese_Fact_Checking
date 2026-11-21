"""Tạo dữ liệu RT-V4: RT-V3 + mẫu "cùng thông tin, khác cách viết" và mẫu tương phản.

Vì sao: claim ViFactCheck gần như chép nguyên định dạng của bài nên RT-V3 chưa thấy
"1-3-2027" ↔ "1.3.2027", "2 năm" ↔ "hai năm", "700.000 đồng" ↔ "700 nghìn đồng",
"430,5 km" ↔ "hơn 430 km". Chẩn đoán trên tin thật (docs/GHI_CHU_LOI_VA_CAI_TIEN.md §2):
verifier đánh REFUTED 0,99 cho đoạn chỉ khác định dạng ngày.

Chỉ đổi CLAIM, giữ nguyên đoạn (Evidence):

* giữ nhãn (mọi nhãn): đổi định dạng ngày / số chữ / số tròn – quan hệ giá trị không đổi;
* SUPPORTED → SUPPORTED: số gần đúng đúng chiều ("hơn 430" khi bài ghi 430,5);
* SUPPORTED → REFUTED (tương phản): đổi định dạng **và** giá trị (ngày khác, "hơn" số lớn hơn nhiều…),
  để model không học lối tắt "khác định dạng ⇒ SUPPORTED".

Mỗi cặp gốc sinh tối đa 1 mẫu giữ nhãn + 1 mẫu tương phản. Train lấy từ train RT-V3; dev tăng cường
(`dev_augmented.parquet`) chỉ để ĐO độ bền định dạng, không dùng chọn checkpoint. Không đọc test.

    python scripts/build_verifier_augmented_data.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.vi_text import DATE_DMY, _valid_dmy

SUPPORTED, REFUTED = 0, 1
DIGIT_WORDS = {2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu", 7: "bảy", 8: "tám", 9: "chín", 10: "mười"}
WORD_DIGITS = {word: n for n, word in DIGIT_WORDS.items() if word != "năm"}  # "năm" (5) trùng "năm" (year)
COUNT_UNITS = ("năm", "tháng", "ngày", "tuần", "giờ", "phút", "người", "lần", "tỉnh", "xã", "huyện", "dự án",
               "trường hợp", "đơn vị", "nhóm", "đợt", "bên", "nước", "chiếc", "con", "vụ", "điểm", "cấp", "kỳ")
_UNITS = "|".join(sorted(map(re.escape, COUNT_UNITS), key=len, reverse=True))
SMALL_COUNT = re.compile(r"(?<![\w.,/\-])(\d{1,2})\s+(" + _UNITS + r")(?![\w])")
WORD_COUNT = re.compile(r"(?<![\w])(" + "|".join(WORD_DIGITS) + r")\s+(" + _UNITS + r")(?![\w])", re.IGNORECASE)
ROUND_THOUSANDS = re.compile(r"(?<![\w.,])(\d{1,3})((?:\.000){1,3})(?![\w.,]|,\d)")
DECIMAL = re.compile(r"(?<![\w.,])(\d{2,6}),(\d{1,2})(?![\w.,]|\.\d)")
INTEGER = re.compile(r"(?<![\w.,/\-])(\d{2,5})(?![\w.,/\-]|\s*%|\s*/)")
SCALE = {1: "nghìn", 2: "triệu", 3: "tỷ"}


def _replace(text: str, match: re.Match, new: str) -> str:
    return text[:match.start()] + new + text[match.end():]


DATE_CONTEXT = re.compile(r"(?:ngày|sáng|chiều|tối|trưa|đêm|hôm|từ|đến|tới|hạn|vào|trước|sau|đầu|cuối|-)\s*$",
                          re.IGNORECASE)


# Sau "3-4"/"8-10" là đơn vị → khoảng số, không phải ngày.
RANGE_UNIT = re.compile(r"\s*(?:triệu|tỷ|tỉ|nghìn|ngàn|vạn|đồng|usd|%|tiết|giờ|phút|tuổi|người|lần|km|m\b|kg|tấn|ha\b|"
                        r"ngày|tuần|tháng|năm(?!\s*\d)|học sinh|ca\b|độ|điểm|bàn|trận|vòng|con|chiếc|căn|phòng)",
                        re.IGNORECASE)


def _date_matches(claim: str) -> list[re.Match]:
    """Ngày d/m(/y) thật: có năm, hoặc ngay sau từ chỉ thời gian ("sáng 21-11") – không lấy khoảng số "3-4 triệu"."""
    return [m for m in DATE_DMY.finditer(claim) if _valid_dmy(m)
            and (m.group(3) or (DATE_CONTEXT.search(claim[max(0, m.start() - 10):m.start()])
                                and not RANGE_UNIT.match(claim, m.end())))]


def _format_date(day: int, month: int, year: str | None, sep: str, pad: bool) -> str:
    parts = [f"{day:02d}" if pad else str(day), f"{month:02d}" if pad else str(month)]
    if year:
        parts.append(year)
    return sep.join(parts)


def date_variant(claim: str, evidence: str, rng: random.Random, shift: bool) -> str | None:
    """Đổi ký tự phân cách / số 0 đứng đầu của ngày có trong đoạn; shift=True thì đổi cả ngày (tương phản)."""
    options = [m for m in _date_matches(claim) if m.group(0) in evidence]
    if not options:
        return None
    match = rng.choice(options)
    day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
    seps = [s for s in "/-." if s != re.sub(r"\d", "", match.group(0))[:1]]
    sep, pad = rng.choice(seps), rng.random() < 0.25
    if shift:
        candidates = [d for d in range(1, 29) if abs(d - day) >= 2 and str(d) not in re.findall(r"\d+", evidence)]
        if not candidates:
            return None
        day = rng.choice(candidates)
    return _replace(claim, match, _format_date(day, month, year, sep, pad))


def count_variant(claim: str, evidence: str, rng: random.Random, shift: bool) -> str | None:
    """"2 năm" ↔ "hai năm" (đoạn phải có cùng số dưới dạng chữ hoặc số)."""
    options = []
    for m in SMALL_COUNT.finditer(claim):
        n = int(m.group(1))
        if n in DIGIT_WORDS and m.group(0) in evidence:
            options.append((m, n, True))
    for m in WORD_COUNT.finditer(claim):
        n = WORD_DIGITS[m.group(1).lower()]
        if m.group(0) in evidence:
            options.append((m, n, False))
    if not options:
        return None
    match, n, to_word = rng.choice(options)
    if shift:
        choices = [k for k in DIGIT_WORDS if abs(k - n) >= 2 and k != 5]
        n = rng.choice(choices)
    number = DIGIT_WORDS[n] if to_word else str(n)
    return _replace(claim, match, f"{number} {match.group(2)}")


def round_variant(claim: str, evidence: str, rng: random.Random, shift: bool) -> str | None:
    """"700.000 đồng" → "700 nghìn đồng", "5.000.000" → "5 triệu"."""
    options = [m for m in ROUND_THOUSANDS.finditer(claim) if m.group(0) in evidence]
    if not options:
        return None
    match = rng.choice(options)
    head, scale = int(match.group(1)), SCALE[match.group(2).count(".000")]
    if shift:
        head = head * rng.choice((2, 3)) if head < 300 else max(1, head // 2)
    return _replace(claim, match, f"{head} {scale}")


def approximate_variant(claim: str, evidence: str, rng: random.Random, shift: bool) -> str | None:
    """Số trong đoạn → "hơn/gần/khoảng" đúng chiều; shift=True → sai xa (tương phản)."""
    options = []
    for m in DECIMAL.finditer(claim):
        if m.group(0) in evidence:
            options.append((m, float(f"{m.group(1)}.{m.group(2)}")))
    for m in INTEGER.finditer(claim):
        value = int(m.group(1))
        if m.group(0) in evidence and not 1900 <= value <= 2100 and value >= 20:
            options.append((m, float(value)))
    if not options:
        return None
    match, value = rng.choice(options)
    before = claim[max(0, match.start() - 12):match.start()].lower()
    if re.search(r"(hơn|trên|gần|khoảng|dưới|xấp xỉ|chừng)\s*$", before):
        return None
    if shift:
        qualifier, number = rng.choice((("hơn", value * rng.uniform(1.8, 3.0)), ("gần", value * rng.uniform(0.3, 0.55)),
                                        ("khoảng", value * rng.choice((0.4, 2.5)))))
        number = int(round(number))
    elif value != int(value):
        qualifier, number = "hơn", int(value)                       # 430,5 → hơn 430
    else:
        step = 10 ** max(0, len(str(int(value))) - 2)                # 2 chữ số có nghĩa
        down, up = (int(value) // step) * step, -(-int(value) // step) * step
        if down == value:
            return None
        qualifier, number = rng.choice((("hơn", down), ("gần", up), ("khoảng", down if value - down < up - value else up)))
        if qualifier == "khoảng" and abs(number - value) > 0.1 * value:
            return None
    return _replace(claim, match, f"{qualifier} {number}")


LABEL_PRESERVING = (date_variant, count_variant, round_variant)
SUPPORTED_ONLY = (approximate_variant,)
CONTRAST = (date_variant, count_variant, round_variant, approximate_variant)


def augment(frame: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, dict[str, int]]:
    rng = random.Random(seed)
    rows, stats = [], {}

    def add(record, claim: str, label: int, kind: str) -> None:
        rows.append({"Statement": claim, "Evidence": record.Evidence, "Url": record.Url, "labels": label,
                     "label_origin": "augmented", "sample_weight": 1.0, "kind": kind})
        stats[kind] = stats.get(kind, 0) + 1

    for record in frame.itertuples():
        claim, evidence, label = str(record.Statement), str(record.Evidence), int(record.labels)
        funcs = list(LABEL_PRESERVING + (SUPPORTED_ONLY if label == SUPPORTED else ()))
        rng.shuffle(funcs)
        for func in funcs:
            new = func(claim, evidence, rng, False)
            if new and new != claim:
                add(record, new, label, f"format_{func.__name__.removesuffix('_variant')}")
                break
        if label != SUPPORTED:
            continue
        funcs = list(CONTRAST)
        rng.shuffle(funcs)
        for func in funcs:
            new = func(claim, evidence, rng, True)
            if new and new != claim:
                add(record, new, REFUTED, f"contrast_{func.__name__.removesuffix('_variant')}")
                break
    return pd.DataFrame(rows, columns=list(frame.columns)), stats


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=ROOT / "data/processed/verifier_windows_v3")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/verifier_windows_v4")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train, dev = pd.read_parquet(args.source / "train.parquet"), pd.read_parquet(args.source / "dev.parquet")
    train_aug, train_stats = augment(train, args.seed)
    dev_aug, dev_stats = augment(dev, args.seed + 1)
    combined = pd.concat([train, train_aug], ignore_index=True).sample(frac=1.0, random_state=args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(args.output / "train.parquet", index=False)
    dev.to_parquet(args.output / "dev.parquet", index=False)          # chọn checkpoint trên dev GỐC
    dev_aug.to_parquet(args.output / "dev_augmented.parquet", index=False)
    manifest = {
        "experiment": "RT-V4 verifier: RT-V3 windows + format-invariance and contrast augmentation",
        "source": str(args.source.relative_to(ROOT)), "seed": args.seed,
        "train": {"original": len(train), "augmented": len(train_aug), "kinds": train_stats,
                  "labels": {str(k): int(v) for k, v in combined.labels.value_counts().sort_index().items()}},
        "dev": {"rows": len(dev), "note": "dev.parquet = dev RT-V3 nguyên vẹn (chọn checkpoint)"},
        "dev_augmented": {"rows": len(dev_aug), "kinds": dev_stats, "note": "chỉ để đo, không chọn checkpoint"},
        "files": {name: sha256(args.output / name) for name in ("train.parquet", "dev.parquet", "dev_augmented.parquet")},
    }
    (args.output / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("train", "dev_augmented")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
