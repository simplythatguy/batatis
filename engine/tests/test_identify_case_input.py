"""Identification consumes current facts and source bytes, without a provider."""
from engine.identify.case_input import compose, fingerprint
from engine.models import Case, Fact, Source
from engine.store import CaseStore


def fact(field, value, *, status='confirmed'):
    return Fact(field=field, value=value, kind='pointed', status=status,
                source=Source(type='user_text', ref='applicant'))


def test_confirmed_answer_changes_input_and_replaces_previous_value():
    case = Case(facts=[fact('project.description', 'A building.'), fact('storeys', 2)])
    first = compose(case)
    case.facts.append(fact('storeys', 8))
    second = compose(case)
    assert first.sha256 != second.sha256
    assert '8' in second.text and ': 2' not in second.text
    assert 'confirmed' in second.text


def test_unconfirmed_answers_remain_labelled_and_personal_fields_are_excluded():
    case = Case(facts=[fact('identify.choice.x', 'Not a departure', status='unconfirmed'),
                       fact('owner_name', 'Private Person')])
    context = compose(case)
    assert 'unconfirmed' in context.text and 'Not a departure' in context.text
    assert 'Private Person' not in context.text


def test_unconfirmed_model_value_cannot_erase_a_confirmed_input():
    case = Case(facts=[fact('storeys', 2), fact('storeys', 8, status='unconfirmed')])
    context = compose(case)
    assert ': 2' in context.text and ': 8' in context.text
    assert context.gaps == ('Conflicting supplied values for storeys; applicability requires confirmation.',)


def test_plans_only_reads_every_text_page_and_tracks_source_changes(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    first = compose(case, store)
    uploaded = store.put_file(case.id, 'plans.txt', b'Eight storeys; exterior wall with spatial separation.',
                              'text/plain')
    context = compose(case, store)
    assert context.sha256 != first.sha256
    assert 'Eight storeys' in context.text and uploaded['id'] in context.text
    assert 'Unconfirmed document context' in context.text
    assert not context.gaps


def test_unreadable_plan_is_explicit_gap_and_never_imagined_content(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    store.put_file(case.id, 'scan.pdf', b'not a pdf')
    context = compose(case, store)
    assert context.gaps and not context.text


def test_generated_results_do_not_change_input_hash_and_explicit_empty_does():
    case = Case(facts=[fact('storeys', 2)])
    before = fingerprint(case)
    case.title = 'Renamed project'
    assert fingerprint(case) == before
    case.facts.append(fact('storeys', None))
    assert fingerprint(case) != before
    assert 'Fact storeys' not in compose(case).text
