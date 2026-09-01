"""Allow the standalone evaluation script to import the project package."""
from pathlib import Path


path = Path("scripts/evaluate_manual_claims.py")
text = path.read_text(encoding="utf-8")
text = text.replace("import argparse\nfrom pathlib import Path\n", "import argparse\nimport sys\nfrom pathlib import Path\n")
text = text.replace(
    "from src.pipeline import FactCheckingPipeline\n\n\nROOT = Path(__file__).resolve().parents[1]",
    "ROOT = Path(__file__).resolve().parents[1]\nif str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n\nfrom src.pipeline import FactCheckingPipeline\n\n\n",
)
path.write_text(text, encoding="utf-8")
print("Patched standalone import path.")
