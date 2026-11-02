"""Bộ test mở rộng cho retrieval LOCAL: BM25, W3-08 metadata rerank, RRF fusion.

Mục tiêu: phủ các nhánh chưa có test (biên tham số, Unicode, xếp hạng, xác định,
lọc metadata, hợp nhất RRF) và ghi nhận các lỗi phát hiện được bằng
``xfail(strict=True)`` — khi lỗi được sửa, test sẽ XPASS và buộc gỡ marker.
"""

from __future__ import annotations

from dataclasses import replace
import unicodedata

import pytest

from src.contracts import Retriever
from src.fusion_retriever import FusionRetriever
from src.reranked_retriever import (
    MetadataRerankedRetriever,
    deduplicate_evidence,
    filter_metadata,
    generate_query,
)
from src.retriever import BM25Retriever
from src.schemas import Evidence, RetrievedEvidence


# --------------------------------------------------------------------------- helpers

CORPUS_TEXTS = [
    ("p1", "Thông báo về lịch học mới của trường đại học Bách khoa Hà Nội."),
    ("p2", "Khuyến cáo sức khỏe cộng đồng trong mùa dịch cúm."),
    ("p3", "Giá xăng RON 95 tăng 500 đồng mỗi lít từ chiều nay."),
    ("p4", "Đội tuyển bóng đá Việt Nam thắng Thái Lan 2-1."),
    ("p5", "Ngân hàng Nhà nước điều chỉnh lãi suất điều hành."),
]


def ev(pid: str, content: str, **kw) -> Evidence:
    kw.setdefault("url", f"https://local.test/{pid}")
    return Evidence(document_id=f"d-{pid}", passage_id=pid, content=content, **kw)


def corpus() -> list[Evidence]:
    return [ev(pid, text) for pid, text in CORPUS_TEXTS]


def ids(items: list[RetrievedEvidence]) -> list[str]:
    return [item.evidence.passage_id for item in items]


def non_increasing(items: list[RetrievedEvidence]) -> bool:
    return all(items[i].score >= items[i + 1].score for i in range(len(items) - 1))


class StaticRetriever:
    def __init__(self, items: list[RetrievedEvidence]) -> None:
        self.items = items
        self.calls: list[tuple[str, int]] = []

    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        self.calls.append((claim, top_k))
        return self.items[:top_k]


class ExplodingRetriever:
    def search(self, claim: str, top_k: int = 3) -> list[RetrievedEvidence]:
        raise TimeoutError("web timeout")


# =========================================================================== BM25


