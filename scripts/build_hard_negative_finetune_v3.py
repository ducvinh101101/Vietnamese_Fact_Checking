"""RT-V3 — bundle huấn luyện có HARD NEGATIVE, sinh tự động CHỈ từ train split.

Vì sao: trên dev, hai lỗi chiếm đa số của RT-V2 là (a) REFUTED bị đoán SUPPORTED
(claim gần giống nguồn nhưng sai một chi tiết) và (b) NEI bị đoán quyết đoán (bằng
chứng cùng chủ đề nhưng không xác nhận claim). Luật hậu kiểm không sửa được hết; cách
đúng là cho mô hình thấy thêm đúng hai dạng này khi huấn luyện.

Sinh từ các cặp SUPPORTED (nhãn 0) của train split:

* ``synthetic_refuted_number``    đổi một con số có mặt trong cả claim và bằng chứng.
* ``synthetic_refuted_direction`` đổi chiều tăng<->giảm, lên<->xuống, cao<->thấp, ...
* ``synthetic_refuted_negation``  đã->chưa, có->không có, được->không được.
  Mỗi câu sinh ra được kiểm lại bằng src/minimal_pair.analyse: phải là ĐÚNG MỘT lật nghĩa
  so với claim gốc, nếu không thì bỏ.
* ``hard_nei_other_article``      claim (nhãn 0/1) ghép với bằng chứng của MỘT BÀI KHÁC (URL
  khác) cùng chủ đề — xếp hạng cao theo BM25 nhưng phủ claim thấp (< ngưỡng) -> nhãn NEI.
  Đây là nhãn bạc: hai bài khác nhau đôi khi cùng đưa một tin, nên có worksheet kiểm tra.

Nguyên tắc (giống RT-V2): giữ nguyên mọi cặp gold + silver RT-V2; cặp tổng hợp có trọng số
0,5; KHÔNG đọc nội dung dev/test (chỉ URL để loại trùng); không ghi đè thí nghiệm cũ; dev
giữ nguyên để chọn checkpoint; test KHÔNG có trong bundle. Bundle dùng thẳng
kaggle/finetune_phobert_retrieval_v1.py (tiếp tục từ RT-V2):

    py -3.13 scripts/build_hard_negative_finetune_v3.py
    # Kaggle: --data-dir <bundle> --model-dir <rt_v2_balanced/best_model> --experiment RT-V3 --epochs 2

Worksheet ``hard_negative_spotcheck_v3_worksheet.csv`` (60 cặp ngẫu nhiên, đọc mù) để NGƯỜI đọc,
cột ``reviewed_pair_label`` để trống — không điền bằng AI. Chấm bằng:

    py -3.13 scripts/score_review_worksheets.py --spotcheck data/processed/retrieval_finetune_v3_hardneg/hard_negative_spotcheck_v3_worksheet.csv --key data/processed/retrieval_finetune_v3_hardneg/hard_negative_spotcheck_v3_key.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evidence_focus import sentence_score  # noqa: E402
from src.minimal_pair import analyse  # noqa: E402

PAIR = ["Statement", "Evidence"]
SYNTH_WEIGHT = 0.5
_NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)(?![\w])")
# Cố ý KHÔNG gồm lên/xuống (lên tiếng, lên án, xuống đường...) và chỉ đổi từ viết thường
# ('Cao' trong Cao Bằng, Cao Văn A là tên riêng).
DIRECTION_SWAPS = {"tăng": "giảm", "giảm": "tăng", "cao": "thấp", "thấp": "cao",
                   "nhiều": "ít", "ít": "nhiều", "thắng": "thua", "thua": "thắng"}
# Từ ghép: đổi chiều sẽ ra từ vô nghĩa (tăng cường -> "giảm cường", cao tốc -> "thấp tốc").
_COMPOUND_NEXT = {
    "tăng": {"cường", "trưởng", "ca", "áp", "huyết"}, "giảm": {"thiểu", "sát", "nhẹ", "biên", "phát"},
    "cao": {"su", "điểm", "tốc", "học", "đẳng", "nguyên", "ốc", "cấp", "tầng", "thủ", "kiến", "niên", "lương", "trào", "ủy", "uỷ"},
    "thấp": {"thoáng"}, "thắng": {"lợi", "cảnh", "thế"}, "thua": {"lỗ", "thiệt", "kém"},
    "nhiều": set(), "ít": {"ỏi"},
}
NEGATION_SWAPS = ((r"\bđã\b", "chưa"),
                  (r"\bcó\b(?!\s+(?:thể|lẽ|vẻ|khi|lúc|điều|người|ai|nhiều|ít)\b)", "không có"),
                  (r"\bđược\b(?!\s+(?:biết|cho là|xem là|coi là)\b)", "không được"))
_WORD = re.compile(r"\w+", re.UNICODE)


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _changed_number(token: str, rng: random.Random) -> str | None:
    digits = token.replace(".", "").replace(",", ".")
    try:
        value = float(digits)
    except ValueError:
        return None
    if 1900 <= value <= 2100 and float(value).is_integer():
        new = int(value) + rng.choice((-3, -2, -1, 1, 2, 3))         # năm
    elif float(value).is_integer():
        step = max(1, round(abs(value) * rng.choice((0.2, 0.3, 0.5))))
        new = int(value) + rng.choice((-1, 1)) * step
        if new <= 0:
            new = int(value) + step
    else:
        new = round(value * rng.choice((0.7, 1.3, 1.5)), 1)
        if new == value:
            return None
    text = f"{new:,}".replace(",", ".") if isinstance(new, int) and abs(new) >= 1000 and "." in token else str(new)
    return text.replace(".", ",") if isinstance(new, float) and "," in token else text


def perturb_number(claim: str, evidence: str, rng: random.Random) -> str | None:
    candidates = [m for m in _NUMBER.finditer(claim) if m.group(1) in evidence]
    if not candidates:
        return None
    match = rng.choice(candidates)
    new = _changed_number(match.group(1), rng)
    return None if new is None else claim[:match.start(1)] + new + claim[match.end(1):]


def perturb_direction(claim: str, evidence: str, rng: random.Random) -> str | None:
    tokens = list(_WORD.finditer(claim))
    words = [m for i, m in enumerate(tokens) if m.group(0) in DIRECTION_SWAPS
             and (i + 1 == len(tokens) or tokens[i + 1].group(0).casefold() not in _COMPOUND_NEXT[m.group(0)])
             and re.search(rf"\b{re.escape(m.group(0))}\b", evidence.casefold())]
    if not words:
        return None
    match = rng.choice(words)
    swap = DIRECTION_SWAPS[match.group(0)]
    return claim[:match.start()] + swap + claim[match.end():]


def perturb_negation(claim: str, evidence: str, rng: random.Random) -> str | None:
    options = [(pattern, repl) for pattern, repl in NEGATION_SWAPS if re.search(pattern, claim)]
    if not options or re.search(r"\b(không|chưa|chẳng)\b", claim.casefold()):
        return None
    pattern, repl = rng.choice(options)
    return re.sub(pattern, repl, claim, count=1)


PERTURBATIONS = {
    "synthetic_refuted_number": (perturb_number, "number"),
    "synthetic_refuted_direction": (perturb_direction, "direction"),
    "synthetic_refuted_negation": (perturb_negation, "negation"),
}


def is_single_flip(original: str, perturbed: str, kind: str) -> bool:
    """Câu sinh ra phải là MỘT lật nghĩa đúng loại so với claim gốc (kiểm bằng minimal_pair)."""
    if not perturbed or perturbed == original:
        return False
    result = analyse(perturbed, original)
    return bool(result and result.contradiction and result.kinds == (kind,))


def synth_refuted(supported: pd.DataFrame, per_kind: int, seed: int) -> pd.DataFrame:
    rows = []
    for offset, (origin, (function, kind)) in enumerate(PERTURBATIONS.items()):
        rng = random.Random(seed + offset)
        order = list(supported.index)
        rng.shuffle(order)
        made = 0
        for index in order:
            if made >= per_kind:
                break
            row = supported.loc[index]
            new = function(str(row.Statement), str(row.Evidence), rng)
            if new and is_single_flip(str(row.Statement), new, kind):
                rows.append({"Statement": new, "Evidence": row.Evidence, "Url": row.Url, "labels": 1,
                             "label_origin": origin, "sample_weight": SYNTH_WEIGHT,
                             "source_statement": row.Statement})
                made += 1
    return pd.DataFrame(rows)


def synth_hard_nei(train: pd.DataFrame, count: int, seed: int, max_coverage: float = 0.55) -> pd.DataFrame:
    """Claim + bằng chứng của bài khác cùng chủ đề (BM25 cao) nhưng phủ claim thấp -> NEI (bạc)."""
    from rank_bm25 import BM25Okapi

    evidence = train.drop_duplicates("Evidence").reset_index(drop=True)
    tokenized = [_WORD.findall(str(text).casefold()) for text in evidence.Evidence]
    bm25 = BM25Okapi(tokenized)
    rng = random.Random(seed)
    decisive = train.loc[train.labels.isin([0, 1])]
    order = list(decisive.index)
    rng.shuffle(order)
    rows = []
    for index in order:
        if len(rows) >= count:
            break
        row = train.loc[index]
        scores = bm25.get_scores(_WORD.findall(str(row.Statement).casefold()))
        for candidate in sorted(range(len(scores)), key=lambda i: -scores[i])[:10]:
            other = evidence.loc[candidate]
            if other.Url == row.Url or scores[candidate] <= 0:
                continue
            if sentence_score(str(row.Statement), str(other.Evidence)) >= max_coverage:
                continue        # bài khác nhưng phủ claim cao -> có thể cùng đưa tin, không dùng
            rows.append({"Statement": row.Statement, "Evidence": other.Evidence, "Url": row.Url, "labels": 2,
                         "label_origin": "hard_nei_other_article", "sample_weight": SYNTH_WEIGHT,
                         "source_statement": row.Statement, "evidence_url": other.Url})
            break
    return pd.DataFrame(rows)


def build(train_gold: pd.DataFrame, base_train: pd.DataFrame, held_urls: set[str], per_kind: int,
          nei_count: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if held_urls & set(train_gold.Url):
        raise ValueError("Train split trùng URL với dev/test")
    supported = train_gold.loc[train_gold.labels == 0]
    synthetic = pd.concat([synth_refuted(supported, per_kind, seed), synth_hard_nei(train_gold, nei_count, seed)],
                          ignore_index=True)
    if "evidence_url" in synthetic and synthetic["evidence_url"].dropna().isin(held_urls).any():
        raise ValueError("Bằng chứng tổng hợp lấy từ URL dev/test")
    existing = set(map(tuple, base_train[PAIR].astype(str).values))
    synthetic = synthetic.loc[[tuple(map(str, pair)) not in existing for pair in synthetic[PAIR].values]]
    synthetic = synthetic.drop_duplicates(PAIR).reset_index(drop=True)
    combined = pd.concat([base_train, synthetic[base_train.columns.intersection(synthetic.columns)]],
                         ignore_index=True)
    if combined.groupby(PAIR)["labels"].nunique().gt(1).any():
        raise ValueError("Bundle có cặp trùng mâu thuẫn nhãn")
    return combined, synthetic


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-kind", type=int, default=150, help="Số REFUTED tổng hợp cho MỖI loại lật nghĩa")
    parser.add_argument("--nei", type=int, default=450, help="Số NEI bài-khác")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/retrieval_finetune_v3_hardneg")
    parser.add_argument("--archive", type=Path, default=ROOT / "kaggle/retrieval_finetune_v3_hardneg.zip")
    args = parser.parse_args()

    split_dir = ROOT / "data/processed/vifactcheck_group_split"
    base_dir = ROOT / "data/processed/retrieval_finetune_v2_balanced"
    if args.output.exists() or args.archive.exists():
        raise FileExistsError("Bundle RT-V3 đã tồn tại; không ghi đè thí nghiệm cũ (đổi --output/--archive)")
    base_manifest = json.loads((base_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    for name, expected in base_manifest["files"].items():
        if sha256(base_dir / name) != expected:
            raise ValueError(f"Bundle RT-V2 không khớp manifest: {name}")
    train_gold = pd.read_parquet(split_dir / "train.parquet")
    base_train = pd.read_parquet(base_dir / "train.parquet")
    held_urls = set(pd.read_parquet(split_dir / "dev.parquet", columns=["Url"]).Url) | \
        set(pd.read_parquet(split_dir / "test.parquet", columns=["Url"]).Url)
    combined, synthetic = build(train_gold, base_train, held_urls, args.per_kind, args.nei, args.seed)

    args.output.mkdir(parents=True)
    combined.to_parquet(args.output / "train.parquet", index=False)
    shutil.copyfile(base_dir / "gold_train.parquet", args.output / "gold_train.parquet")
    shutil.copyfile(base_dir / "dev.parquet", args.output / "dev.parquet")
    synthetic.to_csv(args.output / "synthetic_pairs.csv", index=False, encoding="utf-8-sig")
    # Đọc MÙ, cùng định dạng worksheet spot-check W5-06 để chấm bằng
    # scripts/score_review_worksheets.py --spotcheck ... --key ... (nhãn sinh ra để ở file key).
    names = {0: "SUPPORTED", 1: "REFUTED", 2: "NOT_ENOUGH_INFO"}
    sample = synthetic.sample(n=min(60, len(synthetic)), random_state=args.seed).copy()
    sample.insert(0, "pair_id", [f"HN{i:03d}" for i in range(1, len(sample) + 1)])
    sheet = pd.DataFrame({"pair_id": sample.pair_id, "claim": sample.Statement, "passage": sample.Evidence,
                          "reviewed_pair_label": "", "reviewer": "", "review_reason": ""})
    sheet.to_csv(args.output / "hard_negative_spotcheck_v3_worksheet.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"pair_id": sample.pair_id, "ai_label_hidden": sample.labels.map(names),
                  "label_origin": sample.label_origin, "source_statement": sample.source_statement}).to_csv(
        args.output / "hard_negative_spotcheck_v3_key.csv", index=False, encoding="utf-8-sig")

    files = [args.output / name for name in ("gold_train.parquet", "train.parquet", "dev.parquet")]
    counts = synthetic["label_origin"].value_counts().to_dict()
    manifest = {
        "experiment": "RT-V3 hard negatives (synthetic minimal-pair REFUTED + other-article NEI)",
        "base_bundle": "retrieval_finetune_v2_balanced",
        "base_manifest_sha256": sha256(base_dir / "MANIFEST.json"),
        "source_train_sha256": sha256(split_dir / "train.parquet"),
        "seed": args.seed,
        "synthetic_counts": {k: int(v) for k, v in counts.items()},
        "combined_rows": len(combined),
        "combined_label_counts": {str(k): int(v) for k, v in combined["labels"].value_counts().sort_index().items()},
        "sample_weight": {"original_gold_train": 1.0, "ai_silver": 0.5, "synthetic": SYNTH_WEIGHT},
        "validation": "Mỗi REFUTED tổng hợp là đúng một lật nghĩa theo src/minimal_pair.analyse; NEI dùng bài URL khác, phủ claim < 0,55",
        "heldout_url_check": "passed; dev/test URLs không có trong train hay evidence tổng hợp",
        "test_in_bundle": False,
        "files": {path.name: sha256(path) for path in files},
    }
    (args.output / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files + [args.output / "MANIFEST.json"]:
            archive.write(path, path.name)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"ZIP cho Kaggle: {args.archive}")
    print(f"Worksheet cho người đọc: {args.output / 'hard_negative_spotcheck_v3_worksheet.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
