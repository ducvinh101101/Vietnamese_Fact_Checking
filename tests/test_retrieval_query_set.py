from scripts.build_retrieval_query_set import exact_passage_matches, normalize_text


def test_normalization_keeps_vietnamese_letters_and_ignores_punctuation():
    assert normalize_text('Học, thông qua  CHƠI!') == 'học thông qua chơi'


def test_exact_passage_match_is_candidate_not_token_overlap():
    passages = [
        {"passage_id": "p1", "content": "Học thông qua chơi giúp trẻ sáng tạo."},
        {"passage_id": "p2", "content": "Một câu hoàn toàn khác."},
    ]
    assert exact_passage_matches("Học thông qua chơi", passages) == ["p1"]
    assert exact_passage_matches("Học sáng tạo", passages) == []
