from scripts.build_vifactcheck_evidence import split_passages, write_corpus
from src.io_utils import load_evidence_jsonl


def test_generated_corpus_loads_and_respects_max_chars(tmp_path):
    documents = {
        "https://example.com/article": {
            "content": "Câu đầu tiên ngắn. " + "từ " * 80,
            "source": "Example",
        }
    }
    output = tmp_path / "evidence.jsonl"

    documents_count, passages_count = write_corpus(documents, output, max_chars=100)
    evidence = load_evidence_jsonl(output)

    assert (documents_count, passages_count) == (1, len(evidence))
    assert all(len(item.content) <= 100 for item in evidence)
    assert evidence[0].url == "https://example.com/article"
    assert evidence[0].article_id == evidence[0].document_id
    assert evidence[0].source_type == "unknown"


def test_split_passages_breaks_a_single_oversized_sentence():
    passages = split_passages("từ " * 80, max_chars=100)

    assert len(passages) > 1
    assert all(len(passage) <= 100 for passage in passages)
