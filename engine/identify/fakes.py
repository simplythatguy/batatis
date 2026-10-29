"""Offline stand-ins for Elephant, Jev, Anthropic and OpenAI, selected by BATATIS_PROVIDER=fake.

They are deterministic and read only what a real provider would receive (the request), so the
pipeline, the quote check, the commit policy, the SSE stream and the spend gate all run without
keys. Scores come from word overlap between the proposal and the article card; picks quote the
first words of the article body copied from the request. A fake result is labelled `fake`
everywhere it is shown. It measures nothing about accuracy.

`LyingAnthropic` is the adversary for the property test: it invents article ids, paraphrases
quotes, quotes the wrong article and names articles outside the candidate list.
"""
from __future__ import annotations

import json
import random
import re
from types import SimpleNamespace

from .verify import Pick, Picks

_WORD = re.compile(r'[a-z][a-z0-9-]{2,}')
_ARTICLE_BLOCK = re.compile(r'<article id="([^"]+)">\n(.*?)\n</article>', re.S)
_PROPOSAL = re.compile(r'<proposal>\n(.*?)\n</proposal>', re.S)
# The model rank's numbered form (model_rank.RankVerifier).
_NUMBERED = re.compile(r'^\[\d+\] (\S+) (.*)$', re.M)
_DESCRIPTION = re.compile(r'Applicant description:\n<<<\n(.*?)\n>>>', re.S)
# The table-of-contents search's lines (model_rank.toc_text).
_TOC_LINE = re.compile(r'^(\d+\.\d+\.\d+\.\d+\.) (.*)$', re.M)
_STOP = set('the and for with that this from are was were has have not but its into our their will shall '
            'any all each other than then there which when where who whom what been being such also only'.split())


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def overlap(proposal: str, text: str) -> float:
    """A probability-like score in [0.01, 0.97] from shared content words. Deterministic."""
    want = _words(proposal)
    if not want:
        return 0.01
    hit = len(want & _words(text)) / len(want)
    return round(min(0.97, 0.01 + hit * 1.2), 4)


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _question_card(state, name, question) -> str:
    if 'articles' in state:
        return state['articles'][f'A{name[1:]}']
    from .screen import SELF_QUESTION
    return question['instructions'].removeprefix(SELF_QUESTION.partition('{card}')[0])


