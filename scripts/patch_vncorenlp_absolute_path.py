"""Pass VnCoreNLP an absolute resource path; it changes the process directory internally."""
from pathlib import Path


path = Path("src/phobert_fact_checker.py")
text = path.read_text(encoding="utf-8")
old = 'self.segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(vncorenlp_dir))'
new = 'self.segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(Path(vncorenlp_dir).resolve()))'
if old not in text:
    raise RuntimeError("Expected VnCoreNLP initialization was not found.")
path.write_text(text.replace(old, new), encoding="utf-8")
print("Patched VnCoreNLP to use an absolute resource path.")
