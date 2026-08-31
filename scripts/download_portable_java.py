"""Download a project-local Java 17 runtime for VnCoreNLP on Windows."""
from pathlib import Path
from zipfile import ZipFile

import requests


URL = (
    "https://github.com/adoptium/temurin17-binaries/releases/download/"
    "jdk-17.0.20.1%2B1/OpenJDK17U-jdk_x64_windows_hotspot_17.0.20.1_1.zip"
)


def main() -> None:
    root = Path("tools/java17")
    executable = next(root.glob("**/bin/java.exe"), None) if root.exists() else None
    if executable:
        print(f"Exists: {executable}")
        return

    root.mkdir(parents=True, exist_ok=True)
    archive = root / "temurin17.zip"
    with requests.get(URL, stream=True, timeout=180) as response:
        response.raise_for_status()
        with archive.open("wb") as stream:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    stream.write(chunk)
    with ZipFile(archive) as zipped:
        zipped.extractall(root)
    archive.unlink()
    executable = next(root.glob("**/bin/java.exe"), None)
    if not executable:
        raise RuntimeError("Java executable was not found after extraction.")
    print(f"Ready: {executable}")


if __name__ == "__main__":
    main()
