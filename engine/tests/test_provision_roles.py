"""User-added provisions are the departure. References in that text are citing."""
from engine.models import Case
from engine.provision_roles import record_provision_roles, referenced_ids

DEPARTURE = '9.27.5.1.(1)'


def test_references_are_article_and_sentence_names_only():
    text = ('See Article 9.27.3.3. and Sentences 9.27.3.4.(1) and (2). '
            'Sentence (2) stays on this article. Table 9.25.5.2. is not a provision. '
            'A bare 9.10.17.10.(1) without the word Sentence is not pulled in.')
    assert referenced_ids(text, DEPARTURE) == [
        '9.27.3.3.', '9.27.3.4.(1)', '9.27.3.4.(2)', '9.27.5.1.(2)']


class _Codes:
    def __init__(self, texts):
        self.texts = texts

    def definition(self, code):
        return None

    def provision(self, pid, division='B'):
        if pid not in self.texts:
            return None
        child = f'{pid}(1)' if pid.endswith('.') and f'{pid}(1)' in self.texts else None
        return {
            'id': pid, 'division': division, 'citation': f'synthetic Div {division} {pid}',
            'level': 'article' if child else 'sentence', 'text': self.texts[pid],
            'attributions': [], 'intents': [], 'intent_comparison': [], 'attribution_status': None,
            'children': [{'id': child, 'level': 'sentence'}] if child else [],
            'pdf_page': 1, 'article_title': 'synthetic',
        }


def test_record_keeps_the_departure_and_walks_the_citing_chain():
    texts = {
        '9.27.5.1.': 'See Sentence (1). See Article 9.27.3.3.',
        '9.27.5.1.(1)': 'child of the departure',
        '9.27.3.3.': 'See Sentence 9.25.5.1.(1).',
        '9.27.3.3.(1)': 'child',
        '9.25.5.1.(1)': 'end',
    }
    case = Case(facts=[])
    record_provision_roles(case, _Codes(texts), ['9.27.5.1.'])
    assert case.provisions == ['9.27.5.1.', '9.27.3.3.', '9.25.5.1.(1)']
    roles = {fact.value: fact for fact in case.facts}
    assert roles['departure:9.27.5.1.'].kind == 'pointed'
    assert roles['departure:9.27.5.1.'].source.type == 'user_text'
    assert roles['citing:9.27.3.3.'].kind == 'exact'
    assert roles['citing:9.27.3.3.'].source.type == 'code'
    assert 'citing:9.27.5.1.(1)' not in roles
