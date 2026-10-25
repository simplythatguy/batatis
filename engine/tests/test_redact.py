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


def test_intake_personal_field_names_remain_scrubbed_when_reused_by_identification():
    case = Case(facts=[fact('owner_rep_name', 'Alice Smith'), fact('municipal_address', 'Unit Q, Civic Plaza'),
                       fact('permit_number', '1234')])
    out = scrub('Alice Smith represents the owner at Unit Q, Civic Plaza; permit 1234.', known_values(case))
    assert 'Alice Smith' not in out and 'Civic Plaza' not in out and '1234' not in out


def test_a_known_short_number_does_not_corrupt_an_unrelated_larger_number():
    assert scrub('Permit 202; issued in 2025.', ['202']) == 'Permit [personal detail]; issued in 2025.'


def test_short_personal_names_and_permits_are_still_known_values():
    case = Case(facts=[fact('owner_name', 'Al'), fact('permit_number', 'X7')])
    assert scrub('Owner Al; permit X7.', known_values(case)) == 'Owner [personal detail]; permit [personal detail].'
    assert set(known_values(case, ['Bo'])) == {'Al', 'X7', 'Bo'}


def test_a_known_number_does_not_redact_digits_from_decimals_or_grouped_numbers():
    assert scrub('Permit 9; length 19.9 m.', ['9']) == 'Permit [personal detail]; length 19.9 m.'
    assert scrub('Permit 999; length 1,999 m.', ['999']) == 'Permit [personal detail]; length 1,999 m.'
    assert scrub('Permit 202; length 202.5 m.', ['202']) == 'Permit [personal detail]; length 202.5 m.'


def test_empty_known_values_leave_the_text_alone():
    assert scrub('A plain source statement.', ['']) == 'A plain source statement.'