class TestBM25Retriever:
    def test_rejects_empty_corpus(self):
        with pytest.raises(ValueError):
            BM25Retriever([])

    @pytest.mark.parametrize("top_k", [0, -1])
    def test_rejects_non_positive_top_k(self, top_k):
        with pytest.raises(ValueError):
            BM25Retriever(corpus()).search("lịch học", top_k)

    def test_satisfies_retriever_protocol(self):
        assert isinstance(BM25Retriever(corpus()), Retriever)

    @pytest.mark.parametrize("claim, expected", [
        ("lịch học đại học Bách khoa", "p1"),
        ("giá xăng RON 95 tăng", "p3"),
        ("bóng đá Việt Nam thắng Thái Lan", "p4"),
        ("lãi suất điều hành ngân hàng", "p5"),
        ("sức khỏe cộng đồng dịch cúm", "p2"),
    ])
    def test_top1_is_the_relevant_passage(self, claim, expected):
        assert ids(BM25Retriever(corpus()).search(claim, 1)) == [expected]

    def test_ranking_does_not_depend_on_corpus_order(self):
        forward = BM25Retriever(corpus()).search("giá xăng tăng", 1)
        backward = BM25Retriever(list(reversed(corpus()))).search("giá xăng tăng", 1)
        assert ids(forward) == ids(backward) == ["p3"]

    def test_top_k_larger_than_corpus_returns_whole_corpus_sorted(self):
        result = BM25Retriever(corpus()).search("giá xăng", 50)
        assert len(result) == len(CORPUS_TEXTS)
        assert sorted(ids(result)) == sorted(pid for pid, _ in CORPUS_TEXTS)
        assert non_increasing(result)

    def test_is_deterministic_across_instances_and_calls(self):
        a = BM25Retriever(corpus())
        b = BM25Retriever(corpus())
        runs = [a.search("Hà Nội lịch học", 5) for _ in range(3)] + [b.search("Hà Nội lịch học", 5)]
        assert all([(r.evidence.passage_id, r.score) for r in run] ==
                   [(r.evidence.passage_id, r.score) for r in runs[0]] for run in runs)

    def test_case_insensitive(self):
        upper = BM25Retriever(corpus()).search("GIÁ XĂNG RON", 1)
        assert ids(upper) == ["p3"]

    def test_nfd_query_matches_nfc_corpus(self):
        nfd = unicodedata.normalize("NFD", "giá xăng tăng")
        assert nfd != "giá xăng tăng"
        assert ids(BM25Retriever(corpus()).search(nfd, 1)) == ["p3"]

    def test_nfd_corpus_matches_nfc_query(self):
        items = [ev(pid, unicodedata.normalize("NFD", text)) for pid, text in CORPUS_TEXTS]
        assert ids(BM25Retriever(items).search("lãi suất điều hành", 1)) == ["p5"]

    def test_html_entities_and_zero_width_chars_are_normalised(self):
        items = corpus() + [ev("p6", "Bộ\u200b Y&nbsp;tế công bố phác đồ điều trị sốt xuất huyết.")]
        assert ids(BM25Retriever(items).search("Bộ Y tế phác đồ sốt xuất huyết", 1)) == ["p6"]

    def test_urls_in_claim_do_not_become_tokens(self):
        items = corpus() + [ev("p6", "https vnexpress net tin tức")]
        result = BM25Retriever(items).search("https://vnexpress.net/abc giá xăng", 1)
        assert ids(result) == ["p3"]

    @pytest.mark.parametrize("claim", ["", "   ", "!!! ??? ...", "😀😀"])
    def test_query_without_tokens_does_not_crash(self, claim):
        result = BM25Retriever(corpus()).search(claim, 3)
        assert len(result) == 3
        assert all(item.score == 0.0 for item in result)

    def test_out_of_vocabulary_claim_returns_zero_scores(self):
        """Ghi nhận hành vi: BM25 KHÔNG tự lọc kết quả điểm 0 (verifier/guard phải xử lý NEI)."""
        result = BM25Retriever(corpus()).search("quantum chromodynamics", 2)
        assert len(result) == 2 and all(item.score == 0.0 for item in result)

    def test_unaccented_query_does_not_match_accented_corpus(self):
        """C-03: claim không dấu là HẠN CHẾ đã biết của BM25 baseline."""
        result = BM25Retriever(corpus()).search("gia xang tang", 1)
        assert result[0].score == 0.0

    def test_very_long_claim_does_not_crash(self):
        claim = "giá xăng tăng " * 400
        assert ids(BM25Retriever(corpus()).search(claim, 1)) == ["p3"]

    def test_two_document_corpus_cannot_discriminate(self):
        """Đặc tính của BM25Okapi: N=2, term xuất hiện 1 tài liệu -> idf = log(1.5/1.5) = 0.

        Test cũ ``test_retriever.py::test_bm25_returns_most_relevant_evidence`` pass
        chỉ nhờ thứ tự ổn định của ``sorted``; test này ghi nhận điều đó.
        """
        items = [ev("p2", "Khuyến cáo sức khỏe cộng đồng."), ev("p1", "Thông báo về lịch học mới.")]
        result = BM25Retriever(items).search("lịch học", 2)
        assert [item.score for item in result] == [0.0, 0.0]
        assert ids(result) == ["p2", "p1"]  # thắng chỉ vì đứng trước trong corpus

    def test_returns_same_evidence_objects_from_corpus(self):
        items = corpus()
        result = BM25Retriever(items).search("giá xăng", 1)
        assert result[0].evidence is items[2]


# ====================================================================== W3-08 rerank

RERANK_CONFIG = {
    "candidate_k": 100,
    "rerank": {"query_overlap_weight": 0.20, "authority_weight": 0.05},
    "filters": {
        "allowed_source_types": ["government", "news"],
        "published_after": None,
        "published_before": None,
        "include_unknown_published_at": True,
    },
}


def rerank_config(**filters) -> dict:
    config = {**RERANK_CONFIG, "filters": {**RERANK_CONFIG["filters"], **filters}}
    return config


def r(pid: str, published_at: str | None = "2024-06-01T00:00:00Z", source_type="news",
      authority: float | None = 0.7, content: str | None = None, url: str | None = None,
      score: float = 1.0) -> RetrievedEvidence:
    return RetrievedEvidence(
        ev(pid, content or f"nội dung {pid}", published_at=published_at, source_type=source_type,
           authority_score=authority, url=url or f"https://local.test/{pid}"),
        score,
    )


