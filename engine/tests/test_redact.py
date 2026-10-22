from engine.models import Case
from engine.redact import known_values, scrub, scrub_obj
from engine.tests.case_builder_fixtures import fact


def test_patterns_are_replaced_and_code_references_survive():
    text = ('Email dana.ross+work@city.example.ca or call (780) 555-0199 / 403.555.0123 / +1 587 555 0100. '
            'Site: 10345 82 Avenue NW, Edmonton T6E 2A1. See 9.23.17.3.(1) and Table 9.25.5.2. for 2 storeys.')
    out = scrub(text)
    for secret in ('dana.ross', '555-0199', '555.0123', '555 0100', '10345 82 Avenue NW', 'T6E 2A1'):
        assert secret not in out, secret
    assert '9.23.17.3.(1)' in out and 'Table 9.25.5.2.' in out and '2 storeys' in out
    assert '[email]' in out and '[phone]' in out and '[address]' in out and '[postal code]' in out


def test_known_personal_facts_are_replaced_case_insensitively():
    case = Case(facts=[fact('owner', 'Ravine Homes Ltd.'), fact('representative', 'Sam Ortiz'),
                       fact('evidence.wall.responsible_party', 'Ada Engineer'), fact('scope', 'site')])
    known = known_values(case)
    assert 'site' not in known
    out = scrub_obj({'a': ['ravine homes ltd. hired SAM ORTIZ', 'Ada Engineer signed']}, known)
    assert out == {'a': ['[personal detail] hired [personal detail]', '[personal detail] signed']}


def test_names_in_contact_phrasing_are_removed_but_product_and_code_terms_stay():
    text = ('Please call Jordan Lee or ask Dr. Ada Lin. My name is Sam Ortiz. Prepared by A. Engineer. '
            'NorthCore CX replaces the Sheathing Membrane; ask your Safety Codes Officer about Part 9.')
    out = scrub(text)
    for secret in ('Jordan Lee', 'Ada Lin', 'Sam Ortiz', 'A. Engineer'):
        assert secret not in out, secret
    assert 'call [name]' in out and 'Dr. [name]' in out and 'My name is [name]' in out
    for kept in ('NorthCore CX', 'Sheathing Membrane', 'Safety Codes Officer', 'Part 9'):
        assert kept in out, kept


def test_account_names_connected_to_the_case_are_known():
    from engine.redact import people_names
    from engine.models import Case

    class Person:
        def __init__(self, name, email):
            self.name, self.email = name, email

    class Store:
        def get_user(self, user_id):
            return Person('Priya Natarajan', 'priya@example.test') if user_id == 'owner' else None

    case = Case(owner_id='owner')
    names = people_names(Store(), case, Person('Dana Ross', 'dana@city.example'))
    assert {'Priya Natarajan', 'priya@example.test', 'Dana Ross', 'dana@city.example'} <= set(names)
    assert scrub('Dana Ross spoke with priya natarajan.', known_values(case, names)) == \
        '[personal detail] spoke with [personal detail].'
