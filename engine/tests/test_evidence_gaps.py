"""Evidence gaps are one per provision, and applicant evidence closes the ones it names."""
from engine.evidence_gaps import evidence_covers_item, group_evidence_gaps, list_documents, uncovered_items
from engine.models import EvidenceItem
from engine.section_d import EvidencePlanItem, SectionDPlan


def item(provision, function, objective, status='not provided'):
    return EvidencePlanItem(
        id=f'{provision}-{function}-{objective}', provision_id=provision, citation='synthetic citation',
        attribution_status='direct', objective=objective, function=function, performance_issue='synthetic issue',
        recommended_types=("manufacturer's literature",), status=status)


def test_nineteen_pairs_on_one_provision_are_one_gap():
    provision = '9.99.1.1.(1)'
    items = [item(provision, f'P{i}', f'Q{i}') for i in range(19)]
    items.append(item('9.99.1.2.(1)', 'P1', 'Q1'))
    gaps = group_evidence_gaps(items)
    assert [gap.provision_id for gap in gaps] == [provision, '9.99.1.2.(1)']
    grouped = gaps[0]
    assert grouped.rule == 'evidence' and grouped.severity == 'blocking'
    assert grouped.field == f'evidence.{provision}'
    assert len(grouped.pairs) == 19
    assert [(pair.function, pair.objective) for pair in grouped.pairs] == [(f'P{i}', f'Q{i}') for i in range(19)]
    assert 'compli' not in grouped.fix_hint.casefold() and 'verified' not in grouped.fix_hint.casefold()


def test_provision_evidence_closes_every_pair_and_a_pair_closes_one():
    provision = '9.99.1.1.(1)'
    items = [item(provision, 'P1', 'Q1'), item(provision, 'P2', 'Q2')]
    whole = EvidenceItem(provision_id=provision, description='Applicant report', evidence_type="manufacturer's literature",
                         status='evidence_listed')
    assert uncovered_items(items, [whole]) == []
    one = EvidenceItem(provision_id=provision, objective='Q1', function='P1', description='Applicant note',
                       evidence_type='evaluation', status='evidence_listed')
    left = uncovered_items(items, [one])
    assert [item.function for item in left] == ['P2']
    assert len(group_evidence_gaps(left)) == 1
    assert evidence_covers_item(items[0], [EvidenceItem(description='no provision', status='evidence_listed')]) is False


def test_file_backed_plan_status_stays_covered_without_an_evidence_item():
    """``provided`` and ``evidence_listed`` both mean the plan item is already listed."""
    done = item('9.99.1.1.(1)', 'P1', 'Q1', status='provided')
    listed = EvidencePlanItem.model_construct(**{**done.model_dump(), 'status': 'evidence_listed'})
    legacy = EvidenceItem.model_construct(
        provision_id='9.99.1.1.(1)', description='Legacy listing', status='provided')
    assert uncovered_items([done], []) == []
    assert uncovered_items([listed], []) == []
    assert uncovered_items([item('9.99.1.1.(1)', 'P1', 'Q1')], [legacy]) == []


def test_missing_objective_is_one_warning_and_does_not_invent_a_pair():
    blank = EvidencePlanItem(
        id='scope', provision_id='9.99.1.3.(1)', citation='synthetic citation',
        attribution_status='no row in the attribution table', attribution='not_attributed',
        objective=None, function=None, performance_issue='synthetic issue',
        recommended_types=("manufacturer's literature",))
    [gap] = group_evidence_gaps([blank])
    assert gap.severity == 'warning' and gap.pairs == [] and gap.rule == 'evidence_scope'
    assert gap.evidence_types == ["manufacturer's literature"]
    assert gap.fix_hint == (
        "The code's objectives table has no entry for Sentence 9.99.1.3.(1). "
        "If your design relies on it, ask your designer which objective it serves.")
    assert 'F' not in gap.fix_hint and 'inferred' not in gap.fix_hint


def test_gap_text_uses_pair_wording_and_not_bare_codes():
    named = EvidencePlanItem(
        id='words', provision_id='3.1.9.1.(1)', citation='synthetic citation',
        attribution_status='direct', objective='OS1.2', function='F03',
        function_text='synthetic function wording', objective_text='synthetic objective wording',
        performance_issue='synthetic issue', recommended_types=("manufacturer's literature",))
    [gap] = group_evidence_gaps([named])
    assert gap.missing == ('documents for Sentence 3.1.9.1.(1): '
                           'synthetic function wording; synthetic objective wording.')
    assert gap.fix_hint == list_documents('3.1.9.1.(1)')
    assert 'F03-OS1.2' not in gap.missing and 'F03/OS1.2' not in gap.missing
    assert 'F03-OS1.2' not in gap.fix_hint and 'F03/OS1.2' not in gap.fix_hint
    assert gap.pairs[0].function_text == 'synthetic function wording'
    assert gap.pairs[0].objective_text == 'synthetic objective wording'


def test_plan_shape_round_trip_is_stable():
    plan = SectionDPlan(items=[item('9.99.1.1.(1)', 'P1', 'Q1')], notices=['synthetic'])
    assert group_evidence_gaps(plan.items)[0].pairs[0].function == 'P1'
