from datetime import date

import pytest

from src.gemini_gold import GeminiGoldClient
from src.llm_verifier import DEFAULT_MODEL, LLMVerifier
from src.minimal_pair import MinimalPairVerifier
from src.pipeline_output import build_pipeline_output
from src.schemas import Evidence, RetrievedEvidence
from src.verdict_guard import GuardedVerifier


CLAIM = 'AI thúc đẩy các nhà sản xuất phát triển chip tiên tiến có biên lợi nhuận cao.'


def items():
    return [RetrievedEvidence(Evidence('web-doc', 'web-p1', CLAIM,
                                       url='https://baovanhoa.vn/article.html'), 1.0)]


def test_explicit_model_takes_priority_and_models_prefix_is_normalized(monkeypatch):
    monkeypatch.setenv('GEMINI_MODEL', 'Gemini')
    assert LLMVerifier(model='models/gemma-4-26b-a4b-it', api_key='fake').model == DEFAULT_MODEL


def test_generic_family_name_is_rejected_before_network(monkeypatch):
    monkeypatch.setattr('src.gemini_gold.urlopen', lambda *_a, **_k: pytest.fail('Must reject configuration before HTTP'))
    result = LLMVerifier(model='Gemini', api_key='fake').verify(CLAIM, items())
    assert result.status == 'error' and result.error_code == 'configuration_error'
    assert result.evidence_ids == []
    assert 'concrete model ID' in result.explanation


@pytest.mark.parametrize('model', ['gemini', 'Gemini', 'Gemma', 'gemma-4'])
def test_gold_client_requires_concrete_model_name(model):
    with pytest.raises(ValueError, match='model ID'):
        GeminiGoldClient(model, api_key='fake')


@pytest.mark.parametrize('citations', [[], ['invented'], ['web-p1', 'invented']])
def test_missing_or_unknown_citations_are_errors_not_fabricated_first_passage(monkeypatch, citations):
    def predict(*_):
        return {'label': 'SUPPORTED', 'evidence_ids': citations, 'explanation': 'Confirmed'}, {}
    monkeypatch.setattr(GeminiGoldClient, 'predict', predict)
    result = LLMVerifier(model=DEFAULT_MODEL, api_key='fake').verify(CLAIM, items())
    assert result.status == 'error' and result.error_code == 'invalid_output'
    assert result.evidence_ids == []


def test_date_reference_is_not_hardcoded_and_valid_citation_is_preserved(monkeypatch):
    seen = {}
    def predict(self, record, prompt):
        seen.update(record)
        return {'label': 'SUPPORTED', 'evidence_ids': ['web-p1'], 'explanation': 'Confirmed'}, {}
    monkeypatch.setattr(GeminiGoldClient, 'predict', predict)
    verifier = LLMVerifier(model=DEFAULT_MODEL, api_key='fake', as_of=date(2026, 11, 6))
    result = verifier.verify(CLAIM, items())
    assert result.status == 'ok' and result.evidence_ids == ['web-p1']
    assert seen['as_of'] == '2026-11-06'


def test_provider_failure_remains_error_through_guard_and_verbatim_rules(monkeypatch):
    def fail(*_):
        raise RuntimeError('Gemini HTTP 400 invalid argument fake-key')
    monkeypatch.setattr(GeminiGoldClient, 'predict', fail)
    verifier = MinimalPairVerifier(GuardedVerifier(LLMVerifier(model=DEFAULT_MODEL, api_key='fake-key')),
                                   complete_web_span=True)
    result = verifier.verify(CLAIM, items())
    assert result.status == 'error' and result.evidence_ids == []
    assert 'fake-key' not in result.explanation
    output = build_pipeline_output(result, items())
    assert output['verdict']['status'] == 'error'
    assert output['retrieval']['retrieved_count'] == 1 and output['citations'] == []


def test_genuine_nei_is_not_a_provider_error(monkeypatch):
    monkeypatch.setattr(GeminiGoldClient, 'predict', lambda *_: ({'label': 'NOT_ENOUGH_INFO',
        'evidence_ids': [], 'explanation': 'The source does not establish margins.'}, {}))
    result = LLMVerifier(model=DEFAULT_MODEL, api_key='fake').verify(CLAIM, items())
    assert result.status == 'ok' and result.label == 'NOT_ENOUGH_INFO'
    assert 'status' not in build_pipeline_output(result, items())['verdict']
