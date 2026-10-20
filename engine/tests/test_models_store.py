import pytest
from pydantic import ValidationError

from engine.models import Case, Fact, Source
from engine.store import CaseStore

SRC = Source(type='user_text', ref='msg_1', quote='three storey rowhouse')


def test_proposed_fact_cannot_be_constructed_confirmed():
    with pytest.raises(ValidationError):
        Fact(field='storeys', value=3, kind='proposed', source=SRC, confidence=0.8, status='confirmed')


def test_proposed_fact_never_exports_as_confirmed_even_if_mutated():
    f = Fact(field='storeys', value=3, kind='proposed', source=SRC, confidence=0.8)
    f.status = 'confirmed'                      # bypasses validation (no validate_assignment)
    assert f.export()['status'] == 'unconfirmed'
    with pytest.raises(ValidationError):           # a case re-validates its facts
        Case(facts=[f])
    g = Fact(field='storeys', value=3, kind='proposed', source=SRC, confidence=0.8)
    case = Case(facts=[g, Fact(field='address', value='1 Main St', kind='pointed', source=SRC, status='confirmed')])
    assert case.export_blockers() == [g.id]


def test_store_roundtrip_and_add_fact(tmp_path):
    s = CaseStore(tmp_path / 'cases.sqlite')
    case = s.put(Case(title='Rowhouse'))
    fact = Fact(field='storeys', value=3, kind='pointed', source=SRC)
    got = s.add_fact(case.id, fact)
    assert got.facts == [fact]
    assert s.get(case.id).facts[0].source.quote == 'three storey rowhouse'
    assert s.get('case_missing') is None and s.add_fact('case_missing', fact) is None
