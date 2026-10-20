"""Evidence gaps follow the departure. One article does not become one slot per pair."""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.completeness import Gap
from engine.evidence_gaps import evidence_provision_ids, rank_gaps
from engine.models import Case, Jurisdiction, SectionCRow
from engine.professional import ProfessionalResult
from engine.section_d import EvidencePlanItem, SectionDPlan
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact

DEPARTURE = '9.27.5.1.(1)'
AFFECTED = '9.27.5.1.(2)'
SUPPORTING = (
    '9.36.2.6.(1)', '9.23.13.1.(2)', '9.25.5.1.(1)', '9.25.5.1.(4)',
    '9.27.3.4.(1)', '9.10.17.10.(1)')
CITING = ('9.27.3.3.(1)', '9.25.5.2.(1)')
TYPES = (
    "manufacturer's literature", 'ISO 17025 test report', 'evaluation',
    'CCMC evaluation', 'registered professional opinion')
# One real-looking pair plus synthetic stand-ins. The stand-ins are not code attributions.
PAIRS = [('F20', 'OS2.1')] + [(f'P{index}', f'Q{index}') for index in range(23)]


class FakeCodes:
    db_path = 'synthetic'

    def provision(self, pid, division='B'):
        return {'id': pid, 'division': division, 'citation': f'synthetic Div {division} {pid}',
                'level': 'sentence', 'attributions': [], 'intents': [], 'intent_comparison': [],
                'attribution_status': None, 'children': [], 'text': 'synthetic', 'pdf_page': 1,
                'pdf_page_end': 1, 'article_title': 'synthetic'}

    def citation(self, pid, division='B'):
        return self.provision(pid, division)['citation']


def _item(provision, function, objective):
    return EvidencePlanItem(
        id=f'{provision}-{function}-{objective}', provision_id=provision, citation='synthetic citation',
        attribution_status='direct', objective=objective, function=function, performance_issue='synthetic issue',
        recommended_types=TYPES)


def _plan_items():
    items = [_item(DEPARTURE, function, objective) for function, objective in PAIRS]
    items.append(_item(AFFECTED, 'F20', 'OS2.3'))
    items.extend(_item(pid, 'F20', 'OS2.1') for pid in SUPPORTING + CITING)
    return items


def _rows(provision_ids):
    return [SectionCRow(provision_id=pid, citation=f'synthetic Div B {pid}',
                        attribution_status='no row in the attribution table', pairs=[], intents=[])
            for pid in provision_ids]


def _roles():
    labels = [(DEPARTURE, 'departure'), (AFFECTED, 'affected')]
    labels += [(pid, 'supporting') for pid in SUPPORTING]
    labels += [(pid, 'citing') for pid in CITING]
    return [fact('provision_role', f'{role}:{pid}') for pid, role in labels]


@pytest.fixture
def client(tmp_path, monkeypatch):
    def fake_plan(case, codes, documents=None):
        return SectionDPlan(items=_plan_items(), notices=[])

    monkeypatch.setattr('engine.completeness.section_d_plan', fake_plan)
    monkeypatch.setattr('engine.completeness.section_c_rows', lambda provision_ids, codes: _rows(provision_ids))
    monkeypatch.setattr('engine.completeness.validate_text', lambda *args, **kwargs: {'errors': []})
    monkeypatch.setattr('engine.completeness.process_fields', lambda case, codes: [])
    monkeypatch.setattr(
        'engine.completeness.professional_involvement',
        lambda case, codes: ProfessionalResult(required='no', general_required='no', reasons=[], questions=[]))
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store, FakeCodes())), store


def _case(store):
    provisions = [DEPARTURE, AFFECTED, *SUPPORTING, *CITING]
    return store.put(Case(
        provisions=provisions,
        section_c=_rows(provisions),
        jurisdiction=Jurisdiction(id='alberta-other', name='Synthetic AHJ'),
        facts=[fact(name, 'synthetic') for name in (
            'owner_name', 'application_date', 'civic_address', 'legal_description',
            'representative', 'mailing_address', 'alternative_description', 'scope')] + _roles()))


def _evidence(gaps):
    return [gap for gap in gaps if str(gap.get('field', '')).startswith('evidence.')]


