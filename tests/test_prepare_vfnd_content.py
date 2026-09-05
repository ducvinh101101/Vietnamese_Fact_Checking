import json

from scripts.prepare_vfnd_content import build_records


def test_vfnd_article_only_builder_keeps_title_body_and_binary_label(tmp_path):
    for label, title in (("Real", "Tin thật"), ("Fake", "Tin giả")):
        directory = tmp_path / "Fake_Real_Dataset" / label / "Article_Contents"
        directory.mkdir(parents=True)
        (directory / f"{label}.json").write_text(json.dumps({
            "title": title,
            "text": "Nội dung bài viết.",
            "url": f"https://example.com/{label}",
            "source_domain": "example.com",
        }), encoding="utf-8")

    records = build_records(tmp_path)

    assert {record["label"] for record in records} == {0, 1}
    assert all(record["title"] and record["body"] for record in records)
    assert all(record["source_domain"] == "example.com" for record in records)
