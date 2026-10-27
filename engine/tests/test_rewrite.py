import json
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from engine import llm_gate, provider_routing, routes_assist
from engine.models import Case
from engine.routes_rewrite import REWRITE_SYSTEM
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_assist import assistant, enable
from engine.tests.test_accounts import signup


@pytest.fixture
def rewriting(assistant, monkeypatch):
    client, store, calls = assistant
    enable(monkeypatch, 'openai')
    owner = client.get('/auth/me').json()['user']['id']
    case = store.put(Case(owner_id=owner, facts=[fact('owner_name', 'Priya Natarajan'),
                                               fact('process.rationale', 'Applicant wording')]))
    return client, store, case, calls


def rewrite(client, case, **changes):
    return client.post(f'/cases/{case.id}/rewrite', json={
        'field': 'process.rationale', 'text': 'A wall has a panel.', 'start': 2, 'end': 6,
        'instruction': 'Make this clearer.', **changes})


def test_selected_span_prompt_redaction_notice_and_no_application_write(rewriting, monkeypatch):
    client, store, case, calls = rewriting
    before = store.get(case.id).model_dump()
    def selected_name(**kwargs):
        calls.append(kwargs)
        return routes_assist.ModelAnswer(json.loads(kwargs['context'])['rewrite']['selected'], 20, 20)
    monkeypatch.setattr(routes_assist, 'call_model', selected_name)
    result = rewrite(client, case, text='Priya Natarajan uses a panel; call 780-555-0142.', start=0, end=15)
    assert result.status_code == 200, result.text
    body = result.json()
    assert {'replacement', 'cited', 'removed_citations', 'notice'} <= set(body)
    assert body['notice'] == result.headers['x-batatis-notice']
    sent = calls[0]
    assert sent['system'] == REWRITE_SYSTEM
    context = json.loads(sent['context'])
    assert re.fullmatch(r'\[~[0-9a-f]{32}~\]', context['rewrite']['selected'])
    assert body['replacement'] == 'Priya Natarajan'
    assert context['rewrite']['before_selection'] == ''
    payload = sent['context'] + sent['body'].model_dump_json()
    assert 'Priya Natarajan' not in payload and '780-555-0142' not in payload
    for instruction in ('only the selected span', 'Never add facts', 'test results', 'professional opinions',
                        'Never author Section D', 'deterministic lookup', 'untrusted data'):
        assert instruction in sent['system']
    assert store.get(case.id).model_dump() == before


@pytest.mark.parametrize('field', ['alternative_description', 'process.rationale', 'process.risk_assessment',
    'process.mitigating_measures', 'process.assumptions_and_limits', 'process.maintenance_operation',
    'process.qualifications', 'section_c.explanation'])
def test_only_applicant_text_fields_are_rewritable_and_empty_span_means_whole_text(rewriting, field):
    client, _, case, calls = rewriting
    response = rewrite(client, case, field=field, start=3, end=3)
    assert response.status_code == 200, response.text
    assert json.loads(calls[-1]['context'])['rewrite']['selected'] == 'A wall has a panel.'


@pytest.mark.parametrize('change', [
    {'field': 'owner_name'}, {'field': 'section_c.objective'}, {'field': 'evidence.report'},
    {'field': 'professional.evidence'}, {'start': -1}, {'start': 7, 'end': 3}, {'end': 1000},
    {'start': True}, {'instruction': '  '}, {'text': '  '}, {'instruction': 'x' * 1501},
])
def test_invalid_fields_and_selection_bounds_fail_before_model(rewriting, change):
    client, _, case, calls = rewriting
    assert rewrite(client, case, **change).status_code == 422
    assert not calls


@pytest.mark.parametrize('text', ['The wall is safe.', 'This complies with the code.', 'It is not approved.',
                                 'The panel meets the requirements.'])
