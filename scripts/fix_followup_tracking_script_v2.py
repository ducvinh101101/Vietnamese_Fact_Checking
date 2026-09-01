"""Complete repair of the Vinh tracking helper after the E7 rename."""
from pathlib import Path


path = Path("scripts/add_vinh_followup_tracking.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    '        "e3_phobert_test_predictions.csv", "e7_phobert_test_predictions.csv",\n',
    '        "e3_phobert_test_predictions.csv": "e7_phobert_test_predictions.csv",\n',
)
text = text.replace('Path("docs/KAGGLE_PHOBERT_E3.md")', 'Path("docs/KAGGLE_PHOBERT_E7.md")')
path.write_text(text, encoding="utf-8")
print("Repaired E7 tracking helper.")
