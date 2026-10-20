import pytest
from pydantic import ValidationError

from engine.codes import Codes
from engine.models import Case, Fact, Source
from engine.section_c import section_c_rows
from engine.section_d import (ALTERNATIVE_EVIDENCE_TYPES, CONFIDENCE_LADDER, SupportingDocument,
                              section_d_plan, supporting_documents)


def test_every_confirmed_pair_gets_an_issue_and_ordered_types():
    case = Case(provisions=['9.10.9.16.(1)', '3.1.7.1.(1)'])
    plan = section_d_plan(case, Codes())
    expected = {(r.provision_id, p.function, p.objective) for r in section_c_rows(case.provisions, Codes()) for p in r.pairs}
    assert {(e.provision_id, e.function, e.objective) for e in plan.items} == expected
    assert all(e.recommended_types == CONFIDENCE_LADDER + ALTERNATIVE_EVIDENCE_TYPES for e in plan.items)
    assert all(e.status == 'needed' and e.responsible_party == '' and not e.attachments for e in plan.items)
    assert plan == section_d_plan(case, Codes())


def test_unconfirmed_or_forged_section_c_cannot_generate_evidence_claims():
    rows = section_c_rows(['9.10.9.16.(1)'], Codes())
    case = Case(section_c=rows)
    assert section_d_plan(case, Codes()).items == []
    case.provisions = ['9.10.9.16.(1)']
    case.section_c[0].pairs[0].objective = 'FAKE'
    assert all(item.objective != 'FAKE' for item in section_d_plan(case, Codes()).items)


def test_absent_attribution_stays_absent_and_clauses_keep_conditions():
    plan = section_d_plan(Case(provisions=['9.10.14.2.(1)', '3.1.4.2.(1)(a)']), Codes())
    absent = next(e for e in plan.items if e.provision_id == '9.10.14.2.(1)')
    assert absent.objective is absent.function is None and 'no row' in absent.performance_issue
    inherited = [e for e in plan.items if e.provision_id.endswith('(a)')]
    assert inherited and all(e.clauses == () and e.attributed_via == '3.1.4.2.(1)' for e in inherited)


def test_file_required_before_status_provided_and_responsibility_stays_blank():
    case = Case(provisions=['9.10.9.16.(1)'])
    item = section_d_plan(case, Codes()).items[0]
    with pytest.raises(ValidationError):
        SupportingDocument(id='d1', title='Invented test', file={'type': 'user_text', 'ref': 'm'})
    doc = SupportingDocument(id='d1', title='Applicant report', file={'ref': 'report.pdf'}, item_ids=(item.id,))
    plan = section_d_plan(case, Codes(), [doc])
    supplied = next(e for e in plan.items if e.id == item.id)
    assert supplied.status == 'evidence_listed' and supplied.responsible_party == ''
    assert sum(e.status == 'evidence_listed' for e in plan.items) == 1


def test_file_and_metadata_from_ledger():
    case = Case(provisions=['9.10.9.16.(1)'])
    item = section_d_plan(case, Codes()).items[0]
    def fact(field, value, source):
        return Fact(field=f'evidence.{item.id}.{field}', value=value, source=source, kind='pointed', status='confirmed')
    file = Source(type='file', ref='report.pdf')
    user = Source(type='user_text', ref='m')
    case.facts = [fact('file_ref', 'report.pdf', file), fact('responsible_party', 'Named applicant engineer', user),
                  fact('date', '2026-10-20', user)]
    docs = supporting_documents(case)
    assert len(docs) == 1 and docs[0].file.ref == 'report.pdf'
    result = next(e for e in section_d_plan(case, Codes()).items if e.id == item.id)
    assert result.status == 'evidence_listed' and result.responsible_party == 'Named applicant engineer'
    case.facts.append(fact('file_ref', 'mismatch.pdf', file))
    assert supporting_documents(case) == []


def test_acceptable_path_has_only_shared_ladder():
    case = Case(provisions=['9.10.9.16.(1)'], facts=[Fact(field='pathway', value='acceptable', kind='pointed',
                source=Source(type='user_text', ref='m'), status='confirmed')])
    assert all(i.recommended_types == CONFIDENCE_LADDER for i in section_d_plan(case, Codes()).items)