def test_one_departed_article_is_a_handful_of_gaps_and_every_gap_stays(client):
    http, store = client
    case = _case(store)
    listed = http.get(f'/cases/{case.id}/gaps')
    assert listed.status_code == 200 and isinstance(listed.json(), list)
    assert listed.headers['x-gap-total'] == str(len(listed.json()))
    envelope = http.get(f'/cases/{case.id}/gaps', params={'shape': 'v2'})
    assert envelope.status_code == 200
    body = envelope.json()
    assert body['total'] == len(body['gaps']) == len(listed.json())
    assert body['gaps'] == listed.json()
    assert http.get(f'/cases/{case.id}/gaps', params={'shape': 'v1'}).status_code == 422
    assert len({gap['id'] for gap in body['gaps']}) == body['total']
    evidence = _evidence(body['gaps'])
    assert 1 <= len(evidence) <= 5
    assert {gap['provision_id'] for gap in evidence} == {DEPARTURE, AFFECTED}
    departure = next(gap for gap in evidence if gap['provision_id'] == DEPARTURE)
    assert len(departure['pairs']) == 24
    assert departure['field'] == f'evidence.{DEPARTURE}'
    assert departure['evidence_types'] == list(TYPES)
    assert departure['fix_hint'].count('F20') == 0
    assert not any(gap['field'].endswith(('.date', '.responsible_party', '.title', '.document', '.person'))
                   for gap in body['gaps'])
    assert [gap['priority'] for gap in body['gaps']] == [index < 5 for index in range(body['total'])]
    blocking = [gap for gap in body['gaps'] if gap['severity'] == 'blocking']
    warning = [gap for gap in body['gaps'] if gap['severity'] == 'warning']
    assert body['gaps'][:len(blocking)] == blocking
    assert body['gaps'][len(blocking):] == warning


def test_unlabelled_provisions_stay_in_scope_and_labels_drop_the_citing_chain():
    provisions = [DEPARTURE, *SUPPORTING]
    assert evidence_provision_ids(Case(provisions=provisions)) == provisions
    labelled = Case(provisions=provisions, facts=_roles())
    assert evidence_provision_ids(labelled) == [DEPARTURE]
    proposed = Case(provisions=provisions, facts=[
        fact('provision_role', f'supporting:{DEPARTURE}', kind='proposed', status='unconfirmed')])
    assert evidence_provision_ids(proposed) == provisions


def test_article_departure_covers_its_sentences_and_a_citing_article_does_not():
    from engine.evidence_gaps import provision_in_scope, scoped_plan_items

    article = '9.27.5.1.'
    citing = '9.27.3.3.'
    case = Case(provisions=[article, citing], facts=[
        fact('provision_role', f'departure:{article}'),
        fact('provision_role', f'citing:{citing}'),
        fact('provision_role', f'citing:{article}(2)'),
    ])
    items = [
        _item(f'{article}(1)', 'F20', 'OS2.1'),
        _item(f'{article}(2)', 'F20', 'OS2.3'),
        _item(f'{citing}(1)', 'F20', 'OS2.1'),
    ]
    assert provision_in_scope(case, f'{article}(1)')
    assert not provision_in_scope(case, f'{article}(2)')
    assert [item.provision_id for item in scoped_plan_items(case, items)] == [f'{article}(1)']


# Synthetic reference wording. These ids are the manufacturer shortlist's no-departure
# rows. The sentences are not quotations of the code.
_CHAIN = {
    DEPARTURE: 'Fasten cladding to framing. See Article 9.27.3.3. and Sentence 9.25.5.1.(1).',
    '9.27.3.3.': 'Sheathing membrane. See Sentence 9.27.3.4.(1) and Sentence 9.25.5.2.(1).',
    '9.27.3.3.(1)': 'Sheathing membrane sentence.',
    '9.25.5.1.(1)': 'See Article 9.36.2.6. and Sentence 9.23.13.1.(2) and Sentence 9.10.17.10.(1).',
    '9.27.3.4.(1)': 'Joint detail.',
    '9.25.5.2.(1)': 'Position of the barrier.',
    '9.36.2.6.': 'Energy efficiency article.',
    '9.36.2.6.(1)': 'Energy efficiency sentence.',
    '9.23.13.1.(2)': 'Bracing.',
    '9.10.17.10.(1)': 'Foamed plastic.',
}
_ARTICLES = {'9.27.3.3.': '9.27.3.3.(1)', '9.36.2.6.': '9.36.2.6.(1)'}
_DEPARTURE_PAIRS = (('F20', 'OS2.1'), ('F20', 'OS2.3'), ('F20', 'OH1.1'), ('F20', 'OH1.2'), ('F20', 'OH1.3'))


