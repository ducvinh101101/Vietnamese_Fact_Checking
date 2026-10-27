"""Offline diagnosis; never fits/tunes a model or edits gold/config/checkpoints."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import pandas as pd
from src.evidence_focus import average_probabilities, ensemble_texts, focus_text, split_sentences
from src.schemas import Evidence, RetrievedEvidence
from src.system_builder import SystemOptions, build_system, build_verifier, load_config

LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO")
OUT = Path(__file__).resolve().parent


def fixed_items(passages):
    return [RetrievedEvidence(Evidence(f"diag-doc-{i}", f"e{i}", text), float(len(passages) - i + 1))
            for i, text in enumerate(passages, 1)]


def probabilities(verifier, claim, passages):
    if not passages:
        return []
    if verifier.evidence_view == "ensemble":
        return average_probabilities(verifier.predict_probabilities_batch(claim, ensemble_texts(claim, passages)), 3)
    return verifier.predict_probabilities_batch(claim, [focus_text(claim, p, verifier.evidence_view) for p in passages])


def describe(verifier, claim, items):
    result = verifier.verify(claim, items)
    probs = probabilities(verifier, claim, [item.evidence.content for item in items])
    return {"label": result.label, "confidence": result.confidence, "evidence_ids": result.evidence_ids,
            "explanation": result.explanation,
            "per_passage_probabilities": [dict(zip(LABELS, p)) for p in probs]}


def summary(rows, key, expected="gold_label"):
    matrix = {label: {p: 0 for p in LABELS} for label in LABELS}
    confidence = []
    errors_high = 0
    for row in rows:
        prediction = row[key]
        matrix[row[expected]][prediction["label"]] += 1
        confidence.append(prediction["confidence"])
        errors_high += int(prediction["label"] != row[expected] and prediction["confidence"] >= .9)
    correct = sum(matrix[label][label] for label in LABELS)
    f1 = []
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in LABELS if other != label)
        fn = sum(matrix[label][other] for other in LABELS if other != label)
        f1.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
    return {"n": len(rows), "correct": correct, "accuracy": correct / len(rows), "macro_f1": mean(f1),
            "predicted_counts": dict(Counter(row[key]["label"] for row in rows)),
            "mean_confidence": mean(confidence), "wrong_with_confidence_ge_0_9": errors_high,
            "confusion_rows_gold_columns_predicted": matrix}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    config = load_config(ROOT)
    verifier, fallback = build_verifier(config, ROOT, require_phobert=True)
    if fallback:
        raise RuntimeError("No fallback allowed for diagnosis")
    system = build_system(SystemOptions(mode="local", require_phobert=True), config=config, root=ROOT, verifier=verifier)
    frame = pd.read_parquet(ROOT / "data/processed/vifactcheck_group_split/dev.parquet")
    # Freeze selection before looking at outputs. This is diagnosis on DEV, not a new independent score.
    sample = pd.concat([frame[frame.labels == label].sample(n=12, random_state=137 + label) for label in range(3)])
    corpus = system.pipeline.retriever.evidence_items
    corpus_summary = {"passages": len(corpus), "documents": len({e.document_id for e in corpus}),
                      "published_at_present": sum(bool(e.published_at) for e in corpus)}
    dev_rows = []
    for position, (index, row) in enumerate(sample.iterrows(), 1):
        claim = str(row.Statement)
        raw_result = system.check(claim)
        retrieved = system.pipeline.retriever.search(claim, top_k=3)
        row_info = {
            "source_row_id": int(index), "claim": claim, "gold_label": LABELS[int(row.labels)],
            "annotated_evidence": str(row.Evidence), "gold_url": str(row.Url),
            "oracle": describe(verifier, claim, fixed_items([str(row.Evidence)])),
            "local_final": raw_result["verdict"],
            "local_raw": describe(verifier, claim, retrieved),
            "gold_url_rank_at_top3": next((i for i, item in enumerate(retrieved, 1) if item.evidence.url == str(row.Url)), None),
            "retrieved": [{"passage_id": e.evidence.passage_id, "score": e.score, "url": e.evidence.url,
                           "content": e.evidence.content} for e in retrieved],
        }
        dev_rows.append(row_info)
        print(f"DEV {position}/36 oracle={row_info['oracle']['label']} local={row_info['local_final']['label']}", flush=True)
    controls = [
        ("SUPPORTED", "Phòng Bình Minh có 12 chiếc ghế.", ["Phòng Bình Minh có 12 chiếc ghế."]),
        ("REFUTED", "Phòng Bình Minh có 18 chiếc ghế.", ["Phòng Bình Minh có đúng 12 chiếc ghế."]),
        ("NOT_ENOUGH_INFO", "Phòng Bình Minh có 12 chiếc ghế.", ["Phòng Bình Minh vừa được sơn lại màu vàng."]),
        ("SUPPORTED", "Xưởng gốm Hạ Vân đóng cửa vào thứ Hai.", ["Xưởng gốm Hạ Vân đóng cửa vào thứ Hai."]),
        ("REFUTED", "Xưởng gốm Hạ Vân mở cửa vào thứ Hai.", ["Xưởng gốm Hạ Vân đóng cửa suốt ngày thứ Hai, không nhận khách."]),
        ("NOT_ENOUGH_INFO", "Xưởng gốm Hạ Vân đóng cửa vào thứ Hai.", ["Xưởng gốm Hạ Vân nằm cạnh một vườn cây."]),
        ("SUPPORTED", "Chương trình Góp Sách trao tổng cộng 90 cuốn qua hai đợt.",
         ["Đợt đầu chương trình Góp Sách trao 40 cuốn.", "Đợt thứ hai trao 50 cuốn khác. Chương trình chỉ có hai đợt."]),
    ]
    control_rows = []
    for expected, claim, passages in controls:
        separate = describe(verifier, claim, fixed_items(passages))
        joined = describe(verifier, claim, fixed_items([" ".join(passages)]))
        control_rows.append({"claim": claim, "gold_label": expected, "evidence": passages,
                             "separate": separate, "joined": joined})
        print(f"CONTROL {expected} -> {separate['label']}", flush=True)
    queries = [
        "Hà Nội là thủ đô của Việt Nam.",
        "Thủ đô của Việt Nam là Thành phố Hồ Chí Minh.",
        "Giá xăng tăng từ chiều nay.",
        "Python là một ngôn ngữ lập trình.",
        "Tổng thống Brazil Lula hoãn chuyến thăm 6 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn.",
        "Tổng thống Brazil Lula hoãn chuyến thăm 10 ngày tới Trung Quốc do bệnh viêm phổi chưa khỏi hẳn.",
        "Thư viện Hạ Phong mở cửa lúc 7 giờ sáng.",
    ]
    probe_rows = []
    for claim in queries:
        response = system.check(claim)
        probe_rows.append({"claim": claim, "verdict": response["verdict"],
                           "retrieved": response["retrieval"]["evidence"], "diagnostics": response["diagnostics"]})
        print(f"QUERY {response['verdict']['label']} conf={response['verdict']['confidence']}", flush=True)
    report = {
        "purpose": "Offline diagnosis only. No fitting, threshold search, checkpoint edits or gold changes.",
        "dev_selection": {"seed_base": 137, "per_label": 12, "rows": [int(i) for i in sample.index]},
        "configuration": config, "corpus": corpus_summary,
        "dev_summary": {key: summary(dev_rows, key) for key in ("oracle", "local_raw", "local_final")},
        "dev_gold_url_retrieved_top3": sum(row["gold_url_rank_at_top3"] is not None for row in dev_rows),
        "dev_rows": dev_rows, "controls": control_rows, "local_queries": probe_rows,
        "checkpoint_sha256": hashlib.sha256((ROOT / config["verification"]["model_path"] / "model.safetensors").read_bytes()).hexdigest(),
    }
    path = OUT / "diagnostics.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["dev_summary"], ensure_ascii=False, indent=2), flush=True)
    print(f"Saved {path}", flush=True)


if __name__ == "__main__":
    main()
