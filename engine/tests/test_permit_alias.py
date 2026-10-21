"""Permit text the applicant pasted must land on the form's permit number field."""

from engine.export.scc import confirmed_values
from engine.models import Case, Fact, Source


def test_permit_fact_fills_the_form_permit_number():
    case = Case(facts=[
        Fact(field='permit', value='BP-0000-00000', kind='pointed', status='confirmed',
             source=Source(type='user_text', ref='Your description', quote='BP-0000-00000')),
    ])
    assert confirmed_values(case)['permit_number'] == 'BP-0000-00000'
