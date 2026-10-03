import importlib.util
from pathlib import Path

from src.schemas import Evidence, RetrievedEvidence


def load_acceptance_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_web_retrieval_acceptance.py"
    spec = importlib.util.spec_from_file_location("web_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_acceptance_report_requires_four_allowlisted_domains(monkeypatch):
    module = load_acceptance_module()

    class FakeRetriever:
        calls = 0

        def __init__(self, config):
            self.last_status = "not_run"

        def search(self, query, top_k):
            FakeRetriever.calls += 1
            domain = ["baochinhphu.vn", "moh.gov.vn", "www.who.int", "vnanet.vn"][FakeRetriever.calls - 1]
            self.last_status = "ok"
            evidence = Evidence(
                document_id=f"web-{FakeRetriever.calls}",
                passage_id=f"web-{FakeRetriever.calls}-p01",
                content="Nội dung passage kiểm thử đủ dài để băm.",
                url=f"https://{domain}/test-{FakeRetriever.calls}",
                domain=domain,
                title="Tiêu đề kiểm thử",
                retrieved_at="2026-09-16T00:00:00+00:00",
            )
            return [RetrievedEvidence(evidence, 1.0)]

    config = {
        "source_policy": {"allowlist": [
            {"host": "baochinhphu.vn"}, {"host": "moh.gov.vn"},
            {"host": "www.who.int"}, {"host": "vnanet.vn"},
        ]},
    }
    monkeypatch.setattr(module, "WebRetriever", FakeRetriever)
    monkeypatch.setattr(module, "load_config", lambda: (config, "config-hash"))
    report, passed = module.report_for_queries(["q1", "q2", "q3", "q4"], 1)

    assert passed
    assert report["acceptance"]["minimum_successful_queries"] == 4
    assert report["acceptance"]["successful_query_count"] == 4
    assert report["acceptance"]["distinct_domains"] == ["baochinhphu.vn", "moh.gov.vn", "vnanet.vn", "www.who.int"]
    assert all(query not in str(report) for query in ["q1", "q2", "q3", "q4"])
    serialized = str(report)
    assert "Nội dung passage" not in serialized
    assert report["acceptance"]["no_duplicate_content_per_url"] is True
