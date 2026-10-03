"""JSON output contract for the retrieval-to-verdict pipeline.

This module deliberately serializes an already-produced ``VerificationResult``.
It does not change retrieval ranking or the verifier's decision policy.
"""

from __future__ import annotations

from math import isfinite
from urllib.parse import urlparse

from src.schemas import RetrievedEvidence, VerificationResult


SCHEMA_VERSION = "w3-03/v1"


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _evidence_record(item: RetrievedEvidence) -> dict[str, object]:
    evidence = item.evidence
    if not evidence.passage_id:
        raise RuntimeError("Evidence không có passage_id")
    if not isfinite(item.score):
        raise RuntimeError("Điểm evidence phải hữu hạn để xuất JSON")
    return {
        "passage_id": evidence.passage_id,
        "document_id": evidence.document_id,
        "score": item.score,
        "source": evidence.source,
        "url": evidence.url,
        "domain": evidence.domain,
        "title": evidence.title,
        "published_at": evidence.published_at,
        "retrieved_at": evidence.retrieved_at,
        "source_type": evidence.source_type,
        "content": evidence.content,
    }


def build_pipeline_output(
    result: VerificationResult,
    retrieved: list[RetrievedEvidence],
) -> dict[str, object]:
    """Return a JSON-safe, citation-auditable pipeline response.

    Decisive verdicts must point to one or more positively scored retrieved
    passages with an absolute HTTP(S) URL.  A no-evidence/NEI result must not
    manufacture a citation.
    """
    records = [_evidence_record(item) for item in retrieved]
    passage_ids = [str(record["passage_id"]) for record in records]
    if len(passage_ids) != len(set(passage_ids)):
        raise RuntimeError("Retriever trả passage_id trùng lặp; không thể xuất JSON audit được")
    if len(result.evidence_ids) != len(set(result.evidence_ids)):
        raise RuntimeError("Verifier trả citation ID trùng lặp")

    by_id = {str(record["passage_id"]): record for record in records}
    citations: list[dict[str, object]] = []
    for citation_id in result.evidence_ids:
        record = by_id.get(citation_id)
        if record is None:
            raise RuntimeError("Citation ID không thuộc evidence đã truy xuất")
        if float(record["score"]) <= 0:
            raise RuntimeError("Citation không được trỏ tới evidence có điểm retrieval không dương")
        if not _is_http_url(str(record["url"])):
            raise RuntimeError("Citation phải có URL HTTP(S) hợp lệ")
        citations.append(record)

    if result.label == "NOT_ENOUGH_INFO" and citations:
        raise RuntimeError("NOT_ENOUGH_INFO không được kèm citation")

    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": {
            "label": result.label,
            "confidence": result.confidence,
            "explanation": result.explanation,
        },
        "retrieval": {
            "retrieved_count": len(records),
            "positive_score_count": sum(float(record["score"]) > 0 for record in records),
            "evidence": records,
        },
        "citations": citations,
    }