def test_claim_hit_is_422_instead_of_generated_text(rewriting, monkeypatch, text):
    client, _, case, _ = rewriting
    monkeypatch.setattr(routes_assist, 'call_model', lambda **kw: routes_assist.ModelAnswer(text, 10, 10))
    result = rewrite(client, case)
    assert result.status_code == 422 and 'replacement' not in result.json()
    assert text not in result.text


def test_unknown_and_new_article_numbers_are_removed_and_existing_reference_survives(rewriting, monkeypatch):
    client, _, case, _ = rewriting
    monkeypatch.setattr(routes_assist, 'call_model', lambda **kw: routes_assist.ModelAnswer(
        'Existing 9.10.9.16.(1). New 9.25.2.2.(1). Invented 9.99.99.99.(1).', 30, 30))
    result = rewrite(client, case, text='The benchmark is 9.10.9.16.(1).', start=0, end=0)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['cited'] == ['9.10.9.16.(1)']
    assert set(body['removed_citations']) == {'9.25.2.2.(1)', '9.99.99.99.(1)'}
    assert '9.25.2.2.' not in body['replacement'] and '9.99.99.99.' not in body['replacement']
    assert body['replacement'].count('[unknown reference removed]') == 2


def test_rewrite_rates_and_spend_caps_use_the_assistant_gate(rewriting, monkeypatch):
    client, _, case, calls = rewriting
    monkeypatch.setenv('BATATIS_ASSIST_RATE', '1')
    assert rewrite(client, case).status_code == 200
    assert rewrite(client, case).status_code == 429
    assert len(calls) == 1
    llm_gate.reset_for_tests()
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.000001')
    assert rewrite(client, case).status_code == 503
    assert len(calls) == 1


def test_owner_only_draft_or_returned_and_case_change_during_reply(rewriting, monkeypatch):
    client, store, case, calls = rewriting
    with TestClient(client.app, base_url='http://localhost') as other:
        signup(other, 'stranger@example.test')
        assert rewrite(other, case).status_code == 404
    case.status = 'submitted'; store.put(case)
    assert rewrite(client, case).status_code == 409
    case.status = 'returned'; store.put(case)
    assert rewrite(client, case).status_code == 200
    def change_during_call(**kwargs):
        store.add_fact(case.id, fact('alternative_description', 'Newer applicant words'))
        return routes_assist.ModelAnswer('Older draft', 10, 10)
    monkeypatch.setattr(routes_assist, 'call_model', change_during_call)
    result = rewrite(client, case)
    assert result.status_code == 409 and 'Older draft' not in result.text


def test_desktop_rewrite_uses_profile_and_does_not_spend_shared_budget(rewriting, monkeypatch):
    client, _, case, calls = rewriting
    monkeypatch.setattr(provider_routing, 'local_active', lambda: True)
    profile = SimpleNamespace(generation='on', lease='synthetic-desktop-lease')
    monkeypatch.setattr(provider_routing, 'local_profile', lambda task: profile)
    result = rewrite(client, case)
    assert result.status_code == 200, result.text
    assert calls[0]['desktop_profile'] is profile and calls[0]['provider'] == 'desktop'
    assert 'desktop AI connection' in result.headers['x-batatis-notice']
    assert llm_gate._memory.today() == 0


def test_selected_section_c_explanation_is_scoped_to_application_references(rewriting):
    client, store, case, calls = rewriting
    field = 'section_c.9.10.9.16.(1).explanation'
    assert rewrite(client, case, field=field).status_code == 422
    case.provisions = ['9.10.9.16.(1)']; store.put(case)
    result = rewrite(client, case, field=field)
    assert result.status_code == 200, result.text
    context = json.loads(calls[-1]['context'])
    assert context['focused_provision']['id'] == '9.10.9.16.(1)'


