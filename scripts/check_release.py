"""Kiểm tra bản phát hành có chạy được trên máy này không (C7 / W6-01) — KHÔNG cần mạng.

In một bảng kiểm ✓/✗ cho: phiên bản Python, thư viện, config, checkpoint verifier,
VnCoreNLP + Java, kho bằng chứng (đối chiếu SHA-256 với manifest), cấu hình web,
API key web (chỉ báo có/không, không in giá trị) và các file số liệu dùng trong báo cáo.

    py -3.13 scripts/check_release.py
    py -3.13 scripts/check_release.py --smoke    # nạp PhoBERT thật và chạy 1 claim (chậm)

Mã thoát 0 khi mọi mục BẮT BUỘC đạt; mục tùy chọn (web key, torch) chỉ cảnh báo.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REQUIRED_MODEL_FILES = ("config.json", "model.safetensors", "vocab.txt", "bpe.codes", "tokenizer_config.json")
REPORT_METRICS = (
    "outputs/metrics/w4_02_local_end_to_end_test.json",
    "outputs/metrics/final_local_end_to_end_test.json",
    "outputs/metrics/final_vs_baselines_test.json",
    "outputs/metrics/rt_v2_balanced_e2e_dev.json",
)


class Checklist:
    def __init__(self) -> None:
        self.failed_required = 0

    def item(self, ok: bool, label: str, detail: str = "", required: bool = True) -> bool:
        mark = "✓" if ok else ("✗" if required else "!")
        print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))
        if required and not ok:
            self.failed_required += 1
        return ok


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smoke", action="store_true", help="Nạp verifier theo config và chạy 1 claim mẫu")
    args = parser.parse_args()
    check = Checklist()

    print("1. Môi trường")
    check.item(sys.version_info >= (3, 11), "Python >= 3.11", sys.version.split()[0])
    for module in ("yaml", "rank_bm25", "pandas", "sklearn", "streamlit", "pytest"):
        try:
            importlib.import_module(module)
            check.item(True, f"thư viện {module}")
        except ImportError as error:
            check.item(False, f"thư viện {module}", f"{error} → pip install -r requirements.txt")
    for module in ("torch", "transformers", "py_vncorenlp"):
        try:
            importlib.import_module(module)
            check.item(True, f"thư viện {module} (cho PhoBERT)")
        except Exception as error:  # noqa: BLE001 - torch có thể bị Windows Application Control chặn
            check.item(False, f"thư viện {module} (cho PhoBERT)",
                       f"{type(error).__name__}: {str(error)[:120]} — giao diện sẽ chạy chế độ demo rule-based",
                       required=False)

    print("2. Cấu hình")
    from src.runtime_config import ConfigValidationError, load_runtime_config
    try:
        config = load_runtime_config(ROOT / "configs" / "config.yaml")
        check.item(True, "configs/config.yaml hợp lệ")
    except ConfigValidationError as error:
        check.item(False, "configs/config.yaml hợp lệ", str(error))
        return 1
    v = config["verification"]
    print(f"     engine={v['engine']} · model={v['model_path']} · evidence_view={v.get('evidence_view', 'passage')}"
          f" · minimal_pair={v.get('minimal_pair', True)} · guard={v.get('guard', False)}")

    print("3. Mô hình")
    if v["engine"] == "phobert":
        model_dir = ROOT / v["model_path"]
        missing = [name for name in REQUIRED_MODEL_FILES if not (model_dir / name).exists()]
        check.item(not missing, f"checkpoint {v['model_path']}",
                   "đủ file" if not missing else f"thiếu {missing} (tải từ Kaggle output RT-V2, xem docs/REPRODUCIBILITY_BASELINE.md)")
        segmenter = ROOT / v["vncorenlp_dir"]
        jar = list(segmenter.glob("VnCoreNLP-*.jar"))
        wseg = segmenter / "models" / "wordsegmenter" / "wordsegmenter.rdr"
        check.item(bool(jar) and wseg.exists(), f"VnCoreNLP tại {v['vncorenlp_dir']}",
                   "có jar + wordsegmenter" if jar and wseg.exists() else "chạy scripts/download_vncorenlp_windows.py")
        java = shutil.which("java")
        portable = ROOT / "tools" / "java17"
        if java is None and portable.exists():
            java = next(portable.glob("**/bin/java*"), None)
        check.item(bool(java) or bool(os.environ.get("JAVA_HOME")), "Java cho VnCoreNLP",
                   str(java or os.environ.get("JAVA_HOME")) if (java or os.environ.get("JAVA_HOME"))
                   else "chạy scripts/download_portable_java.py")

    print("4. Dữ liệu")
    corpus = ROOT / config["paths"]["evidence_path"]
    check.item(corpus.exists(), f"kho bằng chứng {config['paths']['evidence_path']}",
               f"{corpus.stat().st_size // 1024} KB" if corpus.exists() else "thiếu")
    manifest_path = ROOT / "data" / "evidence" / "vifactcheck_passages_v2_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        v2 = ROOT / "data" / "evidence" / "vifactcheck_passages_v2.jsonl"
        if v2.exists():
            raw = v2.read_bytes()
            ok = sha256(v2) == manifest["corpus_sha256"]
            hint = ""
            if not ok and hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == manifest["corpus_sha256"]:
                hint = "khác chỉ do CRLF (Git autocrlf) → git config core.autocrlf false; xóa file; git checkout -- data/evidence"
            check.item(ok, "corpus v2 khớp SHA-256 manifest", hint or ("khớp" if ok else "nội dung đã đổi"))
        policy = ROOT / "configs" / "evidence_source_policy.yaml"
        ok = sha256(policy) == manifest["source_policy_sha256"]
        check.item(ok, "evidence_source_policy.yaml khớp manifest",
                   "khớp" if ok else "có thể do CRLF — xem .gitattributes")
    for split in ("dev", "test"):
        path = ROOT / "data" / "processed" / "vifactcheck_group_split" / f"{split}.parquet"
        check.item(path.exists(), f"split {split}", "" if path.exists() else "thiếu")

    print("5. Web (tùy chọn)")
    from src.system_builder import load_dotenv
    load_dotenv(ROOT / ".env")
    check.item(bool(os.environ.get("TAVILY_API_KEY")), "TAVILY_API_KEY",
               "có (không in giá trị)" if os.environ.get("TAVILY_API_KEY")
               else "chưa đặt — chế độ web sẽ chạy chỉ với kho local", required=False)

    print("6. Số liệu báo cáo")
    for rel in REPORT_METRICS:
        path = ROOT / rel
        detail = ""
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            f1 = data.get("classification", {}).get("macro_f1")
            detail = f"Macro-F1 {100 * f1:.2f}%" if isinstance(f1, (int, float)) else "có"
        check.item(path.exists(), rel, detail or "thiếu", required=rel != REPORT_METRICS[2])

    if args.smoke:
        print("7. Chạy thử verifier")
        from src.system_builder import SystemOptions, build_system
        system = build_system(SystemOptions(mode="local"), config=config, root=ROOT)
        response = system.check("Hà Nội là thủ đô của Việt Nam")
        engine = "rule-based (fallback)" if system.fallback_reason else v["engine"]
        check.item(True, f"pipeline chạy được với {engine}",
                   f"verdict {response['verdict']['label']}, {response['retrieval']['retrieved_count']} bằng chứng")

    print("\nKết luận:", "SẴN SÀNG" if check.failed_required == 0 else f"THIẾU {check.failed_required} mục bắt buộc")
    return 0 if check.failed_required == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
