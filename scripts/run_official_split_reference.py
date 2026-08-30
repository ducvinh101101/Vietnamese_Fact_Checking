"""Chạy E1 trên official split chỉ để so sánh tham chiếu với group split."""

from __future__ import annotations

import json
from pathlib import Path

from datasets import load_from_disk

from train_baseline import CS, LABEL_NAMES, create_pipeline, metrics, pair_text


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "vifactcheck"
REPORT = ROOT / "outputs" / "metrics" / "e1_official_split_reference.json"


def main() -> None:
    data = load_from_disk(str(RAW_DIR))
    train, dev, test = (data[name].to_pandas() for name in ("train", "dev", "test"))
    dev_results = {}
    best_c, best_f1 = None, -1.0
    for c_value in CS:
        model = create_pipeline(c_value)
        model.fit(pair_text(train), train["labels"])
        current = metrics(dev["labels"], model.predict(pair_text(dev)))
        dev_results[str(c_value)] = current
        if current["macro_f1"] > best_f1:
            best_c, best_f1 = c_value, current["macro_f1"]
    assert best_c is not None
    model = create_pipeline(best_c)
    model.fit(pair_text(train), train["labels"])
    report = {
        "experiment": "E1-reference",
        "purpose": "Reference only; not used to select the project model or claim primary performance.",
        "protocol": "official ViFactCheck split with URL/context overlap",
        "selected_c": best_c,
        "dev_results": dev_results,
        "test_metrics": metrics(test["labels"], model.predict(pair_text(test))),
        "label_names": LABEL_NAMES,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
