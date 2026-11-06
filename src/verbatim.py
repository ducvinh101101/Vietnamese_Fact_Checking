"""Exact, complete sentence spans; no bag-of-words entailment shortcuts."""
import re
import unicodedata

from src.evidence_focus import split_sentences


def _tokens(text: str) -> list[str]:
    # Preserve values, units and all words, including negation and attribution.
    return re.findall(r'\d+(?:[.,]\d+)*|\w+|[%°]', unicodedata.normalize('NFC', text).casefold())


def verbatim_span(claim: str, passage: str) -> str | None:
    """Return only a full sentence or consecutive complete sentences matching claim.

    Reject embedded substrings: 'X tăng giá' is not supported by 'Tin giả rằng X
    tăng giá'. No dropping context, changing numbers, reordering or paraphrasing.
    """
    wanted = _tokens(claim)
    if len(wanted) < 6:
        return None
    if _tokens(passage) == wanted:
        return passage.strip()
    sentences = split_sentences(passage)
    for start in range(len(sentences)):
        tokens: list[str] = []
        for end in range(start, len(sentences)):
            tokens.extend(_tokens(sentences[end]))
            if len(tokens) > len(wanted):
                break
            if tokens == wanted:
                return ' '.join(sentences[start:end + 1])
    return None
