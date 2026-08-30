"""Áp dụng loader ZIP tự động cho script Kaggle."""

from pathlib import Path


path = Path(__file__).resolve().parents[1] / "kaggle" / "train_phobert_kaggle.py"
text = path.read_text(encoding="utf-8")
text = text.replace("import os\n", "import os\nimport zipfile\n")
text = text.replace(
    '''def resolve_data_file(name: str) -> Path:
    matches = list(INPUT_DIR.rglob(f"{name}.parquet"))
    if not matches:
        raise FileNotFoundError(f"Không tìm thấy {name}.parquet bên dưới {INPUT_DIR}")
    return matches[0]
''',
    '''def prepare_input_dir() -> Path:
    """Dùng parquet trực tiếp hoặc tự giải nén ZIP upload lên Kaggle."""
    if list(INPUT_DIR.rglob("train.parquet")):
        return INPUT_DIR
    archives = list(INPUT_DIR.rglob("*.zip"))
    if not archives:
        raise FileNotFoundError(f"Không tìm thấy parquet hoặc ZIP dữ liệu bên dưới {INPUT_DIR}")
    extract_dir = WORK_DIR / "input_data"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archives[0]) as archive:
        archive.extractall(extract_dir)
    return extract_dir


def resolve_data_file(data_dir: Path, name: str) -> Path:
    matches = list(data_dir.rglob(f"{name}.parquet"))
    if not matches:
        raise FileNotFoundError(f"Không tìm thấy {name}.parquet bên dưới {data_dir}")
    return matches[0]
''',
)
text = text.replace(
    'frames = {name: pd.read_parquet(resolve_data_file(name)) for name in ("train", "dev", "test")}',
    'data_dir = prepare_input_dir()\n    frames = {name: pd.read_parquet(resolve_data_file(data_dir, name)) for name in ("train", "dev", "test")}',
)
path.write_text(text, encoding="utf-8")

doc = Path(__file__).resolve().parents[1] / "docs" / "KAGGLE_PHOBERT_E2.md"
text = doc.read_text(encoding="utf-8")
text = text.replace(
    "ZIP chứa ba tệp `train.parquet`, `dev.parquet`, `test.parquet`. Đây là split chính thức chống rò rỉ theo URL; không dùng official split để chọn model.",
    "ZIP chứa ba tệp `train.parquet`, `dev.parquet`, `test.parquet`. Script tự giải nén ZIP này vào `/kaggle/working` khi cần. Đây là split chính thức chống rò rỉ theo URL; không dùng official split để chọn model.",
)
doc.write_text(text, encoding="utf-8")
