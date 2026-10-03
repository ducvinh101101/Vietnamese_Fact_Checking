"""Create the W3-04 audit of ten wrong predictions from W4-02.

The categories are evidence-based triage labels, not claims of a root cause:
retrieval misses use the URL-level proxy and verifier cases mean the gold URL
was in top-k but the final verdict was still wrong.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "outputs/predictions/w4_02_local_end_to_end_test.csv"
OUTPUT_JSON = ROOT / "outputs/metrics/w3_04_local_pipeline_error_audit.json"
OUTPUT_CSV = ROOT / "outputs/predictions/w3_04_local_pipeline_error_audit.csv"
OUTPUT_DOC = ROOT / "docs/W3_04_PIPELINE_ERROR_ANALYSIS.md"
BUCKETS = ("retrieval_url_miss", "nei_decision", "verifier_with_gold_url")


def stable_key(row: pd.Series) -> str:
    return hashlib.sha256(str(row["source_row_id"]).encode("utf-8")).hexdigest()


def concise(value: object, limit: int = 180) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def category(row: pd.Series) -> str:
    retrieved = str(row["gold_url_retrieved_at_top_k"]).strip().lower() == "true"
    if not retrieved:
        return "retrieval_url_miss"
    if "NOT_ENOUGH_INFO" in {str(row["gold_label"]), str(row["predicted_label"])}:
        return "nei_decision"
    return "verifier_with_gold_url"


def main() -> None:
    if not PREDICTIONS.exists():
        raise FileNotFoundError(f"Chưa có kết quả W4-02: {PREDICTIONS}")
    frame = pd.read_csv(PREDICTIONS, keep_default_na=False)
    wrong = frame.loc[frame["gold_label"] != frame["predicted_label"]].copy()
    wrong["triage_category"] = wrong.apply(category, axis=1)
    wrong["stable_key"] = wrong.apply(stable_key, axis=1)

    selected_parts: list[pd.DataFrame] = []
    # Allocate a balanced audit first; fill remaining slots deterministically.
    targets = {"retrieval_url_miss": 4, "nei_decision": 3, "verifier_with_gold_url": 3}
    for bucket in BUCKETS:
        selected_parts.append(
            wrong.loc[wrong["triage_category"] == bucket].sort_values("stable_key").head(targets[bucket])
        )
    selected = pd.concat(selected_parts, ignore_index=True)
    if len(selected) < 10:
        used = set(selected["source_row_id"].astype(str))
        extra = wrong.loc[~wrong["source_row_id"].astype(str).isin(used)].sort_values("stable_key")
        selected = pd.concat([selected, extra.head(10 - len(selected))], ignore_index=True)
    selected = selected.head(10).copy()
    if len(selected) < 10:
        raise RuntimeError(f"Cần ít nhất 10 lỗi để audit, chỉ có {len(selected)}")

    selected.drop(columns=["stable_key"], inplace=True)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    audit = {
        "purpose": "W3-04: deterministic audit of ten W4-02 wrong local end-to-end predictions.",
        "triage_definition": {
            "retrieval_url_miss": "Annotated evidence URL was absent from BM25 top-k. This is a URL-level retrieval proxy.",
            "nei_decision": "Gold or prediction is NOT_ENOUGH_INFO while the annotated URL is present in top-k.",
            "verifier_with_gold_url": "Annotated URL was in top-k, neither side is NEI, and the verdict is wrong. It indicates a verifier/candidate-evidence issue, not a proven semantic cause.",
        },
        "all_wrong_predictions": int(len(wrong)),
        "all_error_category_counts": dict(Counter(wrong["triage_category"])),
        "selection": "4 retrieval misses, 3 NEI decisions, 3 verifier-with-gold-URL when available; remaining slots filled by SHA-256(source_row_id).",
        "selected_cases": selected.to_dict(orient="records"),
        "source_predictions": str(PREDICTIONS.relative_to(ROOT)),
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# W3-04 — Phân tích lỗi pipeline local",
        "",
        "## Phạm vi và phương pháp",
        "",
        f"Audit chọn cố định 10 trong {len(wrong)} dự đoán sai của W4-02. Các nhãn phân loại là triage quan sát được, không khẳng định nguyên nhân gốc: URL evidence vàng có mặt trong BM25 top-k chỉ là proxy URL-level, không chứng minh passage được trích dẫn đủ ngữ nghĩa.",
        "",
        "| Nhóm triage | Số lỗi toàn bộ | Ý nghĩa quan sát được |",
        "| --- | ---: | --- |",
    ]
    descriptions = {
        "retrieval_url_miss": "URL evidence vàng không trong top-k.",
        "nei_decision": "Sai verdict có liên quan NEI dù URL vàng có trong top-k.",
        "verifier_with_gold_url": "URL vàng có trong top-k, không phải NEI, nhưng verdict vẫn sai.",
    }
    counts = Counter(wrong["triage_category"])
    for bucket in BUCKETS:
        lines.append(f"| {bucket} | {counts[bucket]} | {descriptions[bucket]} |")
    lines += [
        "",
        "## 10 mẫu audit",
        "",
        "| ID | Nhóm | Gold → dự đoán | Conf. | Hạng URL vàng | Claim (rút gọn) |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in selected.itertuples(index=False):
        raw_rank = str(row.first_gold_url_rank_at_top_k).strip()
        rank = "–" if not raw_rank or raw_rank.lower() == "nan" else str(int(float(raw_rank)))
        claim = concise(row.claim).replace("|", "\\|")
        lines.append(
            f"| {row.source_row_id} | {row.triage_category} | {row.gold_label} → {row.predicted_label} | "
            f"{float(row.confidence):.4f} | {rank} | {claim} |"
        )
    lines += [
        "",
        "## Hành động rút ra",
        "",
        "- `retrieval_url_miss`: ưu tiên cải thiện retrieval trước khi quy kết lỗi cho verifier; đánh giá URL-level hiện không thay thế qrels passage-level.",
        "- `nei_decision`: rà soát threshold/hiệu chuẩn trên dev và evidence được trích dẫn; không tune lại bằng test này.",
        "- `verifier_with_gold_url`: cần kiểm tra passage cụ thể, phủ định, thời gian và thực thể trước khi thay đổi model; URL đúng không đồng nghĩa passage đủ chứng cứ.",
        "",
        f"Artifact máy đọc: `{OUTPUT_JSON.relative_to(ROOT)}`; bảng đầy đủ: `{OUTPUT_CSV.relative_to(ROOT)}`.",
    ]
    OUTPUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"W3-04 audit created: {len(selected)} cases")


if __name__ == "__main__":
    main()
