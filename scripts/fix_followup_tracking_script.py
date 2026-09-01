"""Fix one mapping typo in the Vinh follow-up tracking helper."""
from pathlib import Path


path = Path("scripts/add_vinh_followup_tracking.py")
text = path.read_text(encoding="utf-8")
bad = '        "phobert_e3/e3_phobert_metrics.json", "phobert_e7/e7_phobert_metrics.json",\n'
good = '        "phobert_e3/e3_phobert_metrics.json": "phobert_e7/e7_phobert_metrics.json",\n'
if bad not in text:
    raise RuntimeError("Expected mapping typo was not found.")
path.write_text(text.replace(bad, good), encoding="utf-8")
print("Fixed tracking helper mapping.")
