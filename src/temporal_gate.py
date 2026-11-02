"""Neo thời gian (temporal gating) cho claim thời sự.

Vấn đề: với claim cần dữ liệu MỚI ("giá xăng chiều nay", "tỷ giá hôm nay"),
retrieval vẫn có thể trả bài cũ khớp từ khóa (vd bài 2023) rồi verifier SUPPORTED
dựa trên con số đã lỗi thời. Làm giàu truy vấn (query_enrichment) giúp *tìm* bài
mới nhưng KHÔNG đảm bảo loại bài cũ khi trích dẫn.

Giải pháp chuẩn: sau khi đã có ``published_at`` thật trên bằng chứng (web lấy từ
trang, local v2 lấy từ metadata), với claim thời sự ta LOẠI bằng chứng quá cũ so
với ngày tham chiếu. Nếu không còn bằng chứng đủ mới -> trả rỗng -> pipeline kết
luận NOT_ENOUGH_INFO, thay vì SUPPORTED bằng một bài cũ.

Nguyên tắc:
- Chỉ kích hoạt cho claim thời sự (``is_time_sensitive``). Claim phi thời sự
  (lịch sử, định nghĩa) đi qua nguyên vẹn — bài cũ vẫn hợp lệ.
- Bằng chứng KHÔNG rõ ngày đăng bị loại cho claim thời sự (mặc định), vì không
  chứng minh được là mới. Có thể nới bằng ``drop_unknown_dates=False``.
- Không bịa dữ liệu: nếu nguồn không có bài mới, kết quả là NEI — đúng, vì ta
  thật sự chưa đủ bằng chứng tươi để kết luận.
- Chỉ LỌC, không đổi thứ hạng: giữ nguyên thứ tự điểm của retriever bên trong.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from src.contracts import Retriever
from src.query_enrichment import recency_class, window_start
from src.schemas import RetrievedEvidence

# Lệch múi giờ: bài đăng 'ngày mai' theo UTC vẫn là hôm nay ở VN; chỉ loại khi vượt hẳn.
FUTURE_TOLERANCE_DAYS = 1


def _published_date(value: str | None) -> date | None:
    """Đọc phần NGÀY từ published_at ISO; trả None nếu thiếu/không hợp lệ."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date()
    except ValueError:
        return None


class TemporalGateRetriever:
    """Bọc một retriever: với claim thời sự, loại bằng chứng cũ hơn cửa sổ cho phép.

    ``inner`` phải tuân contract ``search(claim, top_k)`` (thường là FusionRetriever).
    Gate lấy dư ứng viên (``candidate_k``) rồi lọc theo ngày, trả tối đa ``top_k``.
    """

    def __init__(self, inner: Retriever, as_of: date | None = None,
                 window_days: int = 30, window_today: int | None = None,
                 window_current: int | None = None, candidate_k: int = 20,
                 drop_unknown_dates: bool = True, enabled: bool = True) -> None:
        if window_days < 0:
            raise ValueError("window_days không được âm")
        if candidate_k < 1:
            raise ValueError("candidate_k phải lớn hơn 0")
        # Cửa sổ phân tầng theo loại mốc. Nếu không chỉ định, dùng window_days cho cả
        # hai (giữ tương thích cũ). "today" hẹp (giá xăng), "current" rộng (tổng thống).
        self.window_days = window_days
        self.window_today = window_today if window_today is not None else window_days
        self.window_current = window_current if window_current is not None else window_days
        if self.window_today < 0 or self.window_current < 0:
            raise ValueError("cửa sổ không được âm")
        self.inner = inner
        self.as_of = as_of
        self.candidate_k = candidate_k
        self.drop_unknown_dates = drop_unknown_dates
        self.enabled = enabled
        # Để runner/giải thích biết gate đã chạy ra sao.
        self.last_applied = False
        self.last_cutoff: date | None = None
        self.last_class: str | None = None
        self.last_window: int | None = None
        self.last_dropped = 0          # tổng số bị loại
        self.last_dropped_stale = 0    # có ngày nhưng quá cũ
        self.last_dropped_undated = 0  # không rõ ngày đăng
        self.last_dropped_future = 0   # đăng SAU ngày tham chiếu (rò rỉ tương lai)
        self.last_kept = 0
        # Danh sách (lý do, RetrievedEvidence) bị loại, để runner in chẩn đoán.
        self.last_dropped_items: list[tuple[str, RetrievedEvidence]] = []

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        self.last_applied = False
        self.last_cutoff = None
        self.last_class = None
        self.last_window = None
        self.last_dropped = 0
        self.last_dropped_stale = 0
        self.last_dropped_undated = 0
        self.last_dropped_future = 0
        self.last_kept = 0
        self.last_dropped_items = []

        # Claim phi thời sự hoặc gate tắt: không can thiệp.
        cls = recency_class(claim)
        if not self.enabled or cls is None:
            return self.inner.search(claim, top_k)

        # Chọn cửa sổ theo loại mốc: today hẹp, current rộng.
        window = self.window_today if cls == "today" else self.window_current
        reference = self.as_of or datetime.now().date()
        cutoff = window_start(claim, reference, window)
        self.last_applied = True
        self.last_cutoff = cutoff
        self.last_class = cls
        self.last_window = window

        candidates = self.inner.search(claim, max(top_k, self.candidate_k))
        kept: list[RetrievedEvidence] = []
        for item in candidates:
            published = _published_date(item.evidence.published_at)
            if published is None:
                if self.drop_unknown_dates:
                    self.last_dropped_undated += 1
                    self.last_dropped_items.append(("không rõ ngày", item))
                    continue
                kept.append(item)
                continue
            if published > reference + timedelta(days=FUTURE_TOLERANCE_DAYS):
                self.last_dropped_future += 1
                self.last_dropped_items.append(("sau ngày tham chiếu", item))
                continue
            if published < cutoff:
                self.last_dropped_stale += 1
                self.last_dropped_items.append(("quá cũ", item))
                continue
            kept.append(item)
        self.last_dropped = self.last_dropped_stale + self.last_dropped_undated + self.last_dropped_future
        self.last_kept = len(kept)
        # Giữ nguyên thứ tự điểm của retriever bên trong (đã giảm dần).
        return kept[:top_k]
