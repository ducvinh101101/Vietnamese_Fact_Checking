# BM25 retrieval evaluation — W2-01

## Purpose and boundary

This is Quang's reproducible baseline evaluation for the existing local
ViFactCheck passage corpus. It does not change the verifier, data contract,
pipeline configuration, or any implementation owned by Vinh.

## Relevance protocol

The grouped ViFactCheck test split provides an annotated evidence `Url` for
every claim. A retrieved passage is counted as relevant when its `url` equals
that annotated URL. Thus the reported metrics are **URL-level**, even though
the index retrieves passages.

This distinction matters: a direct normalised-string comparison finds the
annotated `Evidence` inside (or containing) a corpus passage for only a subset
of queries. The exact coverage is emitted in the metrics JSON and must always
accompany the headline scores. This baseline must not be described as
passage-level gold evaluation.

## Inputs

- Corpus: `data/evidence/vifactcheck_passages.jsonl`.
- Query set: `data/processed/vifactcheck_group_split/test.parquet`.
- Relevance key: `Url` in the query split and `url` in the passage corpus.
- Retriever: the unmodified `src.retriever.BM25Retriever` using
  `rank-bm25` and `src.preprocessing.tokenize_for_retrieval`.

The grouped split is used to avoid URL leakage between train, development and
test datasets. BM25 has no learned parameters in this run; this is a frozen
baseline, not a tuning result.

## Metrics and latency

- Recall@3 and Recall@5: fraction of queries with the annotated URL in the
  first 3 or 5 retrieved passages.
- MRR@5: reciprocal rank of the first retrieved passage with that URL, zero
  when absent from the first 5.
- Latency: per-query wall-clock time for `BM25Retriever.search`, including
  tokenisation, scoring, sorting and result construction, but excluding corpus
  loading, index building and output I/O. Mean, p50 and p95 are recorded.

## Reproduce

From the repository root, with the locked environment installed:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_bm25_retrieval.py
```

This writes the metrics, all top-5 predictions and a deterministic ten-query
audit set. The audit queries are selected by the ten smallest SHA-256 values of
their stable split row IDs; they are a review sample, not the benchmark itself.

## Outputs

- `outputs/metrics/bm25_retrieval_test.json`
- `outputs/retrieval/bm25_retrieval_test_top5.jsonl`
- `data/evaluation/bm25_retrieval_audit_queries.jsonl`

For a later passage-level evaluation, define independently reviewed positive
passage IDs or spans before comparing the results with this URL-level baseline.