class _ChainCodes:
    """One departed sentence whose text names the rest of the shortlist."""

    db_path = 'synthetic'

    def provision(self, pid, division='B'):
        if pid not in _CHAIN:
            return None
        child = _ARTICLES.get(pid)
        pairs = _DEPARTURE_PAIRS if pid == DEPARTURE else (('F20', 'OS2.1'),)
        return {
            'id': pid, 'division': division, 'citation': f'synthetic Div {division} {pid}',
            'level': 'article' if child else 'sentence',
            'attributions': [_pair_row(pid, function, objective) for function, objective in pairs],
            'intents': [], 'intent_comparison': [],
            'attribution_status': {'status': 'direct', 'root_provision': None},
            'children': [{'id': child, 'level': 'sentence'}] if child else [],
            'text': _CHAIN[pid], 'pdf_page': 1, 'pdf_page_end': 1, 'article_title': 'synthetic',
        }

    def citation(self, pid, division='B'):
        found = self.provision(pid, division)
        return found['citation'] if found else None

    def definition(self, code):
        return None


def _pair_row(pid, function, objective):
    return {'provision_id': pid, 'fs': [function], 'objectives': [objective], 'bracket': f'[{function}-{objective}]',
            'clauses': [], 'application_note': None, 'table_id': 'synthetic', 'pdf_page': 1}


@pytest.fixture
def chain_client(tmp_path, monkeypatch):
    monkeypatch.setattr('engine.completeness.validate_text', lambda *args, **kwargs: {'errors': []})
    monkeypatch.setattr('engine.completeness.process_fields', lambda case, codes: [])
    monkeypatch.setattr(
        'engine.completeness.professional_involvement',
        lambda case, codes: ProfessionalResult(required='no', general_required='no', reasons=[], questions=[]))
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store, _ChainCodes())), store


def test_added_departure_pulls_the_citing_chain_and_gaps_stay_few(chain_client):
    http, store = chain_client
    case = store.put(Case(
        jurisdiction=Jurisdiction(id='alberta-other', name='Synthetic AHJ'),
        facts=[fact(name, 'synthetic') for name in (
            'owner_name', 'application_date', 'civic_address', 'legal_description',
            'representative', 'mailing_address', 'alternative_description', 'scope')]))
    posted = http.post(f'/cases/{case.id}/section-d', json={'provisions': [DEPARTURE]})
    assert posted.status_code == 200, posted.text
    stored = store.get(case.id)
    assert stored.provisions[0] == DEPARTURE
    citing = stored.provisions[1:]
    assert set(citing) >= {
        '9.27.3.3.', '9.25.5.1.(1)', '9.27.3.4.(1)', '9.25.5.2.(1)',
        '9.36.2.6.', '9.23.13.1.(2)', '9.10.17.10.(1)'}
    roles = {fact.value for fact in stored.facts if fact.field == 'provision_role'}
    assert f'departure:{DEPARTURE}' in roles
    assert all(f'citing:{pid}' in roles for pid in citing)
    listed = http.get(f'/cases/{stored.id}/gaps')
    assert isinstance(listed.json(), list)
    assert listed.headers['x-gap-total'] == str(len(listed.json()))
    evidence = _evidence(listed.json())
    assert listed.json() == evidence
    assert len(evidence) == 1
    assert {gap['provision_id'] for gap in evidence} == {DEPARTURE}
    assert len(evidence[0]['pairs']) == len(_DEPARTURE_PAIRS)
    assert len(stored.provisions) > len(evidence)
    assert not any(gap['field'].endswith(('.date', '.responsible_party', '.title', '.document', '.person'))
                   for gap in listed.json())
    envelope = http.get(f'/cases/{stored.id}/gaps', params={'shape': 'v2'}).json()
    assert envelope['total'] == len(listed.json()) and envelope['gaps'] == listed.json()


def test_rank_returns_every_gap_and_marks_the_first_five():
    gaps = [Gap(id=f'g{index}', section='D', field=f'f{index}', message='synthetic',
                fix_hint='synthetic', severity='warning' if index % 2 else 'blocking')
            for index in range(8)]
    ranked = rank_gaps(gaps)
    assert [gap.id for gap in ranked] == [gap.id for gap in gaps if gap.severity == 'blocking'] + [
        gap.id for gap in gaps if gap.severity == 'warning']
    assert len(ranked) == 8
    assert [gap.priority for gap in ranked] == [True, True, True, True, True, False, False, False]
