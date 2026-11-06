from datetime import date

from src.minimal_pair import MinimalPairVerifier
from src.schemas import Evidence, RetrievedEvidence, VerificationResult
from src.topical_rerank import TopicalRerankRetriever
from src.fusion_retriever import FusionRetriever
from src.temporal_gate import TemporalGateRetriever
from src.verbatim import verbatim_span
from src.web_retriever import extract_passages


CLAIM = 'Google sẽ đánh giá ứng dụng từ năm 2027.'
MULTI = CLAIM + ' Những ứng dụng tối ưu tốt sẽ được ưu tiên hiển thị.'


class NEI:
    def verify(self, claim, items):
        return VerificationResult('NOT_ENOUGH_INFO', 0.7, [], 'model abstained')


def web(text, pid='web-a', score=1):
    return RetrievedEvidence(Evidence(pid, pid, text, url=f'https://dantri.com.vn/{pid}',
                                       published_at='2026-11-03'), score)


def test_complete_multi_sentence_span_is_detected_with_surrounding_sentences():
    assert verbatim_span(MULTI, 'Thông tin mở đầu. ' + MULTI + ' Bối cảnh bổ sung.') == MULTI
    assert verbatim_span(MULTI, CLAIM) is None


def test_no_substring_support_inside_negation_attribution_or_qualification():
    claim = 'Doanh nghiệp tăng giá điện lên 20 phần trăm'
    assert verbatim_span(claim, 'Tin giả cho rằng ' + claim + '.') is None
    assert verbatim_span(claim, 'Chưa xác nhận thông tin ' + claim + '.') is None
    assert verbatim_span(claim, claim + ' nếu được phê duyệt.') is None


def test_no_support_for_changed_number_negation_unit_or_order():
    assert verbatim_span(CLAIM.replace('2027', '2028'), CLAIM) is None
    assert verbatim_span(CLAIM.replace('sẽ', 'sẽ không'), CLAIM) is None
    assert verbatim_span('Giá vàng tăng hơn 8% so với hôm trước.', 'Giá vàng tăng hơn 8 so với hôm trước.') is None
    assert verbatim_span(MULTI, 'Những ứng dụng tối ưu tốt sẽ được ưu tiên hiển thị. ' + CLAIM) is None


def test_short_copied_sentence_survives_minimum_length_and_ranks_first():
    noise = 'Google công bố thông tin về ứng dụng, điện thoại và cửa hàng. ' * 4
    _, passages = extract_passages(f'<article><p>{noise}</p><p>{CLAIM}</p></article>', 120, 800, 3, query=CLAIM)
    assert passages[0] == CLAIM


def test_outside_article_title_and_standfirst_are_available_together():
    title = 'Google thay đổi cách đánh giá ứng dụng'
    description = 'Ứng dụng trên điện thoại gập sẽ được đánh giá theo tiêu chí mới từ năm 2027.'
    html = f'<h1>{title}</h1><meta property="og:description" content="{description}"><article><p>Thông tin khác. ' + 'Bối cảnh. ' * 20 + '</p></article>'
    query = title + '. ' + description
    _, passages = extract_passages(html, 120, 800, 3, query=query)
    assert any(verbatim_span(query, p) is not None for p in passages)


def test_exact_span_beats_keyword_stuffed_passage_in_same_article_and_other_articles():
    claim = MULTI
    exact = web(claim, 'web-exact', 0.01)
    noisy = web('Google ứng dụng đánh giá năm 2027 hiển thị tối ưu ưu tiên. ' * 7, 'web-noise', 100)
    class Inner:
        def search(self, *_):
            return [noisy, exact]
    assert TopicalRerankRetriever(Inner()).search(claim, 1)[0].evidence.passage_id == 'web-exact'


def test_abstaining_model_with_full_web_span_gets_grounded_citation():
    checker = MinimalPairVerifier(NEI(), complete_web_span=True)
    result = checker.verify(MULTI, [web('Thông tin mở đầu. ' + MULTI)])
    assert result.label == 'SUPPORTED' and result.evidence_ids == ['web-a']
    assert checker.last_base_result.label == 'NOT_ENOUGH_INFO'
    assert checker.last_reason == 'complete_verbatim_support'


def test_partial_multi_claim_and_qualified_substring_remain_nei():
    checker = MinimalPairVerifier(NEI(), complete_web_span=True)
    assert checker.verify(MULTI, [web(CLAIM)]).label == 'NOT_ENOUGH_INFO'
    claim = 'Doanh nghiệp tăng giá điện lên 20 phần trăm'
    assert checker.verify(claim, [web('Tin giả cho rằng ' + claim)]).label == 'NOT_ENOUGH_INFO'


def test_complete_web_span_does_not_upgrade_local_only_evidence():
    checker = MinimalPairVerifier(NEI(), complete_web_span=True)
    assert checker.verify(MULTI, [web(MULTI, 'local-a')]).label == 'NOT_ENOUGH_INFO'


def test_web_candidates_survive_local_fusion_until_date_filtering():
    # With an early top-20 fusion cap, the relevant web document at rank 15 is
    # discarded even though all local documents would later fail the date gate.
    class Static:
        def __init__(self, items):
            self.items = items
        def search(self, _, top_k):
            return self.items[:top_k]
    claim = 'Giá xăng tăng từ chiều nay'
    local = [RetrievedEvidence(Evidence(f'l{i}', f'l{i}', claim, published_at='2020-01-01',
                                        url=f'https://dantri.com.vn/old-{i}'), 100 - i) for i in range(20)]
    online = [web('Chủ đề khác về điện thoại và phần mềm. ' * 5, f'web-{i}', 1 - i / 100) for i in range(14)]
    online.append(web(claim, 'web-target', 0.8))
    gate = TemporalGateRetriever(FusionRetriever(Static(local), Static(online), candidate_k=20),
                                 as_of=date(2026, 11, 3), candidate_k=40, force_reference=True)
    result = TopicalRerankRetriever(gate, candidate_k=40).search(claim, 3)
    assert result[0].evidence.passage_id == 'web-target'