class TestGenerateQuery:
    @pytest.mark.parametrize("claim, expected", [
        ("  a   b\tc\n", "a b c"),
        ("Hà\u00a0Nội", "Hà Nội"),
        ("x", "x"),
    ])
    def test_normalises_whitespace(self, claim, expected):
        assert generate_query(claim) == expected

    @pytest.mark.parametrize("claim", ["", "   ", "\n\t"])
    def test_rejects_blank(self, claim):
        with pytest.raises(ValueError):
            generate_query(claim)


class TestFilterMetadata:
    def test_empty_allowlist_keeps_all_source_types(self):
        items = [r("a", source_type="other"), r("b", source_type="unknown")]
        assert ids(filter_metadata(items, {})) == ["a", "b"]

    def test_source_type_allowlist(self):
        items = [r("g", source_type="government"), r("n"), r("o", source_type="other")]
        assert ids(filter_metadata(items, {"allowed_source_types": ["government", "news"]})) == ["g", "n"]

    def test_date_bounds_are_inclusive(self):
        items = [r("before", "2023-12-31T23:59:59Z"), r("start", "2024-01-01T00:00:00Z"),
                 r("end", "2024-12-31T00:00:00Z"), r("after", "2025-01-01T00:00:00Z")]
        kept = filter_metadata(items, {"published_after": "2024-01-01T00:00:00Z",
                                       "published_before": "2024-12-31T00:00:00Z"})
        assert ids(kept) == ["start", "end"]

    def test_unknown_dates_follow_flag(self):
        items = [r("u", None), r("k")]
        assert ids(filter_metadata(items, {"published_after": "2020-01-01T00:00:00Z"})) == ["u", "k"]
        assert ids(filter_metadata(items, {"include_unknown_published_at": False})) == ["k"]

    def test_timezone_offsets_are_compared_as_instants(self):
        # 2024-01-01T06:00+07:00 == 2023-12-31T23:00Z -> trước mốc after
        items = [r("vn", "2024-01-01T06:00:00+07:00")]
        assert filter_metadata(items, {"published_after": "2024-01-01T00:00:00Z"}) == []

    def test_preserves_input_order(self):
        items = [r("c"), r("a"), r("b")]
        assert ids(filter_metadata(items, rerank_config()["filters"])) == ["c", "a", "b"]

    @pytest.mark.xfail(strict=True, raises=TypeError,
                       reason="BUG: so sánh datetime naive (không múi giờ) với aware ('Z') -> TypeError")
    def test_naive_published_at_against_aware_filter_does_not_crash(self):
        items = [r("naive", "2024-06-01")]
        assert ids(filter_metadata(items, {"published_after": "2024-01-01T00:00:00Z"})) == ["naive"]

    @pytest.mark.xfail(strict=True, raises=ValueError,
                       reason="BUG: published_at không phải ISO (vd '15/03/2023') làm sập cả truy vấn")
    def test_malformed_published_at_is_treated_as_unknown(self):
        items = [r("bad", "15/03/2023"), r("ok")]
        assert ids(filter_metadata(items, {"include_unknown_published_at": True})) == ["bad", "ok"]


class TestDeduplicate:
    def test_same_url_and_whitespace_case_variant_content_is_merged(self):
        a = r("a", content="Giá xăng  tăng", url="https://x/1")
        b = r("b", content="giá xăng tăng ", url="https://x/1")
        assert ids(deduplicate_evidence([a, b])) == ["a"]

    def test_same_content_different_url_is_kept(self):
        a = r("a", content="Giá xăng tăng", url="https://x/1")
        b = r("b", content="Giá xăng tăng", url="https://x/2")
        assert ids(deduplicate_evidence([a, b])) == ["a", "b"]

    def test_keeps_first_occurrence(self):
        a = r("a", content="same", url="https://x/1", score=0.1)
        b = r("b", content="same", url="https://x/1", score=9.0)
        assert ids(deduplicate_evidence([a, b])) == ["a"]


def rerank_corpus() -> list[Evidence]:
    return [
        ev("gov", "Bộ Y tế ban hành hướng dẫn tiêm vaccine cho trẻ em", source_type="government",
           authority_score=0.95, published_at="2024-03-01T00:00:00Z"),
        ev("news", "Bộ Y tế ban hành hướng dẫn tiêm vaccine cho trẻ em", source_type="news",
           authority_score=0.7, published_at="2024-03-01T00:00:00Z", url="https://local.test/news"),
        ev("other", "Bộ Y tế ban hành hướng dẫn tiêm vaccine cho trẻ em", source_type="other",
           authority_score=0.9, published_at="2024-03-01T00:00:00Z", url="https://local.test/other"),
        ev("old", "Hướng dẫn tiêm vaccine cho trẻ em năm 2019", source_type="news",
           authority_score=0.7, published_at="2019-01-01T00:00:00Z"),
        ev("noise1", "Giá vàng hôm nay giảm mạnh", source_type="news", authority_score=0.7),
        ev("noise2", "Đội tuyển bóng đá thắng đậm", source_type="news", authority_score=0.7),
        ev("noise3", "Lãi suất ngân hàng tiếp tục giảm", source_type="news", authority_score=0.7),
    ]


