"""W4-06: chấm điểm rủi ro nội dung cấp bài — tách biệt hoàn toàn với verdict.

Điểm rủi ro là tín hiệu văn phong/nguồn từ E9 (content-only). Nó KHÔNG phải bằng
chứng, KHÔNG tham gia quyết định SUPPORTED/REFUTED/NEI, và không được diễn giải
như xác suất một bài là tin giả. Module này chỉ đọc title + body và trả một
``ContentRiskAssessment`` để hiển thị RIÊNG, kèm cảnh báo khi nguồn nằm ngoài
phân bố huấn luyện (vì mỗi domain VFND chỉ gắn một nhãn).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

import joblib

RiskBand = Literal["thấp", "trung bình", "cao"]

_DISCLAIMER = (
    "Tín hiệu văn phong/nguồn, KHÔNG phải bằng chứng và không quyết định nhãn "
    "đúng/sai. Không diễn giải như xác suất tin giả."
)


@dataclass(frozen=True)
class ContentRiskAssessment:
    risk_score: float
    band: RiskBand
    out_of_distribution_source: bool
    disclaimer: str = _DISCLAIMER


def _content_text(title: str, body: str) -> str:
    return f"[TITLE] {title or ''} [BODY] {body or ''}"


class ContentRiskScorer:
    """Nạp model E9 đã fit và chấm rủi ro cho một bài viết.

    Nếu không có model, dùng ``ContentRiskScorer(None)`` để tắt hẳn nhánh này;
    khi đó ``score`` trả ``None`` và UI không hiển thị điểm — đúng bằng cách nhánh
    verdict vẫn chạy độc lập.
    """

    def __init__(self, model=None, band_edges=(0.34, 0.67), band_names=("thấp", "trung bình", "cao"),
                 training_source_domains: frozenset[str] = frozenset()) -> None:
        if not (0 <= band_edges[0] <= band_edges[1] <= 1):
            raise ValueError("band_edges phải tăng dần trong [0, 1]")
        self.model = model
        self.band_edges = tuple(band_edges)
        self.band_names = tuple(band_names)
        self.training_source_domains = frozenset(training_source_domains)

    @classmethod
    def load(cls, model_dir: str | Path) -> "ContentRiskScorer":
        directory = Path(model_dir)
        model = joblib.load(directory / "model.joblib")
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        return cls(
            model=model,
            band_edges=tuple(metadata.get("band_edges", (0.34, 0.67))),
            band_names=tuple(metadata.get("band_names", ("thấp", "trung bình", "cao"))),
            training_source_domains=frozenset(metadata.get("training_source_domains", [])),
        )

    @property
    def enabled(self) -> bool:
        return self.model is not None

    def _band(self, score: float) -> RiskBand:
        low, high = self.band_edges
        if score < low:
            return self.band_names[0]  # type: ignore[return-value]
        if score < high:
            return self.band_names[1]  # type: ignore[return-value]
        return self.band_names[2]  # type: ignore[return-value]

    def score(self, title: str, body: str, source_domain: str | None = None) -> ContentRiskAssessment | None:
        """Trả đánh giá rủi ro, hoặc ``None`` nếu nhánh content-risk bị tắt."""
        if self.model is None:
            return None
        probability = float(self.model.predict_proba([_content_text(title, body)])[0][1])
        out_of_distribution = bool(
            self.training_source_domains
            and source_domain is not None
            and source_domain not in self.training_source_domains
        )
        return ContentRiskAssessment(
            risk_score=round(probability, 4),
            band=self._band(probability),
            out_of_distribution_source=out_of_distribution,
        )
