"""Chèn mốc thời gian vào TRUY VẤN cho claim thời sự, trước khi retrieval.

Claim kiểu "giá xăng tăng chiều nay" chứa mốc tương đối ("chiều nay") nên retrieval
dễ khớp bài cũ. Module này phát hiện biểu thức thời gian tương đối rồi thêm ngày
hiện tại vào **truy vấn gửi cho retriever**, giúp ưu tiên bài mới (nhất là web).

Nguyên tắc quan trọng — chỉ sửa truy vấn, KHÔNG sửa claim gửi cho verifier:
- Verifier vẫn chấm claim gốc với passage, để không bóp méo quan hệ entailment.
- Chỉ dùng cho nhánh cần tươi mới (web). Corpus local là tĩnh/lịch sử, thêm ngày
  vào BM25 thường làm giảm khớp, nên KHÔNG bọc local bằng lớp này.
- Thêm ngày KHÔNG tạo ra dữ liệu không tồn tại: nếu nguồn không có bài hôm nay thì
  vẫn không có. Đây là tín hiệu ưu tiên, không phải nguồn real-time.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import re

from src.contracts import Retriever
from src.schemas import RetrievedEvidence

# Mốc thời gian tương đối, chia 2 LOẠI vì nhịp thay đổi khác nhau:
# - "today": sự kiện theo NGÀY, dữ liệu cũ nhanh (giá xăng chiều nay) -> cửa sổ hẹp.
# - "current": trạng thái HIỆN TẠI đổi chậm (tổng thống hiện nay) -> cửa sổ rộng.
# Cố ý KHÔNG gồm "đang" vì quá phổ biến, dễ báo nhầm.
_TODAY_MARKERS = (
    "hôm nay", "chiều nay", "sáng nay", "trưa nay", "tối nay", "đêm nay",
    "hôm qua", "ngày mai", "sáng mai", "chiều mai", "tối mai",
)
_CURRENT_MARKERS = (
    "hiện nay", "hiện tại", "bây giờ", "mới nhất", "gần đây", "mới đây",
    "vừa qua", "vừa mới", "tuần này", "tháng này", "năm nay",
    "sắp tới", "tới đây", "đương nhiệm",
)
# Chức danh có nhiệm kỳ là một dạng claim "hiện tại" ngầm. Ví dụ "Donald Trump
# là tổng thống Mỹ" không có từ "hiện nay", nhưng nếu không neo thời gian thì
# retriever có thể dùng bài viết về một nhiệm kỳ cũ để kết luận sai ở hiện tại.
# Danh sách này cố ý chỉ gồm vai trò thay đổi theo thời gian, không gồm các nghề
# nghiệp chung như "bác sĩ" hoặc "ca sĩ".
_CURRENT_ROLE_MARKERS = (
    "tổng thống", "thủ tướng", "chủ tịch nước", "bộ trưởng", "thống đốc",
    "ceo", "giám đốc điều hành", "quốc vương", "thị trưởng",
)
_HISTORICAL_ROLE_MARKERS = ("cựu ", "từng ", "đã từng", "trước đây", "sẽ ", "dự kiến")
_RELATIVE_MARKERS = _TODAY_MARKERS + _CURRENT_MARKERS
# Nếu claim đã có ngày tuyệt đối (13/3, 13-3-2023, ngày 5 tháng 10...) thì KHÔNG
# cần chèn — nó đã có mốc.
# Năm cụ thể ("năm 2020") và tháng/năm ("tháng 3/2023", "3/2023") cũng là mốc tuyệt đối.
_ABSOLUTE_DATE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b|ngày\s+\d{1,2}\b"
    r"|\bnăm\s+(?:19|20)\d{2}\b"
    r"|\btháng\s+\d{1,2}\s*(?:[/-]|năm\s+)\s*(?:19|20)\d{2}\b"
    r"|\b\d{1,2}[/-](?:19|20)\d{2}\b"
)


def recency_class(claim: str) -> str | None:
    """Trả 'today' | 'current' | None theo loại mốc thời gian của claim.

    None nếu claim không thời sự (hoặc đã có ngày tuyệt đối). 'today' ưu tiên hơn
    'current' khi có cả hai (mốc chặt hơn thì an toàn hơn). Chức danh nhiệm kỳ
    không có dấu hiệu quá khứ cũng được coi là 'current' ngầm."""
    text = claim.casefold()
    if _ABSOLUTE_DATE.search(text):
        return None
    if any(marker in text for marker in _TODAY_MARKERS):
        return "today"
    if any(marker in text for marker in _CURRENT_MARKERS):
        return "current"
    if (
        any(role in text for role in _CURRENT_ROLE_MARKERS)
        and not any(marker in text for marker in _HISTORICAL_ROLE_MARKERS)
    ):
        return "current"
    return None


def is_time_sensitive(claim: str) -> bool:
    """True nếu claim có mốc tương đối mà chưa có ngày tuyệt đối."""
    return recency_class(claim) is not None


def enrich_query(claim: str, as_of: date | None = None) -> tuple[str, bool]:
    """Trả (truy vấn, đã_chèn). Chèn 'ngày dd/mm/yyyy' nếu claim thời sự."""
    if not is_time_sensitive(claim):
        return claim, False
    day = as_of or datetime.now().date()
    return f"{claim} ngày {day:%d/%m/%Y}", True


class TimeAwareRetriever:
    """Bọc một retriever (thường là web) để chèn ngày vào truy vấn tìm kiếm.

    Evidence trả về giữ nguyên; chỉ truy vấn được làm giàu. Không dùng cho corpus
    local tĩnh.
    """

    def __init__(self, inner: Retriever, as_of: date | None = None, enabled: bool = True,
                 window_today: int = 10, window_current: int = 365) -> None:
        if window_today < 0 or window_current < 0:
            raise ValueError("cửa sổ tìm kiếm web không được âm")
        self.inner = inner
        self.as_of = as_of
        self.enabled = enabled
        self.window_today = window_today
        self.window_current = window_current
        self.last_enriched_query: str | None = None

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        query, enriched = (enrich_query(claim, self.as_of) if self.enabled else (claim, False))
        self.last_enriched_query = query if enriched else None
        # WebRetriever exposes this opt-in capability.  Keep the Retriever
        # protocol unchanged so non-web retrievers remain compatible.
        search_time_window = getattr(self.inner, "search_time_window", None)
        recency = recency_class(claim)
        if enriched and recency is not None and callable(search_time_window):
            reference = self.as_of or datetime.now().date()
            window = self.window_today if recency == "today" else self.window_current
            return search_time_window(
                query,
                top_k,
                reference - timedelta(days=window),
                reference,
                language="vi",
            )
        return self.inner.search(query, top_k)