class TestMetadataRerankedRetriever:
    def build(self, **filters) -> MetadataRerankedRetriever:
        return MetadataRerankedRetriever(BM25Retriever(rerank_corpus()), rerank_config(**filters))

    def test_rejects_bad_candidate_k_and_top_k(self):
        with pytest.raises(ValueError):
            MetadataRerankedRetriever(BM25Retriever(corpus()), {**RERANK_CONFIG, "candidate_k": 0})
        with pytest.raises(ValueError):
            self.build().search("vaccine", 0)

    def test_rejects_blank_claim(self):
        with pytest.raises(ValueError):
            self.build().search("   ", 3)

    def test_authority_breaks_tie_for_identical_content(self):
        """C-07: cùng nội dung, nguồn government xếp trên news."""
        result = self.build().search("Bộ Y tế ban hành hướng dẫn tiêm vaccine", 3)
        assert ids(result)[:2] == ["gov", "news"]
        assert result[0].score - result[1].score == pytest.approx(0.05 * (0.95 - 0.7))

    def test_disallowed_source_type_is_never_returned(self):
        result = self.build().search("hướng dẫn tiêm vaccine trẻ em", 10)
        assert "other" not in ids(result)

    def test_published_after_filter_drops_old_passage(self):
        result = self.build(published_after="2023-01-01T00:00:00Z").search("tiêm vaccine trẻ em", 10)
        assert "old" not in ids(result)
        assert {"gov", "news"} <= set(ids(result))

    def test_scores_non_increasing_and_capped_at_top_k(self):
        for k in (1, 2, 3, 5):
            result = self.build().search("tiêm vaccine trẻ em", k)
            assert len(result) <= k
            assert non_increasing(result)

    def test_candidate_k_bounded_by_corpus_size(self):
        retriever = MetadataRerankedRetriever(BM25Retriever(corpus()), {**RERANK_CONFIG, "candidate_k": 10_000})
        assert len(retriever.search("giá xăng", 3)) <= 3

    def test_small_candidate_k_limits_reranking_pool(self):
        retriever = MetadataRerankedRetriever(BM25Retriever(rerank_corpus()), {**RERANK_CONFIG, "candidate_k": 1})
        assert len(retriever.search("tiêm vaccine trẻ em", 5)) == 1

    def test_deterministic(self):
        retriever = self.build()
        first = [(i.evidence.passage_id, i.score) for i in retriever.search("tiêm vaccine trẻ em", 5)]
        assert all(first == [(i.evidence.passage_id, i.score) for i in retriever.search("tiêm vaccine trẻ em", 5)]
                   for _ in range(3))

    def test_duplicate_url_and_content_collapsed(self):
        items = rerank_corpus() + [replace(rerank_corpus()[0], passage_id="gov-dup")]
        retriever = MetadataRerankedRetriever(BM25Retriever(items), RERANK_CONFIG)
        result = ids(retriever.search("hướng dẫn tiêm vaccine trẻ em", 10))
        assert not ({"gov", "gov-dup"} <= set(result))

    def test_missing_authority_score_is_treated_as_zero(self):
        items = [ev("a", "vaccine trẻ em", source_type="news", authority_score=None),
                 ev("b", "vaccine trẻ em", source_type="news", authority_score=0.7, url="https://local.test/b"),
                 ev("n1", "giá vàng"), ev("n2", "bóng đá")]
        items = [replace(i, source_type="news") for i in items]
        result = MetadataRerankedRetriever(BM25Retriever(items), RERANK_CONFIG).search("vaccine trẻ em", 2)
        assert ids(result) == ["b", "a"]


# ============================================================================ Fusion


def fr(pid: str, content: str | None = None, url: str | None = None, score: float = 1.0) -> RetrievedEvidence:
    return RetrievedEvidence(ev(pid, content or f"nội dung {pid}", url=url or f"https://x/{pid}"), score)


