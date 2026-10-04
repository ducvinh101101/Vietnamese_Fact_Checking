"""Guards for inputs that are instructions rather than factual claims."""

from __future__ import annotations

import re


_INSTRUCTION_PATTERNS = (
    re.compile(r"\b(ignore|bypass)\b.{0,80}\b(instruction|instructions|previous)\b", re.IGNORECASE),
    re.compile(r"\b(system|assistant)\s*:\s*", re.IGNORECASE),
    re.compile(r"\b(output|conclude|label)\b.{0,50}\b(supported|refuted|nei)\b", re.IGNORECASE),
    re.compile(r"\bbỏ\s+qua\b.{0,80}\b(hướng\s+dẫn|dữ\s+liệu|đối\s+chiếu)\b", re.IGNORECASE),
    re.compile(r"\b(kết\s+luận|gán\s+nhãn)\b.{0,50}\b(supported|refuted|nei)\b", re.IGNORECASE),
)


def is_instruction_like_claim(text: str) -> bool:
    """Return True for prompt-injection-like directives, not ordinary fact claims.

    This is deliberately narrow: it blocks requests to override the verification
    process, rather than treating words such as ``SUPPORTED`` as unsafe by themselves.
    """
    return any(pattern.search(text) is not None for pattern in _INSTRUCTION_PATTERNS)
