"""W5-02: dựng bảng so sánh đánh giá nhiều tầng từ các file metrics đã có.

Đọc các JSON metrics (oracle E2, BM25-local, reranked-local, và về sau web/fusion)
rồi in một bảng Markdown thống nhất, kèm ghi chú giao thức cho từng tầng. Script
KHÔNG chạy model; nó chỉ tổng hợp kết quả Vinh đã sinh ra, nên tách metric theo
đúng giao thức và không trộn số khác điều kiện.

    py -3.13 scripts/build_evaluation_comparison.py \
        --tier "Oracle E2 (gold evidence)=outputs/metrics/e2_phobert_metrics.json" \
        --tier "BM25-local E2E=outputs/metrics/w4_02_local_end_to_end_test.json" \
        --tier "Reranked-local E2E=outputs/metrics/reranked_e2e_test.json" \
        --output docs/W5_02_EVALUATION_COMPARISON.md

Mỗi --tier là "Tên hiển thị=đường_dẫn.json". Thứ tự giữ nguyên như truyền vào.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _get(node: dict, *path, default=None):
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def extract_row(name: str, metrics: dict) -> dict:
    """Rút các chỉ số so sánh được từ nhiều schema metrics khác nhau của dự án.

    Xử lý ba dạng: end-to-end (khối ``classification``), oracle E2 (``test_metrics``
    + ``test_per_label``), và content baseline E9 (khối ``metrics``).
    """
    classification = metrics.get("classification") or metrics.get("metrics") or {}
    test_metrics = metrics.get("test_metrics", {})
    per_label = classification.get("per_label") or metrics.get("test_per_label") or {}

    def label_f1(label: str):
        cell = per_label.get(label, {})
        return cell.get("f1-score", cell.get("f1"))

    accuracy = classification.get("accuracy")
    if accuracy is None:
        accuracy = test_metrics.get("test_accuracy")
    macro_f1 = classification.get("macro_f1")
    if macro_f1 is None:
        macro_f1 = test_metrics.get("test_macro_f1") or classification.get("macro_f1")

    retrieval = _get(classification, "retrieval_and_citation") or metrics.get("retrieval_and_citation", {})
    queries = _get(metrics, "evaluation_split", "queries")
    if queries is None and per_label:
        supports = [cell.get("support") for cell in per_label.values() if isinstance(cell, dict)]
        supports = [value for value in supports if isinstance(value, (int, float))]
        queries = int(sum(supports)) if supports else None
    return {
        "name": name,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "f1_supported": label_f1("SUPPORTED"),
        "f1_refuted": label_f1("REFUTED"),
        "f1_nei": label_f1("NOT_ENOUGH_INFO"),
        "gold_url_recall": _get(retrieval, "gold_url_recall_at_top_k"),
        "citation_match": _get(retrieval, "citation_url_matches_gold_rate"),
        "queries": queries,
    }


def _fmt(value, percent: bool = True) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value * 100:.2f}%" if percent else str(value)
    return str(value)


def build_markdown(rows: list[dict]) -> str:
    header = (
        "| Tầng đánh giá | N | Accuracy | Macro-F1 | F1 SUP | F1 REF | F1 NEI | URL Recall@k | Citation URL-match |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    lines = [header]
    for row in rows:
        lines.append(
            f"| {row['name']} | {_fmt(row['queries'], percent=False)} | {_fmt(row['accuracy'])} | "
            f"{_fmt(row['macro_f1'])} | {_fmt(row['f1_supported'])} | {_fmt(row['f1_refuted'])} | "
            f"{_fmt(row['f1_nei'])} | {_fmt(row['gold_url_recall'])} | {_fmt(row['citation_match'])} |"
        )
    body = "\n".join(lines)
    notes = (
        "\n\n## Cách đọc\n\n"
        "- **Oracle** dùng bằng chứng vàng cho sẵn → trần năng lực verifier, KHÔNG phải năng lực hệ thống.\n"
        "- **BM25-local** và **Reranked-local** là end-to-end tự đi tìm bằng chứng trên corpus cục bộ; "
        "chênh lệch giữa oracle và các tầng này là khoảng cách retrieval-to-verdict.\n"
        "- URL Recall@k và citation-match là **proxy URL-level**, không chứng minh passage đủ để entail claim; "
        "xem audit passage-level W5-03a.\n"
        "- Không so accuracy giữa các tầng như thể cùng một phép đo: mỗi tầng có đầu vào bằng chứng khác nhau.\n"
        "- Web/fusion chưa có trong bảng vì bước hợp nhất local+web chưa được triển khai.\n"
    )
    return "# W5-02 — So sánh đánh giá nhiều tầng\n\n" + body + notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", action="append", default=[], metavar="TÊN=ĐƯỜNG_DẪN",
                        help="Một tầng: 'Tên hiển thị=path/metrics.json'. Lặp lại nhiều lần.")
    parser.add_argument("--output", type=Path, help="Ghi Markdown ra file; không có thì in ra stdout")
    args = parser.parse_args()
    if not args.tier:
        raise SystemExit("Cần ít nhất một --tier")

    rows = []
    for spec in args.tier:
        if "=" not in spec:
            raise SystemExit(f"--tier sai định dạng (thiếu '='): {spec}")
        name, path = spec.split("=", 1)
        metrics = json.loads(Path(path).read_text(encoding="utf-8"))
        rows.append(extract_row(name.strip(), metrics))

    markdown = build_markdown(rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown + "\n", encoding="utf-8")
        print(f"Đã ghi {args.output}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
