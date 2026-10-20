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
    body = http.get(f'/cases/{case.id}/gaps').json()
    assert body['total'] == len(body['gaps'])
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


def test_rank_returns_every_gap_and_marks_the_first_five():
    gaps = [Gap(id=f'g{index}', section='D', field=f'f{index}', message='synthetic',
                fix_hint='synthetic', severity='warning' if index % 2 else 'blocking')
            for index in range(8)]
    ranked = rank_gaps(gaps)
    assert [gap.id for gap in ranked] == [gap.id for gap in gaps if gap.severity == 'blocking'] + [
        gap.id for gap in gaps if gap.severity == 'warning']
    assert len(ranked) == 8
    assert [gap.priority for gap in ranked] == [True, True, True, True, True, False, False, False]
