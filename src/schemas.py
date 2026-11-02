from dataclasses import dataclass
from typing import Literal


Label = Literal["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]
SourceType = Literal["government", "international_org", "news", "fact_check", "academic", "other", "unknown"]


@dataclass(frozen=True)
class Article:
    """Canonical source article, as specified in docs/DATA_CONTRACT.md."""

    article_id: str
    title: str
    body: str
    url: str
    retrieved_at: str | None
    source: str = "Không rõ nguồn"
    published_at: str | None = None
    source_type: SourceType = "unknown"
    authority_score: float | None = None


@dataclass(frozen=True)
class Claim:
    """An atomic claim linked to one source article."""

    claim_id: str
    article_id: str
    text: str
    published_at: str | None = None


@dataclass(frozen=True)
class Evidence:
    document_id: str
    passage_id: str
    content: str
    source: str = "Không rõ nguồn"
    url: str = ""
    # Preserve the resolved hostname explicitly.  A web citation must not rely
    # on consumers parsing it back out of the URL.
    domain: str = ""
    article_id: str = ""
    title: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    source_type: SourceType = "unknown"
    authority_score: float | None = None
    published_at_source: str | None = None


@dataclass(frozen=True)
class RetrievedEvidence:
    evidence: Evidence
    score: float


@dataclass(frozen=True)
class VerificationResult:
    label: Label
    confidence: float
    evidence_ids: list[str]
    explanation: str
