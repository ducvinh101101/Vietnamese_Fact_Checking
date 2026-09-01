"""Derive the E3 long-context Kaggle runner from the frozen E2 runner."""
from pathlib import Path


source = Path("kaggle/train_phobert_kaggle.py")
target = Path("kaggle/train_phobert_e3_long_context.py")
text = source.read_text(encoding="utf-8")
replacements = {
    "E2 — Fine-tune PhoBERT-base": "E3 — PhoBERT-base với ngữ cảnh dài hơn",
    'WORK_DIR = Path("/kaggle/working/phobert_e2")': 'WORK_DIR = Path("/kaggle/working/phobert_e3")',
    "MAX_LENGTH = 256": "MAX_LENGTH = 384",
    "per_device_train_batch_size=16,": "per_device_train_batch_size=8,",
    "gradient_accumulation_steps=1,": "gradient_accumulation_steps=2,",
    '"experiment": "E2",': '"experiment": "E3_long_context",',
    '"max_length": MAX_LENGTH,': '"max_length": MAX_LENGTH,',
    '"train_batch_size": 16,': '"train_batch_size": 8,\n            "gradient_accumulation_steps": 2,',
    '"e2_phobert_metrics.json"': '"e3_phobert_metrics.json"',
    '"e2_phobert_test_predictions.csv"': '"e3_phobert_test_predictions.csv"',
}
for old, new in replacements.items():
    if old not in text:
        raise RuntimeError(f"Missing expected E2 fragment: {old}")
    text = text.replace(old, new)
target.write_text(text, encoding="utf-8")
print(f"Created: {target}")
