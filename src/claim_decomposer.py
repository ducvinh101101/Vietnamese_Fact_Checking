"""Tách candidate claim bảo toàn nguyên văn từ một :class:`Article`.

Đây là bước tiền xử lý có chủ đích bảo thủ: không dùng LLM, không viết lại nội
dung và không tự gán nhãn đúng/sai. Mỗi câu trần thuật hoặc vế ngăn bởi dấu
chấm phẩy trở thành một claim cần được retrieval/verifier xử lý độc lập.
"""

from __future__ import annotations

from hashlib import sha256
import re

from src.preprocessing import normalize_text
from src.schemas import Article, Claim


SEGMENT_BOUNDARY = re.compile(r"(?<=[.!?…])(?:[\"'\)\]\}]+)?\s+|\s*;\s*")
QUESTION_PREFIXES = ("liệu ", "phải chăng ", "có phải ")


class ClaimDecomposer:
    """Sinh claim có ID ổn định và giữ liên kết về article gốc.

    Việc tách ở mức câu/vế tránh tự suy diễn chủ thể hoặc quan hệ từ văn bản.
    Một câu ghép chưa đủ nguyên tử vẫn được giữ nguyên để bước review sau này
    có thể tách tiếp mà không làm mất ngữ cảnh.
    """

    def __init__(self, min_characters: int = 12) -> None:
        if min_characters < 1:
            raise ValueError("min_characters phải lớn hơn 0")
        self.min_characters = min_characters

    def decompose(self, article: Article) -> list[Claim]:
        """Trả candidate claim theo thứ tự xuất hiện trong article.

        Tiêu đề được dùng khi body rỗng hoặc khi tiêu đề không lặp nguyên văn
        trong body. Câu hỏi bị loại vì chúng không phải khẳng định để verifier
        kiểm chứng. Các claim trùng nguyên văn chỉ được giữ một lần.
        """
        if not article.article_id.strip():
            raise ValueError("article_id không được để trống")

        body = normalize_text(article.body)
        candidates: list[str] = []
        title = normalize_text(article.title)
        if title and title.casefold() not in body.casefold():
            candidates.extend(self._split_segments(title))
        candidates.extend(self._split_segments(body))

        claims: list[Claim] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = normalize_text(candidate)
            canonical = text.casefold()
            if not self._is_assertion(text) or canonical in seen:
                continue
            seen.add(canonical)
            digest = sha256(canonical.encode("utf-8")).hexdigest()[:12]
            claims.append(
                Claim(
                    claim_id=f"{article.article_id}:claim:{digest}",
                    article_id=article.article_id,
                    text=text,
                    published_at=article.published_at,
                )
            )
        return claims

    def _split_segments(self, text: str) -> list[str]:
        if not text:
            return []
        return [segment.strip(" -•\t") for segment in SEGMENT_BOUNDARY.split(text) if segment.strip()]

    def _is_assertion(self, text: str) -> bool:
        if len(text) < self.min_characters:
            return False
        lowered = text.casefold()
        return not text.endswith("?") and not lowered.startswith(QUESTION_PREFIXES)
