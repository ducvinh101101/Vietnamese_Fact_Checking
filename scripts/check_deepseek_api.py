"""Make one DeepSeek verification request with a fixed synthetic example."""

import sys
from pathlib import Path

from src.llm_verifier import LLMVerifier
from src.schemas import Evidence, RetrievedEvidence
from src.system_builder import load_dotenv


def main() -> int:
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    verifier = LLMVerifier(provider="deepseek", timeout=30)
    claim = "Một mét bằng 100 xăng-ti-mét."
    evidence = [RetrievedEvidence(Evidence("demo", "demo-p1", claim), 1.0)]
    result = verifier.verify(claim, evidence)
    if result.status == "error":
        print(result.explanation, file=sys.stderr)
        return 1
    if result.label != "SUPPORTED" or result.evidence_ids != ["demo-p1"]:
        print(f"DeepSeek API đã phản hồi, nhưng ca thử cho kết quả ngoài kỳ vọng ({result.label}).", file=sys.stderr)
        return 1
    print(f"OK: {verifier.model} -> {result.label} ({result.evidence_ids[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