def fake_jev_ask():
    """Jev's ask(state, questions, timeout) contract: one `noul` probability per question."""
    def ask(state, questions, timeout):
        proposal = state['proposal']
        answers = {}
        for name, question in questions.items():
            card = _question_card(state, name, question)
            answers[name] = {'noul': overlap(proposal, card)}
        size = len(proposal) + (sum(len(v) for v in state['articles'].values()) if 'articles' in state else
                                sum(len(q['instructions']) for q in questions.values()))
        return {'answers': answers, 'usage': {'input_tokens': max(1, size // 4), 'output_tokens': 4 * len(questions)},
                'latency_ms': 1}
    return ask


def fake_decisions(body: dict, timeout: float) -> dict:
    """The Decisions wire shape, using only synthetic overlap estimates in offline mode."""
    state = json.loads(body['input'])
    answers = [{'name': q['name'], 'type': 'predicate',
                'probability': overlap(state['proposal'], _question_card(state, q['name'], q))}
               for q in body['questions']]
    tokens = _tokens(json.dumps(body))
    return {'model': body['model'], 'answers': answers,
            'usage': {'input_tokens': tokens, 'output_tokens': 0, 'total_tokens': tokens,
                      'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                      'output_tokens_details': {'reasoning_tokens': 0}}}


def fake_elephant_post(body: bytes, headers: dict, timeout: float) -> tuple[int, bytes]:
    """Real typed Decisions shape, passed through the same validator as live responses."""
    from .elephant_runtime import RESPONSE_MODEL
    request = json.loads(body)
    state = request['state']
    answers = {}
    for name, question in request['questions'].items():
        text = _question_card(state, name, question)
        answers[name] = {'type': 'noul', 'noul': overlap(state['proposal'], text)}
    return 200, json.dumps({'model': RESPONSE_MODEL, 'answers': answers,
                            'usage': {'input_tokens': _tokens(body), 'output_tokens': len(answers),
                                      'cost': 0}}).encode('utf-8')


def _body(card_text: str) -> str:
    """The article text after its heading ('Title (Part 9 > ...): body')."""
    head_end = card_text.find('): ')
    return card_text[head_end + 3:] if head_end >= 0 else card_text


def _quote(card_text: str, words: int = 14) -> str:
    return ' '.join(_body(card_text).split()[:words])


def parse_request(user: str) -> tuple[str, list[tuple[str, str]]]:
    proposal = _PROPOSAL.search(user) or _DESCRIPTION.search(user)
    return (proposal.group(1) if proposal else ''), _ARTICLE_BLOCK.findall(user) or _NUMBERED.findall(user)


def honest_picks(user: str, n: int = 2) -> list[dict]:
    proposal, listed = parse_request(user)
    scored = sorted(listed, key=lambda item: -overlap(proposal, item[1]))
    out = []
    for article, text in scored[:n]:
        if overlap(proposal, text) <= 0.01:
            continue
        out.append({'article': article, 'quote': _quote(text),
                    'reason': 'The proposal describes the situation this requirement governs.',
                    'confidence': overlap(proposal, text)})
    return out


def toc_search(user: str, n: int = 12) -> list[dict]:
    """The table-of-contents lines sharing the most words with the description, as the search answers."""
    description = _DESCRIPTION.search(user)
    proposal = description.group(1) if description else ''
    lines = sorted(_TOC_LINE.findall(user.split('\n>>>\n', 1)[-1]), key=lambda item: -overlap(proposal, item[1]))
    return [{'id': article, 'why': 'The title matches the description.'}
            for article, title in lines[:n] if overlap(proposal, title) > 0.01]


def _usage(prompt: str, out: int = 200):
    return SimpleNamespace(input_tokens=_tokens(prompt), output_tokens=out)


class _Messages:
    def __init__(self, picker, searcher):
        self.picker, self.searcher = picker, searcher
        self.calls: list[dict] = []

    def parse(self, **kw):
        self.calls.append(kw)
        user = kw['messages'][0]['content']
        output = kw.get('output_format')
        if output is not None and 'candidates' in output.model_fields:     # the table-of-contents search
            parsed = output.model_validate({'candidates': self.searcher(user)})
        else:
            parsed = Picks(picks=[Pick(**p) for p in self.picker(user)])
        return SimpleNamespace(parsed_output=parsed, stop_reason='end_turn',
                               usage=_usage((kw.get('system') or '') + user), model=kw['model'])


class FakeAnthropic:
    """messages.parse(...) like the Anthropic SDK, picking honestly from the listed articles."""

    def __init__(self, picker=honest_picks, searcher=toc_search):
        self.messages = _Messages(picker, searcher)


def lying_picks(seed: int):
    """Fabrications of every kind, plus (sometimes) one honest pick so filtering is visible."""
    rng = random.Random(seed)

    def picker(user: str) -> list[dict]:
        proposal, listed = parse_request(user)
        ids = [a for a, _ in listed]
        texts = dict(listed)
        lies = []
        for _ in range(rng.randint(1, 6)):
            kind = rng.choice(['invented_id', 'paraphrase', 'wrong_article', 'outside_list', 'joined', 'empty'])
            target = rng.choice(ids) if ids else '9.10.15.5.'
            if kind == 'invented_id':
                lies.append({'article': f'{rng.randint(1, 12)}.{rng.randint(50, 99)}.{rng.randint(1, 9)}.{rng.randint(1, 9)}.',
                             'quote': _quote(texts.get(target, 'x')), 'reason': 'r', 'confidence': 0.99})
            elif kind == 'paraphrase':
                words = _quote(texts.get(target, 'shall be provided')).split()
                rng.shuffle(words)
                lies.append({'article': target, 'quote': ' '.join(words) + ' approximately', 'reason': 'r',
                             'confidence': 0.95})
            elif kind == 'wrong_article' and len(ids) > 1:
                other = rng.choice([a for a in ids if a != target])
                lies.append({'article': target, 'quote': 'ZZZ ' + _quote(texts[other]), 'reason': 'r',
                             'confidence': 0.9})
            elif kind == 'outside_list':
                lies.append({'article': '3.2.4.1.' if '3.2.4.1.' not in ids else '9.36.2.6.',
                             'quote': 'fire alarm system shall be installed', 'reason': 'r', 'confidence': 0.9})
            elif kind == 'joined' and ids:
                words = _body(texts[target]).split()
                if len(words) > 40:
                    lies.append({'article': target, 'quote': ' '.join(words[:6] + words[30:36]), 'reason': 'r',
                                 'confidence': 0.9})
            else:
                lies.append({'article': target, 'quote': '   ', 'reason': 'r', 'confidence': 0.9})
        if rng.random() < 0.5:
            lies.extend(honest_picks(user, 1))
        rng.shuffle(lies)
        return lies
    return picker


class LyingAnthropic(FakeAnthropic):
    def __init__(self, seed: int = 0):
        super().__init__(lying_picks(seed))


def fake_openai_json(name, schema, system, user, *, model, max_output_tokens=4096, effort=None, timeout=60):
    """OpenAI JSON transport contract. `picks` for the verifier, `scores` for a model rerank."""
    proposal, listed = parse_request(user)
    if name == 'picks':
        payload = {'picks': honest_picks(user)}
    elif name == 'toc_candidates':
        # Read the same complete TOC as the live selector; no hidden gold ids or corpus access.
        toc = re.findall(r'^(\d+\.\d+\.\d+\.\d+\.) (.*)$', system, re.M)
        toc.sort(key=lambda item: -overlap(proposal, item[1]))
        count = re.search(r'Return up to (\d+) tentative', user)
        payload = {'articles': [a for a, _ in toc[:int(count.group(1)) if count else 40]]}
    elif name == 'pool_review':
        payload = {'labels': [dict(article=a, label='applies' if overlap(proposal, text) > 0.01 else 'check',
                                   quote=_quote(text), reason='A tentative requirement for the applicant to review.',
                                   confidence=overlap(proposal, text)) for a, text in listed]}
    else:
        payload = {'scores': [{'article': a, 'probability': overlap(proposal, text)} for a, text in listed]}
    return payload, {'input_tokens': _tokens(system + user), 'output_tokens': 150, 'returned_model': model}
