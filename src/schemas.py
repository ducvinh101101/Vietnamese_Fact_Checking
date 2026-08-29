from dataclasses import dataclass
from typing import Literal


Label = Literal["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


@dataclass(frozen=True)
class Evidence:
    document_id: str
    passage_id: str
    content: str
    source: str = "Không rõ nguồn"
    url: str = ""


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