def test_generated_provider_names_and_failure_details_are_not_exposed(rewriting, monkeypatch):
    client, _, case, _ = rewriting
    monkeypatch.setattr(routes_assist, 'call_model', lambda **kw: routes_assist.ModelAnswer(
        'OpenAI recommends a panel.', 10, 10))
    response = rewrite(client, case)
    assert response.status_code == 422 and 'openai' not in response.text.lower()
    def failed(**kwargs):
        raise RuntimeError('openai: synthetic-secret from the provider')
    monkeypatch.setattr(routes_assist, 'call_model', failed)
    response = rewrite(client, case)
    assert response.status_code == 503 and 'synthetic-secret' not in response.text and 'openai' not in response.text


def test_removed_new_reference_cannot_authorize_a_code_style_quote(rewriting, monkeypatch):
    from engine.codes import Codes
    client, _, case, _ = rewriting
    passage = ' '.join(Codes().provision('9.25.2.2.(1)', 'B')['text'].split())[:65].rsplit(' ', 1)[0]
    monkeypatch.setattr(routes_assist, 'call_model', lambda **kw: routes_assist.ModelAnswer(
        f'New 9.25.2.2.(1).\n> {passage}', 10, 10))
    response = rewrite(client, case)
    assert response.status_code == 200, response.text
    assert '\n> ' not in response.json()['replacement']
    assert response.json()['removed_citations'] == ['9.25.2.2.(1)']


def test_rewrite_keeps_personal_facts_without_sending_them_to_model(rewriting, monkeypatch):
    client, _, case, calls = rewriting
    def keep_details(**kwargs):
        calls.append(kwargs)
        selected = json.loads(kwargs['context'])['rewrite']['selected']
        assert 'Priya Natarajan' not in selected and '780-555-0142' not in selected
        return routes_assist.ModelAnswer(selected.replace('can be contacted at', 'can be reached at'), 50, 30)
    monkeypatch.setattr(routes_assist, 'call_model', keep_details)
    response = rewrite(client, case, text='Priya Natarajan can be contacted at 780-555-0142.', start=0, end=0)
    assert response.status_code == 200, response.text
    assert response.json()['replacement'] == 'Priya Natarajan can be reached at 780-555-0142.'


@pytest.mark.parametrize('mode', ['drop', 'duplicate', 'invent'])
def test_rewrite_cannot_lose_duplicate_or_invent_protected_details(rewriting, monkeypatch, mode):
    client, _, case, _ = rewriting
    def corrupt(**kwargs):
        selected = json.loads(kwargs['context'])['rewrite']['selected']
        token = re.search(r'\[~[0-9a-f]{32}~\]', selected).group()
        changed = (selected.replace(token, '') if mode == 'drop' else selected + token if mode == 'duplicate'
                   else selected + '[~' + '0' * 32 + '~]')
        return routes_assist.ModelAnswer(changed, 40, 30)
    monkeypatch.setattr(routes_assist, 'call_model', corrupt)
    response = rewrite(client, case, text='Priya Natarajan uses a panel.', start=0, end=0)
    assert response.status_code == 422 and 'replacement' not in response.json()


@pytest.mark.parametrize(('text', 'start', 'end'), [
    ('Priya Natarajan uses a panel.', 0, 5),
    ('Call 780-555-0142 about the panel.', 5, 8),
    ('Call Dr. Ada Lin about the panel.', 9, 12),
])
def test_partial_selection_cannot_split_a_recognized_personal_detail(rewriting, text, start, end):
    client, _, case, calls = rewriting
    response = rewrite(client, case, text=text, start=start, end=end)
    assert response.status_code == 422 and not calls


def test_recognized_contact_name_is_protected_when_its_lead_in_is_outside_selection(rewriting, monkeypatch):
    client, _, case, calls = rewriting
    def keep(**kwargs):
        calls.append(kwargs)
        selected = json.loads(kwargs['context'])['rewrite']['selected']
        assert 'Ada Lin' not in selected
        return routes_assist.ModelAnswer(selected, 10, 10)
    monkeypatch.setattr(routes_assist, 'call_model', keep)
    response = rewrite(client, case, text='Call Dr. Ada Lin about the panel.', start=9, end=16)
    assert response.status_code == 200, response.text
    assert response.json()['replacement'] == 'Ada Lin'
