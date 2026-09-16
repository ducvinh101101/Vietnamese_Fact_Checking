from scripts.check_versioned_evidence_corpus import validate


def test_w3_07_versioned_corpus_is_integrity_checked():
    manifest = validate()
    assert manifest["passages"] == 5844
    assert manifest["deduplication"]["removed_duplicates"] == 1
    assert set(manifest["metadata"]["source_counts"]) == {
        "baochinhphu.vn", "baotintuc.vn", "dantri.com.vn", "nld.com.vn", "plo.vn",
        "thanhnien.vn", "tienphong.vn", "tuoitre.vn", "vnexpress.net",
    }
