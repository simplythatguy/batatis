import pytest

from engine import routes_assist
from engine.codes import Codes
from engine.tests.test_assist import assistant, ask, enable


class QuoteCodes:
    def provision(self, pid, division):
        if pid == '9.10.9.16.(1)' and division == 'B':
            return {'id': pid, 'text': '1) A fire separation shall be provided between the rooms.\nThe wall has two layers.'}
        if pid == '9.25.2.2.(1)' and division == 'B':
            return {'id': pid, 'text': '1) Thermal insulation shall be installed.'}
        return None


@pytest.mark.parametrize(('quote', 'keeps_style'), [
    ('A fire separation shall be provided between the rooms.', True),
    ('A fire separation  shall\tbe provided', True),
    ('A fire separation ... between the rooms.', False),
    ('A fire separation … between the rooms.', False),
    ('... shall be provided between the rooms.', True),
    ('A fire separation shall be …', True),
    ('N ... o ... t ... r ... e', False),
    ('a fire separation shall be provided', False),
    ('Batatis invented this interpretation.', False),
    ('Thermal insulation shall be installed.', False),
    ('between the rooms. ... A fire separation', False),
    ('A fire separation ... Thermal insulation', False),
    ('...', False),
])
def test_quote_style_requires_a_case_sensitive_match_in_a_cited_provision(quote, keeps_style):
    text = f'Read 9.10.9.16.(1).\n> {quote}'
    answer, cited, removed = routes_assist.check_citations(text, QuoteCodes())
    assert ('\n> ' in answer) is keeps_style
    assert quote in answer
    assert cited == ['9.10.9.16.(1)'] and removed == []


def test_focused_provision_is_verified_against_code_database_even_without_a_reply_citation():
    text = '> A fire separation shall be provided'
    context = {'focused_provision': {'id': '9.10.9.16.(1)', 'division': 'B', 'text': 'untrusted substitute'}}
    assert routes_assist.check_citations(text, QuoteCodes(), context=context)[0] == text
    assert routes_assist.check_citations(text, QuoteCodes())[0] == text[2:]
    fake = '> untrusted substitute'
    assert routes_assist.check_citations(fake, QuoteCodes(), context=context)[0] == fake[2:]


def test_each_quote_line_requires_its_own_match_and_does_not_borrow_text_across_sources():
    text = ('Read 9.10.9.16.(1) and 9.25.2.2.(1).\n'
            '> A fire separation shall be provided\n'
            '> invented explanation\n'
            '> A fire separation ... Thermal insulation\n'
            '> Thermal insulation shall be installed.')
    answer, cited, _ = routes_assist.check_citations(text, QuoteCodes())
    assert answer.splitlines()[1:] == ['> A fire separation shall be provided', 'invented explanation',
        'A fire separation ... Thermal insulation', '> Thermal insulation shall be installed.']
    assert len(cited) == 2


def test_real_assistant_route_preserves_only_the_focused_code_quote(assistant, monkeypatch):
    client, _, _ = assistant
    enable(monkeypatch, 'openai')
    text = Codes().provision('9.10.9.16.(1)', 'B')['text']
    passage = ' '.join(text.split())[:70].rsplit(' ', 1)[0]
    generated = f'> {passage}\n> An explanation that is not in the code.'
    monkeypatch.setattr(routes_assist, 'call_model', lambda **kw: routes_assist.ModelAnswer(generated, 30, 30))
    response = ask(client, focus={'kind': 'provision', 'id': '9.10.9.16.(1)'})
    assert response.status_code == 200, response.text
    assert response.json()['answer'] == f'> {passage}\nAn explanation that is not in the code.'


def test_generated_provider_names_are_not_returned_by_assistant():
    assert routes_assist.check_citations('OpenAI wrote this.', QuoteCodes())[0] == routes_assist.SAFE_HELP


@pytest.mark.parametrize('prefix', ['\u00a0', '\u2003', ' \u00a0', '\u3000'])
def test_unicode_space_before_the_mark_cannot_smuggle_an_unverified_quote(prefix):
    invented = 'thermal insulation is optional in all buildings'
    answer = routes_assist.check_citations(f'Read 9.10.9.16.(1).\n{prefix}> {invented}', QuoteCodes())[0]
    assert answer.splitlines()[1] == invented
    verified = routes_assist.check_citations(f'Read 9.10.9.16.(1).\n{prefix}> A fire separation shall be provided', QuoteCodes())[0]
    assert verified.splitlines()[1] == '> A fire separation shall be provided', 'a verified quote is rewritten with a plain mark'
