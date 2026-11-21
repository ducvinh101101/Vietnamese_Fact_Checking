"""Chấm điểm mức liên quan claim–đoạn văn ở thang tuyệt đối [0, 1].

Điểm BM25/RRF chỉ so sánh được trong cùng một truy vấn nên không thể dùng làm
ngưỡng "không tìm thấy nguồn". Module này cung cấp hai bộ chấm cho cùng một
giao diện ``score(claim, passages) -> list[float]``:

* ``CrossEncoderReranker``: model cross-encoder. Hỗ trợ
  - reranker một logit (vd. ``BAAI/bge-reranker-v2-m3``) → sigmoid;
  - PhoBERT nhị phân do nhóm fine-tune (``kaggle/finetune_phobert_reranker.py``)
    → softmax lớp "liên quan"; cần tách từ VnCoreNLP như lúc train.
* ``LexicalSourceScorer``: không cần model; độ phủ từ nội dung, bigram và các
  chi tiết cứng (số, ngày, tên riêng) của claim trong đoạn văn. Dùng làm
  baseline có thể giải thích được và làm fallback khi chưa có model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, Sequence

from src.schemas import RetrievedEvidence
from src.vi_text import (
    ClaimFacets, approximate_numbers, content_syllables, extract_dates, extract_numbers, fold, number_matches, tokenize_bm25,
)


class RelevanceScorer(Protocol):
    name: str

    def score(self, claim: str, passages: Sequence[str]) -> list[float]: ...


def dates_compatible(claim_date: str, passage_dates: set[str]) -> bool:
    """"03/2023" khớp "15/03/2023"; "15/03" khớp "15/03/2023"; "2023" khớp cả hai."""
    return any(
        date == claim_date or date.endswith("/" + claim_date) or date.startswith(claim_date + "/")
        for date in passage_dates
    )


def entity_present(entity: str, passage_folded: str) -> bool:
    folded = fold(entity)
    if folded in passage_folded:
        return True
    parts = folded.split()
    return len(parts) > 1 and all(f" {part} " in f" {passage_folded} " for part in parts)


class LexicalSourceScorer:
    """Độ phủ có trọng số: 0.45 âm tiết + 0.25 bigram + 0.30 chi tiết cứng."""

    name = "lexical"

    def __init__(self, approximate: bool = True) -> None:
        # approximate: số sau "hơn/gần/khoảng" khớp như check_facets (False = hành vi cũ, để so sánh)
        self.approximate = approximate

    def score(self, claim: str, passages: Sequence[str]) -> list[float]:
        facets = ClaimFacets.from_text(claim)
        approximate = approximate_numbers(claim) if self.approximate else {}
        claim_terms = set(content_syllables(claim))
        claim_bigrams = {token for token in tokenize_bm25(claim) if "_" in token}
        results: list[float] = []
        for passage in passages:
            passage_terms = set(tokenize_bm25(passage))
            unigram = len(claim_terms & passage_terms) / max(1, len(claim_terms))
            bigram = len(claim_bigrams & passage_terms) / max(1, len(claim_bigrams))
            hard_total = len(facets.numbers) + len(facets.dates) + len(facets.entities)
            if hard_total:
                passage_folded = fold(passage)
                numbers = extract_numbers(passage)
                dates = extract_dates(passage)
                hits = sum(number_matches(number, numbers, approximate) for number in facets.numbers)
                hits += sum(dates_compatible(date, dates) for date in facets.dates)
                hits += sum(entity_present(entity, passage_folded) for entity in facets.entities)
                hard = hits / hard_total
                results.append(round(0.45 * unigram + 0.25 * bigram + 0.30 * hard, 6))
            else:
                results.append(round(0.6 * unigram + 0.4 * bigram, 6))
        return results


class CrossEncoderReranker:
    """Cross-encoder Hugging Face; tự nhận dạng đầu ra 1 hay 2 logit."""

    def __init__(
        self,
        model_path: str | Path,
        max_length: int = 256,
        batch_size: int = 16,
        segmenter: Callable[[str], str] | None = None,
        positive_index: int = 1,
        device: str | None = None,
    ) -> None:
        try:
            from src.phobert_fact_checker import prepare_torch_dll_path

            prepare_torch_dll_path()
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as error:
            raise RuntimeError("Cần cài torch và transformers để dùng cross-encoder.") from error
        self.torch = torch
        self.name = f"cross-encoder:{Path(str(model_path)).name}"
        self.max_length = max_length
        self.batch_size = batch_size
        self.segmenter = segmenter
        self.positive_index = positive_index
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        use_fast = segmenter is None  # PhoBERT dùng tokenizer chậm, như lúc train
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_path), use_fast=use_fast)
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_path)).to(self.device)
        self.model.eval()

    def score(self, claim: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        prepare = self.segmenter or (lambda text: text)
        claim_text = prepare(claim)
        scores: list[float] = []
        for start in range(0, len(passages), self.batch_size):
            batch = [prepare(passage) for passage in passages[start:start + self.batch_size]]
            inputs = self.tokenizer(
                [claim_text] * len(batch), batch, padding=True, truncation=True,
                max_length=self.max_length, return_tensors="pt",
            ).to(self.device)
            with self.torch.inference_mode():
                logits = self.model(**inputs).logits.float()
            if logits.shape[-1] == 1:
                values = self.torch.sigmoid(logits[:, 0])
            else:
                values = self.torch.softmax(logits, dim=-1)[:, self.positive_index]
            scores.extend(float(value) for value in values.cpu().tolist())
        return scores


class VerifierRelevanceScorer:
    """Dùng verifier 3 lớp đã train (RT-V2) làm reranker: P(SUPPORTED) + P(REFUTED).

    NEI của RT-V2 nghĩa là "đoạn này không đủ để kết luận" – phần bù của nó là
    xác suất đoạn văn nói về đúng sự việc trong claim. ``blend`` trộn thêm điểm
    lexical để giữ tín hiệu khớp số/ngày/tên riêng.
    """

    def __init__(self, verifier: object, blend: float = 0.0) -> None:
        if not 0 <= blend <= 1:
            raise ValueError("blend phải trong [0, 1]")
        self.verifier = verifier
        self.blend = blend
        self.lexical = LexicalSourceScorer()
        self.name = "rt-v2-relevance" + (f"+lexical{blend:g}" if blend else "")

    def score(self, claim: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        probabilities = self.verifier.predict_probabilities_batch(claim, list(passages))  # type: ignore[attr-defined]
        model = [float(p[0]) + float(p[1]) for p in probabilities]
        if not self.blend:
            return model
        lexical = self.lexical.score(claim, passages)
        return [(1 - self.blend) * m + self.blend * l for m, l in zip(model, lexical)]


def rerank(scorer: RelevanceScorer, claim: str, items: Sequence[RetrievedEvidence], top_k: int) -> list[RetrievedEvidence]:
    """Thay điểm retrieval bằng điểm liên quan tuyệt đối rồi sắp lại."""
    if not items:
        return []
    scores = scorer.score(claim, [item.evidence.content for item in items])
    rescored = [RetrievedEvidence(item.evidence, float(score)) for item, score in zip(items, scores)]
    rescored.sort(key=lambda item: (-item.score, item.evidence.passage_id))
    return rescored[:top_k]
