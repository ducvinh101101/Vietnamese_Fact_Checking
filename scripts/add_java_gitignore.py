"""Add the project-local Java runtime to Git exclusions exactly once."""
from pathlib import Path


path = Path(".gitignore")
text = path.read_text(encoding="utf-8")
entry = "\n# Project-local runtime; downloaded automatically by scripts/download_portable_java.py.\ntools/java17/\n"
if "tools/java17/" not in text:
    path.write_text(text.rstrip() + entry, encoding="utf-8")
    print("Added tools/java17/ to .gitignore")
else:
    print("tools/java17/ is already ignored")