class TestFusionRetriever:
    @pytest.mark.parametrize("kwargs", [{"rrf_k": 0}, {"candidate_k": 0}])
    def test_rejects_bad_parameters(self, kwargs):
        with pytest.raises(ValueError):
            FusionRetriever(StaticRetriever([]), **kwargs)

    def test_rejects_bad_top_k(self):
        with pytest.raises(ValueError):
            FusionRetriever(StaticRetriever([fr("a")])).search("x", 0)

    def test_local_only_preserves_local_order_with_rrf_scores(self):
        local = StaticRetriever([fr("a"), fr("b"), fr("c")])
        result = FusionRetriever(local, None, rrf_k=60).search("x", 3)
        assert ids(result) == ["a", "b", "c"]
        assert [item.score for item in result] == pytest.approx([1 / 61, 1 / 62, 1 / 63])

    def test_requests_candidate_k_from_both_branches(self):
        local, web = StaticRetriever([fr("a")]), StaticRetriever([fr("w")])
        FusionRetriever(local, web, candidate_k=7).search("claim", 2)
        assert local.calls == [("claim", 7)] and web.calls == [("claim", 7)]

    def test_passage_found_by_both_branches_ranks_first(self):
        shared = fr("shared", "Hà Nội là thủ đô", url="https://x/shared")
        local = StaticRetriever([fr("l1"), shared])
        web = StaticRetriever([fr("w1"), RetrievedEvidence(shared.evidence, 99.0)])
        result = FusionRetriever(local, web).search("x", 3)
        assert ids(result)[0] == "shared"
        assert result[0].score == pytest.approx(2 / 62)

    def test_raw_score_scale_does_not_matter(self):
        local = StaticRetriever([fr("l1", score=0.01)])
        web = StaticRetriever([fr("w1", score=10_000.0)])
        result = FusionRetriever(local, web).search("x", 2)
        assert result[0].score == result[1].score == pytest.approx(1 / 61)

    def test_interleaves_by_rank(self):
        local = StaticRetriever([fr("l1"), fr("l2")])
        web = StaticRetriever([fr("w1"), fr("w2")])
        result = FusionRetriever(local, web).search("x", 4)
        ranks = {pid: i for i, pid in enumerate(ids(result))}
        assert max(ranks["l1"], ranks["w1"]) < min(ranks["l2"], ranks["w2"])

    def test_dedup_is_case_and_whitespace_insensitive(self):
        a = fr("a", "Giá xăng  tăng", url="https://X/1")
        b = fr("b", "giá xăng tăng", url="https://x/1")
        result = FusionRetriever(StaticRetriever([a]), StaticRetriever([b])).search("x", 5)
        assert ids(result) == ["a"]  # giữ bản local

    def test_web_error_falls_back_and_is_reset_on_next_call(self):
        local = StaticRetriever([fr("a")])
        fusion = FusionRetriever(local, ExplodingRetriever())
        assert ids(fusion.search("x", 3)) == ["a"]
        assert "TimeoutError" in (fusion.last_web_error or "")
        fusion.web = StaticRetriever([fr("w")])
        fusion.search("x", 3)
        assert fusion.last_web_error is None

    def test_local_error_is_not_swallowed(self):
        with pytest.raises(TimeoutError):
            FusionRetriever(ExplodingRetriever(), StaticRetriever([fr("w")])).search("x", 3)

    def test_empty_both_branches_returns_empty(self):
        assert FusionRetriever(StaticRetriever([]), StaticRetriever([])).search("x", 3) == []

    def test_output_contract_scores_non_increasing_and_top_k(self):
        local = StaticRetriever([fr(f"l{i}") for i in range(10)])
        web = StaticRetriever([fr(f"w{i}") for i in range(10)])
        for k in (1, 3, 7, 25):
            result = FusionRetriever(local, web).search("x", k)
            assert len(result) == min(k, 20)
            assert non_increasing(result)


# ===================================================== Local end-to-end on real corpus


@pytest.mark.slow
def test_real_v1_corpus_retrieves_gold_article_for_dev_queries():
    """Smoke chất lượng trên dữ liệu thật: 50 truy vấn dev đầu, BM25 corpus v1.

    Ngưỡng thấp có chủ đích (chống hồi quy thô, không phải benchmark). Benchmark đầy
    đủ: ``scripts/check_retrieval_quality.py``.
    """
    import json
    from pathlib import Path

    from src.io_utils import load_evidence_jsonl

    root = Path(__file__).resolve().parents[1]
    queries = [json.loads(line) for line in
               (root / "data/evaluation/vifactcheck_retrieval_query_set_v1.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    dev = [q for q in queries if q["split"] == "dev"][:50]
    retriever = BM25Retriever(load_evidence_jsonl(root / "data/evidence/vifactcheck_passages.jsonl"))
    hits = 0
    for query in dev:
        result = retriever.search(query["query"], 5)
        assert non_increasing(result)
        hits += any(item.evidence.url == query["gold_url"] for item in result)
    assert hits / len(dev) >= 0.6
