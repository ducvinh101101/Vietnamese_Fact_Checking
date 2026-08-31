"""Configure the project-local Java runtime before py_vncorenlp is imported."""
from pathlib import Path


path = Path("src/phobert_fact_checker.py")
text = path.read_text(encoding="utf-8")
needle = "\n\nclass PhoBERTFactChecker:\n"
addition = '''\n\ndef prepare_java_runtime() -> None:
    """Use the project-local Java runtime when Java is not installed system-wide."""
    if os.name != "nt" or os.environ.get("JAVA_HOME"):
        return
    java_root = Path(__file__).resolve().parents[1] / "tools" / "java17"
    executable = next(java_root.glob("**/bin/java.exe"), None) if java_root.exists() else None
    if executable is None:
        return
    java_home = executable.parent.parent
    os.environ["JAVA_HOME"] = str(java_home)
    os.environ["PATH"] = f"{executable.parent}{os.pathsep}{os.environ.get('PATH', '')}"


class PhoBERTFactChecker:
'''
if "def prepare_java_runtime" not in text:
    text = text.replace(needle, addition)
text = text.replace(
    "            prepare_torch_dll_path()\n            import py_vncorenlp",
    "            prepare_torch_dll_path()\n            prepare_java_runtime()\n            import py_vncorenlp",
)
path.write_text(text, encoding="utf-8")
print("Patched project-local Java runtime support.")
