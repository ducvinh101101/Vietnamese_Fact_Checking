"""Thêm DLL search path cho PyTorch trong runtime Windows hiện tại."""

from pathlib import Path


path = Path(__file__).resolve().parents[1] / "src" / "phobert_fact_checker.py"
text = path.read_text(encoding="utf-8")
text = text.replace("from functools import lru_cache\nfrom pathlib import Path\n", "from functools import lru_cache\nfrom pathlib import Path\nimport os\nimport sys\n")
text = text.replace(
    "from src.schemas import RetrievedEvidence, VerificationResult\n\n\nclass PhoBERTFactChecker:",
    '''from src.schemas import RetrievedEvidence, VerificationResult


_DLL_DIRECTORY_HANDLES: list[object] = []


def prepare_torch_dll_path() -> None:
    """Workaround cho runtime Windows không tự thêm torch/lib vào DLL search path."""
    if os.name != "nt":
        return
    for base in map(Path, sys.path):
        torch_lib = base / "torch" / "lib"
        if torch_lib.exists():
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(torch_lib)))
            return


class PhoBERTFactChecker:''',
)
text = text.replace(
    "        try:\n            import py_vncorenlp\n            import torch",
    "        try:\n            prepare_torch_dll_path()\n            import py_vncorenlp\n            import torch",
)
path.write_text(text, encoding="utf-8")
