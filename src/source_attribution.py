"""Pipeline kiểm tra nguồn: claim → có tìm được nguồn ngoài thực tế hay không.

Định nghĩa bài toán (thay cho phân loại thật/giả):

* ``SOURCE_FOUND`` – có ít nhất một đoạn từ nguồn được truy xuất nói đúng nội
  dung claim (liên quan đủ cao, verifier xác nhận, không lệch số/ngày);
* ``SOURCE_CONFLICT`` – có nguồn nói về cùng sự việc nhưng lệch chi tiết
  (số liệu/ngày tháng khác, hoặc verifier đánh giá mâu thuẫn);
* ``NO_SOURCE`` – không có đoạn nào vượt ngưỡng liên quan/xác nhận.

Các model đã train được tái sử dụng: verifier PhoBERT RT-V2 (3 lớp
SUPPORTED/REFUTED/NEI) chấm từng cặp claim–đoạn sau khi rerank; ánh xạ
SUPPORTED→xác nhận, REFUTED→mâu thuẫn, NEI→không đủ. Reranker có thể là
PhoBERT nhị phân do nhóm fine-tune hoặc cross-encoder đa ngữ.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import isfinite
from typing import Protocol, Sequence
from urllib.parse import urlparse

from src.preprocessing import normalize_text
from src.schemas import Evidence, RetrievedEvidence
from src.source_reranker import LexicalSourceScorer, RelevanceScorer, dates_compatible, entity_present, rerank
from src.vi_text import ClaimFacets, approximate_numbers, extract_dates, extract_numbers, fold, number_matches


SCHEMA_VERSION = "source-attribution/v1"
SOURCE_LABELS = ("SOURCE_FOUND", "SOURCE_CONFLICT", "NO_SOURCE")
LABEL_TEXT = {
    "SOURCE_FOUND": "Có nguồn xác nhận",
    "SOURCE_CONFLICT": "Có nguồn liên quan nhưng lệch chi tiết",
    "NO_SOURCE": "Không tìm thấy nguồn",
}
# Map nhãn cũ (ViFactCheck/RT-V2) sang nhãn mới – dùng cho đánh giá và giải thích.
LEGACY_TO_SOURCE = {"SUPPORTED": "SOURCE_FOUND", "REFUTED": "SOURCE_CONFLICT", "NOT_ENOUGH_INFO": "NO_SOURCE"}


def is_web_retriever(retriever: object) -> bool:
    """WebRetriever thật hoặc lớp bọc nó (ghi/phát lại kết quả web khi đánh giá) – khai báo ``is_web_retriever``."""
    return type(retriever).__name__ == "WebRetriever" or bool(getattr(retriever, "is_web_retriever", False))


def is_web_evidence(evidence: object) -> bool:
    """Đoạn lấy từ WebRetriever có ``document_id`` / ``passage_id`` bắt đầu bằng ``web-``."""
    doc_id = str(getattr(evidence, "document_id", "") or "")
    pid = str(getattr(evidence, "passage_id", "") or "")
    return doc_id.startswith("web-") or pid.startswith("web-")


class PairVerifier(Protocol):
    """Verifier trả xác suất [SUPPORTED, REFUTED, NEI] cho từng đoạn."""

    def predict_probabilities_batch(self, claim: str, evidences: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class FacetCheck:
    """Kết quả so khớp chi tiết cứng giữa claim và một đoạn văn."""

    matched: list[str] = field(default_factory=list)
    conflicting: list[str] = field(default_factory=list)  # có giá trị cùng loại nhưng khác
    missing: list[str] = field(default_factory=list)      # đoạn không nhắc tới

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflicting)


def _date_kind(date: str) -> tuple[int, bool]:
    """Loại ngày để so lệch: số phần và phần cuối có phải năm không – "11" (tháng) ≠ "2026" (năm),
    "21/11" (ngày/tháng) ≠ "11/2026" (tháng/năm)."""
    parts = date.split("/")
    return len(parts), len(parts[-1]) == 4


def check_facets(claim: str, passage: str) -> FacetCheck:
    """So số, ngày, tên riêng của claim với đoạn văn.

    Số/ngày của claim không có trong đoạn được coi là **lệch** nếu đoạn có
    số/ngày khác cùng loại (vd. claim 15%, đoạn ghi 12%), ngược lại là
    **thiếu**. Tên riêng thiếu chỉ là "thiếu" – không đủ căn cứ để gọi là lệch.
    """
    facets = ClaimFacets.from_text(claim)
    approximate = approximate_numbers(claim)
    passage_numbers = extract_numbers(passage)
    passage_dates = extract_dates(passage)
    passage_folded = fold(passage)
    matched: list[str] = []
    conflicting: list[str] = []
    missing: list[str] = []
    # Chỉ số "không giải thích được" (không khớp số nào của claim) mới là căn cứ báo lệch: đoạn ghi
    # "người dưới 18 tuổi" không làm "3 luật" của claim thành lệch khi claim cũng nói "18 tuổi".
    unexplained = {value for value in passage_numbers
                   if not any(number_matches(number, {value}, approximate) for number in facets.numbers)}
    percent_in_passage = {value for value in unexplained if value.endswith("%")}
    plain_in_passage = unexplained - percent_in_passage
    for number in sorted(facets.numbers):
        same_kind = percent_in_passage if number.endswith("%") else plain_in_passage
        if number_matches(number, passage_numbers, approximate):  # gồm "hơn/gần/khoảng X" trong khoảng hợp lý
            matched.append(f"số {number}")
        elif same_kind:
            conflicting.append(f"số {number}")
        else:
            missing.append(f"số {number}")
    for date in sorted(facets.dates):
        if dates_compatible(date, passage_dates):
            matched.append(f"thời gian {date}")
        elif any(_date_kind(other) == _date_kind(date) for other in passage_dates):
            conflicting.append(f"thời gian {date}")
        else:
            missing.append(f"thời gian {date}")
    for entity in sorted(facets.entities):
        (matched if entity_present(entity, passage_folded) else missing).append(f"tên riêng {entity}")
    return FacetCheck(matched, conflicting, missing)


@dataclass(frozen=True)
class PassageAssessment:
    item: RetrievedEvidence
    relevance: float
    verifier_probabilities: list[float] | None
    facets: FacetCheck
    status: str  # "supports" | "conflicts" | "related" | "unrelated"


@dataclass(frozen=True)
class SourceAttributionResult:
    label: str
    confidence: float
    explanation: str
    citations: list[PassageAssessment]
    assessed: list[PassageAssessment]
    queries: list[str]
    retrieved_count: int
    # Trạng thái tra web: None = pipeline không có web; "ok"/"no_eligible_passages" = đã tra được;
    # giá trị khác (xem web_retriever.WEB_FAILURE_MESSAGES) = web lỗi, kết quả chỉ dựa trên kho cục bộ.
    web_status: str | None = None

    @property
    def independent_domains(self) -> list[str]:
        domains = []
        for assessment in self.citations:
            domain = assessment.item.evidence.domain or urlparse(assessment.item.evidence.url).hostname or assessment.item.evidence.source
            if domain and domain not in domains:
                domains.append(domain)
        return domains


@dataclass(frozen=True)
class AttributionThresholds:
    """Ngưỡng chọn trên tập dev (``scripts/evaluate_source_attribution.py``)."""

    relevance: float = 0.5           # dưới ngưỡng: đoạn không liên quan
    support: float = 0.5             # P(SUPPORTED) để coi là xác nhận (khi có verifier)
    conflict: float = 0.5            # P(REFUTED) để coi là mâu thuẫn
    lexical_support: float = 0.65    # không có verifier: điểm liên quan để coi là xác nhận


class SourceAttributionPipeline:
    """retrieve (multi-query, local+web) → rerank tuyệt đối → verifier + facet → nhãn nguồn."""

    def __init__(
        self,
        retriever: object,
        scorer: RelevanceScorer | None = None,
        verifier: PairVerifier | None = None,
        thresholds: AttributionThresholds | None = None,
        candidate_k: int = 40,
        assess_k: int = 8,
        max_citations: int = 3,
        require_claim_numbers: bool = False,
        web_thresholds: AttributionThresholds | None = None,
        article_digest: dict | None = None,
    ) -> None:
        if candidate_k < 1 or assess_k < 1 or max_citations < 1:
            raise ValueError("candidate_k, assess_k, max_citations phải lớn hơn 0")
        self.retriever = retriever
        self.scorer = scorer or LexicalSourceScorer()
        self.verifier = verifier
        self.thresholds = thresholds or AttributionThresholds()
        self.web_thresholds = web_thresholds
        # Bản tóm tắt cả bài (src/article_digest.py): None = tắt. Khóa: max_articles, max_sentences, max_chars,
        # min_unit_coverage, scope ("all" | "web").
        self.article_digest = dict(article_digest) if article_digest else None
        self.candidate_k = candidate_k
        self.assess_k = assess_k
        self.max_citations = max_citations
        # Đoạn thiếu một con số của claim → tối đa "related", không "xác nhận" (dev: báo nhầm 5,8% → 5,1%).
        self.require_claim_numbers = require_claim_numbers

    def thresholds_for(self, evidence: object) -> AttributionThresholds:
        """Ngưỡng áp dụng cho một đoạn: dùng ``web_thresholds`` (nếu có) cho đoạn từ web, ngược lại ``thresholds``."""
        if self.web_thresholds is not None and is_web_evidence(evidence):
            return self.web_thresholds
        return self.thresholds

    def _status(self, relevance: float, probabilities: list[float] | None, facets: FacetCheck,
                article_numbers: set[str] | frozenset[str] = frozenset(),
                thresholds: AttributionThresholds | None = None) -> str:
        """``article_numbers``: số của claim đã thấy ở đoạn khác của cùng bài (báo hay tách số ra đoạn khác)."""
        status = self._base_status(relevance, probabilities, facets, thresholds)
        if status == "supports" and self.require_claim_numbers and any(
                m.startswith("số ") and m not in article_numbers for m in facets.missing):
            return "related"
        return status

    def assign_statuses(self, assessed: list[PassageAssessment]) -> list[PassageAssessment]:
        """Gán trạng thái từng đoạn; số của claim được gom theo bài (URL) khi xét ``require_claim_numbers``."""
        numbers_by_article: dict[str, set[str]] = {}
        for a in assessed:
            key = a.item.evidence.url or a.item.evidence.document_id
            numbers_by_article.setdefault(key, set()).update(m for m in a.facets.matched if m.startswith("số "))
        return [replace(a, status=self._status(
            a.relevance, a.verifier_probabilities, a.facets,
            numbers_by_article[a.item.evidence.url or a.item.evidence.document_id],
            self.thresholds_for(a.item.evidence),
        )) for a in assessed]

    def _base_status(self, relevance: float, probabilities: list[float] | None, facets: FacetCheck,
                     thresholds: AttributionThresholds | None = None) -> str:
        t = thresholds or self.thresholds
        if relevance < t.relevance:
            return "unrelated"
        if probabilities is not None:
            supported, refuted = probabilities[0], probabilities[1]
            if refuted >= t.conflict and refuted > supported:
                return "conflicts"
            if facets.has_conflict:
                return "conflicts"
            if supported >= t.support:
                return "supports"
            return "related"
        if facets.has_conflict:
            return "conflicts"
        return "supports" if relevance >= t.lexical_support else "related"

    def run(self, claim: str) -> SourceAttributionResult:
        text = normalize_text(claim)
        if not text:
            raise ValueError("Phát biểu không được để trống")
        from src.query_generation import generate_queries

        queries = [query.text for query in generate_queries(text)]
        candidates = self.retriever.search(text, self.candidate_k)  # type: ignore[attr-defined]
        candidates = [item for item in candidates if isfinite(item.score) and item.evidence.content.strip()]
        reranked = rerank(self.scorer, text, candidates, self.assess_k)
        reranked = self._with_article_digests(text, candidates, reranked)
        # Chỉ chạy verifier trên các đoạn đạt ngưỡng liên quan của nguồn tương ứng (local hoặc web).
        relevant_indices = [
            index for index, item in enumerate(reranked)
            if item.score >= self.thresholds_for(item.evidence).relevance
        ]
        probabilities: list[list[float] | None] = [None] * len(reranked)
        if self.verifier is not None and relevant_indices:
            scored = self.verifier.predict_probabilities_batch(
                text, [reranked[i].evidence.content for i in relevant_indices]
            )
            for index, value in zip(relevant_indices, scored):
                probabilities[index] = [float(v) for v in value]
        assessed = self.assign_statuses([
            PassageAssessment(item, item.score, probabilities[index], check_facets(text, item.evidence.content), "")
            for index, item in enumerate(reranked)
        ])
        result = self._decide(text, assessed, queries, len(candidates))
        return replace(result, web_status=self._web_status())

    def _with_article_digests(self, claim: str, candidates: list[RetrievedEvidence],
                              reranked: list[RetrievedEvidence]) -> list[RetrievedEvidence]:
        """Thêm cho mỗi bài liên quan nhất một đoạn "tóm tắt cả bài" (câu khớp từng ý của claim)."""
        settings = self.article_digest
        if not settings:
            return reranked
        from src.article_digest import build_digest

        web_only = settings.get("scope", "all") == "web"
        lookup = getattr(self.retriever, "article_passages", None)
        first: dict[str, Evidence] = {}
        for item in [*reranked, *candidates]:
            evidence = item.evidence
            key = evidence.document_id or evidence.url
            if key and key not in first and (not web_only or is_web_evidence(evidence)):
                first[key] = evidence
        existing = {" ".join(item.evidence.content.casefold().split()) for item in reranked}
        digests: list[Evidence] = []
        for key, evidence in list(first.items())[: int(settings.get("max_articles", 3))]:
            passages = (lookup(evidence.document_id) if callable(lookup) else None) or [
                item.evidence.content for item in candidates if (item.evidence.document_id or item.evidence.url) == key]
            digest = build_digest(claim, passages, int(settings.get("max_sentences", 4)),
                                  int(settings.get("max_chars", 700)), float(settings.get("min_unit_coverage", 0.4)))
            if digest and " ".join(digest.casefold().split()) not in existing:
                existing.add(" ".join(digest.casefold().split()))
                digests.append(replace(evidence, passage_id=f"{evidence.passage_id.split('-w')[0]}-digest",
                                       content=digest))
        if not digests:
            return reranked
        scores = self.scorer.score(claim, [evidence.content for evidence in digests])
        merged = [*reranked, *(RetrievedEvidence(e, float(score)) for e, score in zip(digests, scores))]
        merged.sort(key=lambda item: (-item.score, item.evidence.passage_id))
        return merged

    def _web_status(self) -> str | None:
        """Đọc trạng thái của retriever web (nếu có) sau lần search vừa rồi."""
        retrievers = getattr(self.retriever, "retrievers", [self.retriever])
        web = [r for r in retrievers if is_web_retriever(r)]
        if not web:
            return None
        errors = getattr(self.retriever, "last_errors", [])
        if any(error.startswith(f"{type(web[0]).__name__}:") for error in errors):
            return "error"  # ngoại lệ ngoài dự kiến đã bị FusedRetriever nuốt
        return str(getattr(web[0], "last_status", "error"))

    def _decide(self, claim: str, assessed: list[PassageAssessment], queries: list[str], retrieved: int) -> SourceAttributionResult:
        supports = [a for a in assessed if a.status == "supports"]
        conflicts = [a for a in assessed if a.status == "conflicts"]
        related = [a for a in assessed if a.status == "related"]

        def strength(assessment: PassageAssessment, index: int) -> float:
            if assessment.verifier_probabilities is None:
                return assessment.relevance
            return assessment.relevance * assessment.verifier_probabilities[index]

        if supports:
            supports.sort(key=lambda a: -strength(a, 0))
            citations = supports[: self.max_citations]
            confidence = strength(citations[0], 0)
            domains = len({a.item.evidence.domain or a.item.evidence.url for a in citations})
            explanation = f"Tìm thấy {len(supports)} đoạn từ {domains} nguồn nói cùng nội dung với phát biểu."
            if conflicts:
                explanation += f" Lưu ý: {len(conflicts)} đoạn khác có chi tiết lệch, nên đọc đối chiếu."
            label = "SOURCE_FOUND"
        elif conflicts:
            conflicts.sort(key=lambda a: -strength(a, 1))
            citations = conflicts[: self.max_citations]
            confidence = citations[0].relevance
            detail = ", ".join(citations[0].facets.conflicting) or "nội dung bị verifier đánh giá mâu thuẫn"
            explanation = f"Có nguồn nói về cùng sự việc nhưng lệch chi tiết ({detail})."
            label = "SOURCE_CONFLICT"
        else:
            citations = []
            best = max((a.relevance for a in assessed), default=0.0)
            confidence = 1 - best
            if related:
                explanation = "Có bài liên quan đến chủ đề nhưng không đoạn nào xác nhận đúng nội dung phát biểu."
            else:
                explanation = "Không tìm thấy đoạn nào đủ liên quan trong các nguồn đã tra cứu."
            label = "NO_SOURCE"
        return SourceAttributionResult(label, round(float(confidence), 4), explanation, citations, assessed, queries, retrieved)

    def run_json(self, claim: str) -> dict[str, object]:
        return build_source_output(self.run(claim))


def _assessment_record(assessment: PassageAssessment) -> dict[str, object]:
    evidence = assessment.item.evidence
    return {
        "passage_id": evidence.passage_id,
        "document_id": evidence.document_id,
        "relevance": round(assessment.relevance, 4),
        "status": assessment.status,
        "verifier_probabilities": (
            dict(zip(("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"), (round(v, 4) for v in assessment.verifier_probabilities)))
            if assessment.verifier_probabilities is not None else None
        ),
        "matched_details": assessment.facets.matched,
        "conflicting_details": assessment.facets.conflicting,
        "missing_details": assessment.facets.missing,
        "source": evidence.source,
        "url": evidence.url,
        "domain": evidence.domain,
        "title": evidence.title,
        "published_at": evidence.published_at,
        "retrieved_at": evidence.retrieved_at,
        "source_type": evidence.source_type,
        "content": evidence.content,
    }


def build_source_output(result: SourceAttributionResult) -> dict[str, object]:
    if result.label not in SOURCE_LABELS:
        raise RuntimeError(f"Nhãn không hợp lệ: {result.label}")
    if result.label == "NO_SOURCE" and result.citations:
        raise RuntimeError("NO_SOURCE không được kèm citation")
    if result.label != "NO_SOURCE" and not result.citations:
        raise RuntimeError("Nhãn có nguồn phải kèm ít nhất một citation")
    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": {
            "label": result.label,
            "label_text": LABEL_TEXT[result.label],
            "confidence": result.confidence,
            "explanation": result.explanation,
            "independent_sources": result.independent_domains,
        },
        "queries": result.queries,
        "retrieval": {
            "retrieved_count": result.retrieved_count,
            "web_status": result.web_status,
            "assessed": [_assessment_record(a) for a in result.assessed],
        },
        "citations": [_assessment_record(a) for a in result.citations],
    }


def legacy_label(label: str) -> str:
    """Ánh xạ nhãn nguồn về nhãn ViFactCheck để so sánh với baseline cũ."""
    return {value: key for key, value in LEGACY_TO_SOURCE.items()}[label]
