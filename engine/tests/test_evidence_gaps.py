"""GET /cases/{id}/gaps emits one evidence gap per provision, not one per pair."""
from engine.completeness import check_completeness
from engine.models import Case, Jurisdiction
from engine.professional import ProfessionalResult
from engine.section_d import EvidencePlanItem, SectionDPlan


def _item(provision, function, objective):
    return EvidencePlanItem(
        id=f'{provision}-{function}-{objective}', provision_id=provision, citation='synthetic citation',
        attribution_status='direct', objective=objective, function=function, performance_issue='synthetic issue',
        recommended_types=("manufacturer's literature",))


def test_three_uncovered_pairs_yield_one_evidence_gap(monkeypatch):
    provision = '9.99.1.1.(1)'
    items = [_item(provision, f'F0{index}', f'OS1.{index}') for index in range(1, 4)]
    monkeypatch.setattr('engine.completeness.process_fields', lambda case, codes: [])
    monkeypatch.setattr('engine.completeness.section_c_rows', lambda pids, codes: [
        type('Row', (), {'provision_id': provision, 'citation': 'synthetic citation'})()])
    monkeypatch.setattr(
        'engine.completeness.section_d_plan',
        lambda case, codes, docs=None: SectionDPlan(items=items, notices=[]))
    case = Case(
        provisions=[provision],
        jurisdiction=Jurisdiction(id='org', name='Accredited organisation', authority='Accredited organisation'))
    professional = ProfessionalResult(required='no', general_required='no', reasons=[], questions=[])
    gaps = check_completeness(case, object(), professional=professional)
    evidence = [gap for gap in gaps if gap.id == f'evidence:{provision}']
    assert len(evidence) == 1
    gap = evidence[0]
    assert gap.provision_id == provision
    assert gap.field == f'evidence.{provision}'
    assert [(pair.function, pair.objective) for pair in gap.pairs] == [
        ('F01', 'OS1.1'), ('F02', 'OS1.2'), ('F03', 'OS1.3')]
    assert sum(1 for item in gaps if item.provision_id == provision) == 1
