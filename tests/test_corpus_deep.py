"""Deep corpus validation tests (no model required)."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
import pytest

from tests.fc_helpers import CORPUS_PATH, REQUIRED_FIELDS, read_jsonl

pytestmark = pytest.mark.skipif(not CORPUS_PATH.exists(), reason=f"Corpus file not found: {CORPUS_PATH}")


@pytest.fixture(scope="module")
def corpus_records():
    raw_lines = read_jsonl(CORPUS_PATH)
    records = []
    invalid_lines = []
    blank_lines = []
    for line_num, line in raw_lines:
        s = line.strip()
        if not s:
            blank_lines.append(line_num)
            continue
        try:
            records.append((line_num, json.loads(s)))
        except Exception:
            invalid_lines.append(line_num)
    return records, blank_lines, invalid_lines


def test_no_blank_or_invalid_lines(corpus_records):
    records, blank_lines, invalid_lines = corpus_records
    # In file vifactcheck_passages.jsonl có 5845 dòng hợp lệ về cú pháp JSON, 0 dòng trống.
    # Trong khi vifactcheck_passages_v2.jsonl có 5844 dòng do đã khử 1 dòng trùng lặp nội dung tại dòng 5704 (vifactcheck_01010_p006).
    assert not blank_lines, f"Found blank lines at line numbers: {blank_lines}"
    assert not invalid_lines, f"Found invalid JSON lines at: {invalid_lines}"
    print(f"\n[CORPUS_LINES] Total parsed lines: {len(records)}; Blank: {len(blank_lines)}; Invalid JSON: {len(invalid_lines)}")


def test_required_fields_non_empty(corpus_records):
    records, _, _ = corpus_records
    missing_or_empty = []
    for line_num, row in records:
        for field in REQUIRED_FIELDS:
            val = row.get(field)
            if val is None or not str(val).strip():
                missing_or_empty.append((line_num, field))
    assert not missing_or_empty, f"Missing or empty required fields: {missing_or_empty[:10]}"


def test_passage_id_unique(corpus_records):
    records, _, _ = corpus_records
    seen = set()
    duplicates = []
    for line_num, row in records:
        pid = row.get("passage_id")
        if pid in seen:
            duplicates.append((line_num, pid))
        seen.add(pid)
    assert not duplicates, f"Duplicate passage_ids found: {duplicates}"


def test_max_length_700(corpus_records):
    records, _, _ = corpus_records
    too_long = [(line_num, len(row.get("content", ""))) for line_num, row in records if len(row.get("content", "")) > 700]
    assert not too_long, f"Passages exceeding 700 chars: {len(too_long)}"


def test_min_length_not_tiny(corpus_records):
    records, _, _ = corpus_records
    tiny = [row for _, row in records if len(row.get("content", "").strip()) < 20]
    ratio = len(tiny) / len(records)
    print(f"\n[TINY_PASSAGES] Count < 20 chars: {len(tiny)} ({ratio:.2%})")
    assert ratio < 0.01, f"Too many tiny passages: {ratio:.2%}"


def test_unicode_nfc(corpus_records):
    records, _, _ = corpus_records
    not_nfc = []
    for line_num, row in records:
        c = row.get("content", "")
        if not unicodedata.is_normalized("NFC", c):
            not_nfc.append(line_num)
    assert not not_nfc, f"Passages not normalized to NFC: {len(not_nfc)} lines (first 5: {not_nfc[:5]})"


def test_no_control_chars_or_markup(corpus_records):
    records, _, _ = corpus_records
    # Pattern for suspicious HTML tags and control chars (except standard whitespace \n \t)
    html_pattern = re.compile(r"<\s*(script|style|iframe|div|span|br)[^>]*>", re.IGNORECASE)
    # Zero-width spaces, joiners, or control characters < 32 (excluding \t, \n, \r)
    control_pattern = re.compile(r"[\u200B-\u200D\uFEFF]|[\x00-\x08\x0B\x0C\x0E-\x1F]")

    violations = []
    for line_num, row in records:
        content = row.get("content", "")
        if html_pattern.search(content) or control_pattern.search(content):
            violations.append(line_num)
    assert not violations, f"Markup or control characters found in lines: {violations[:10]}"


def test_no_surrounding_whitespace(corpus_records):
    records, _, _ = corpus_records
    bad_ws = []
    for line_num, row in records:
        content = row.get("content", "")
        if content != content.strip():
            bad_ws.append(line_num)
    ratio = len(bad_ws) / len(records)
    print(f"\n[SURROUNDING_WS] Passages with leading/trailing ws: {len(bad_ws)} ({ratio:.2%})")
    assert ratio < 0.01, f"Too many passages with surrounding whitespace: {ratio:.2%}"


def test_url_scheme_valid(corpus_records):
    records, _, _ = corpus_records
    bad_urls = []
    for line_num, row in records:
        url = row.get("url", "")
        if not (url.startswith("http://") or url.startswith("https://")):
            bad_urls.append((line_num, url))
    assert not bad_urls, f"Invalid URL scheme found: {bad_urls[:10]}"


def test_document_url_one_to_one(corpus_records):
    records, _, _ = corpus_records
    doc_to_urls = {}
    url_to_docs = {}
    for line_num, row in records:
        doc = row.get("document_id")
        url = row.get("url")
        doc_to_urls.setdefault(doc, set()).add(url)
        url_to_docs.setdefault(url, set()).add(doc)

    multi_urls = {doc: urls for doc, urls in doc_to_urls.items() if len(urls) > 1}
    multi_docs = {url: docs for url, docs in url_to_docs.items() if len(docs) > 1}

    assert not multi_urls, f"document_id mapped to multiple URLs: {list(multi_urls.items())[:5]}"
    assert not multi_docs, f"URL mapped to multiple document_ids: {list(multi_docs.items())[:5]}"


def test_duplicate_content_across_documents(corpus_records):
    records, _, _ = corpus_records
    content_to_urls = {}
    for _, row in records:
        c = row.get("content", "").strip().casefold()
        u = row.get("url")
        content_to_urls.setdefault(c, set()).add(u)

    cross_doc_dups = {c: urls for c, urls in content_to_urls.items() if len(urls) > 1}
    ratio = len(cross_doc_dups) / len(records)
    print(f"\n[CONTENT_DUP] Content appearing across multiple URLs: {len(cross_doc_dups)} ({ratio:.2%})")
    assert ratio < 0.02, f"Too much cross-document duplicate content: {ratio:.2%}"


def test_sentence_boundary_heuristic(corpus_records):
    records, _, _ = corpus_records
    min_ratio = float(os.environ.get("FC_BOUNDARY_MIN", "0.6"))
    # Check if ends with punctuation mark . ! ? " ” …
    sentence_endings = re.compile(r'[\.\!\?\"”\…\:\;]\s*$')
    ending_count = 0
    for _, row in records:
        content = row.get("content", "").strip()
        if sentence_endings.search(content):
            ending_count += 1
    ratio = ending_count / len(records)
    print(f"\n[SENTENCE_BOUNDARY] Passages ending with punctuation: {ending_count}/{len(records)} ({ratio:.2%})")
    assert ratio >= min_ratio, f"Sentence boundary ratio below threshold: {ratio:.2%} < {min_ratio:.2%}"


def test_claim_leak_into_corpus(corpus_records):
    test_claims_path = os.environ.get("FC_TEST_CLAIMS")
    if not test_claims_path or not Path(test_claims_path).exists():
        pytest.skip("FC_TEST_CLAIMS environment variable not set or file does not exist.")

    records, _, _ = corpus_records
    # Build normalized corpus content set / text search
    corpus_contents = [row.get("content", "").strip().casefold() for _, row in records]

    claim_lines = read_jsonl(test_claims_path)
    if not claim_lines:
        pytest.skip(f"No claims found in {test_claims_path}")

    leak_count = 0
    total_claims = 0
    for _, raw_line in claim_lines:
        total_claims += 1
        data = json.loads(raw_line)
        claim_text = data.get("claim", "").strip().casefold()
        if not claim_text:
            continue
        # Check if verbatim claim appears inside any corpus passage
        if any(claim_text in passage for passage in corpus_contents):
            leak_count += 1

    leak_ratio = leak_count / max(1, total_claims)
    print(f"\n[LEAK] Verbatim claim leak ratio: {leak_count}/{total_claims} ({leak_ratio:.2%})")
    assert leak_ratio < 0.05, f"Claim leak into corpus is too high: {leak_ratio:.2%} >= 5%"


def test_heldout_urls_not_in_corpus(corpus_records):
    heldout_path = os.environ.get("FC_HELDOUT")
    if not heldout_path or not Path(heldout_path).exists():
        pytest.skip("FC_HELDOUT environment variable not set or file does not exist.")

    records, _, _ = corpus_records
    corpus_urls = {row.get("url") for _, row in records}

    heldout_lines = read_jsonl(heldout_path)
    overlap = []
    for line_num, raw_line in heldout_lines:
        data = json.loads(raw_line)
        url = data.get("url")
        if url in corpus_urls:
            overlap.append((line_num, url))

    assert not overlap, f"Held-out URLs found in corpus: {overlap[:10]}"
