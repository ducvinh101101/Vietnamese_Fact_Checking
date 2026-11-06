"""User regression: school fire must not retrieve a different fatality in Cu Chi."""
from datetime import date
from pathlib import Path

from src.query_enrichment import resolve_time_scope
from src.schemas import Evidence, RetrievedEvidence
from src.temporal_gate import TemporalGateRetriever
from src.topical_rerank import eligible, TopicalRerankRetriever
from src.web_retriever import extract_passages


CLAIM = 'Nạn nhân tử vong trong vụ cháy trường Kim Liên là học sinh lớp 6'
WRONG = 'Người đàn ông chết tại chỗ sau tiếng động mạnh ở huyện Củ Chi. Nạn nhân tử vong tại chỗ, vụ việc đang được điều tra.'


def test_generic_fatality_words_do_not_replace_school_identity():
    assert not eligible(CLAIM, WRONG)
    assert eligible(CLAIM, 'Nạn nhân trong vụ cháy Trường THCS Kim Liên là học sinh lớp 6.')
    assert not eligible(CLAIM, 'Nạn nhân tử vong trong vụ cháy trường Kim Đồng là học sinh lớp 6.')


def test_fire_event_gets_time_gate_without_user_setting_reference_date():
    scope = resolve_time_scope(CLAIM, date(2026, 11, 6))
    assert scope.kind == 'today' and scope.start == date(2026, 10, 27)
    class Local:
        def search(self, *_):
            return [RetrievedEvidence(Evidence('old', 'old', WRONG, published_at='2023-03-29'), 100)]
    gate = TemporalGateRetriever(Local(), as_of=date(2026, 11, 6), window_today=10)
    assert not gate.search(CLAIM)
    assert gate.last_dropped_stale == 1


def test_copied_short_headline_is_not_lost_outside_article_header():
    html = f'<meta property="og:title" content="{CLAIM}"><header><h1>{CLAIM}</h1></header><article><p>Bối cảnh khác. ' + 'Thông tin bổ sung. ' * 20 + '</p></article>'
    _, passages = extract_passages(html, 120, 800, 3, query=CLAIM)
    assert passages[0] == CLAIM


def test_wrong_local_article_is_absent_from_final_candidates():
    class Inner:
        def search(self, *_):
            return [RetrievedEvidence(Evidence('old', 'old', WRONG), 100),
                    RetrievedEvidence(Evidence('web-good', 'web-good', CLAIM), 0.1)]
    items = TopicalRerankRetriever(Inner()).search(CLAIM, 5)
    assert [item.evidence.passage_id for item in items] == ['web-good']
