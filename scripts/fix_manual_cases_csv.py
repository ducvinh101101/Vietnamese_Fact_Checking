"""Keep the simple comma-delimited manual test file structurally valid."""
from pathlib import Path


path = Path("data/evaluation/vinh_manual_claims_v1.csv")
text = path.read_text(encoding="utf-8")
text = text.replace("Nguồn chỉ đưa khuyến cáo, không có lệnh cấm", "Nguồn chỉ đưa khuyến cáo và không có lệnh cấm")
path.write_text(text, encoding="utf-8")
print("Fixed comma in manual-case note.")
