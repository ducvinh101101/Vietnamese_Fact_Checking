"""Record the local environment and immutable inputs used for W1-07.

This script does not train or alter models, data, or application code. It writes
an exact dependency lockfile and a manifest with SHA-256 hashes for reproducible
local validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCKFILE = ROOT / "requirements.lock"
MANIFEST = ROOT / "outputs" / "metrics" / "reproducibility_baseline.json"
HASHED_ARTIFACTS = (
    "requirements.txt",
    "requirements.lock",
    "configs/config.yaml",
    "data/manifest.json",
    "data/evidence/sample_evidence.jsonl",
    "data/evidence/vifactcheck_passages.jsonl",
    "models/e2_phobert/best_model/config.json",
    "models/e2_phobert/best_model/model.safetensors",
    "models/e2_phobert/best_model/tokenizer_config.json",
    "models/e2_phobert/best_model/vocab.txt",
    "models/vncorenlp/VnCoreNLP-1.2.jar",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def lock_environment() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"], text=True, capture_output=True, check=True
    )
    packages = sorted(line for line in result.stdout.splitlines() if line)
    LOCKFILE.write_text("\n".join(packages) + "\n", encoding="utf-8", newline="\n")
    return packages


def run_tests() -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True
    )
    return {
        "command": f"{sys.executable} -m pytest -q",
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    packages = lock_environment()
    test_result = run_tests() if args.run_tests else None
    if test_result and test_result["exit_code"] != 0:
        raise RuntimeError(f"pytest thất bại:\n{test_result['stdout']}\n{test_result['stderr']}")

    missing = [relative for relative in HASHED_ARTIFACTS if not (ROOT / relative).is_file()]
    if missing:
        raise FileNotFoundError(f"Thiếu artefact cần hash: {missing}")

    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_revision(),
        "python": sys.version,
        "platform": platform.platform(),
        "dependency_lockfile": LOCKFILE.relative_to(ROOT).as_posix(),
        "dependency_count": len(packages),
        "artifacts": {
            relative: {"sha256": sha256(ROOT / relative), "bytes": (ROOT / relative).stat().st_size}
            for relative in HASHED_ARTIFACTS
        },
        "pytest": test_result,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"lockfile={LOCKFILE.relative_to(ROOT)} packages={len(packages)}")
    print(f"manifest={MANIFEST.relative_to(ROOT)} artifacts={len(HASHED_ARTIFACTS)}")


if __name__ == "__main__":
    main()
