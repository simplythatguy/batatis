"""Offline stand-ins for the providers, so every adapter and the runner can be tested without a key or a network.

* ``tiny_corpus`` is a small article table in the shape of ``engine.identify.corpus.articles()``.
* ``FakeJev`` answers Jev's ``ask(state, questions, timeout)`` with a word-overlap score, counts requests, and can be told
  to fail on chosen calls.
* ``fake_openai_http`` is an ``Http`` callable for ``OpenAIChat``. Modes: ``honest`` (picks the best-overlap candidate and
  quotes it exactly), ``liar`` (invents an article, fabricates a quote, repeats a pick), ``rate_limit`` (429 twice, then
  honest), ``always_429``, ``timeout``, ``refusal``, ``truncated``, ``garbage``, ``no_usage``.

The fakes are deterministic. They are not a model of accuracy; they exist to exercise contracts and failure paths.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable

_WORD = re.compile(r'[a-z]{4,}')


def words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


TOPICS = [
    ('soffit', 'overhang projection of a roof soffit near the property line'),
    ('guard', 'guard height and openings on balconies and decks'),
    ('stair', 'stair rise and run dimensions for dwelling stairs'),
    ('cladding', 'fastening of exterior cladding to furring over sheathing'),
    ('insulation', 'thermal insulation installation in basement walls'),
    ('firestop', 'firestop systems at penetrations of fire separations'),
    ('footing', 'strip footing width on silty soil with a high water table'),
    ('exit', 'minimum number of exits from an assembly occupancy'),
    ('sprinkler', 'sprinklered group c building up to six storeys'),
    ('smoke', 'smoke alarm locations in dwelling units'),
    ('window', 'egress window size for bedrooms'),
    ('radon', 'subfloor depressurisation rough-in for soil gas'),
]
PARTS = (3, 4, 9)


def tiny_corpus() -> dict[str, dict]:
    arts = {}
    for i, (topic, phrase) in enumerate(TOPICS):
        for k in range(1, 4):
            part = PARTS[(i + k) % 3]
            aid = f'{part}.{i + 1}.{k}.1.'
            arts[aid] = {'id': aid, 'part': part, 'title': f'{topic.title()} {k}',
                         'section': f'Section {topic}', 'subsection': f'Subsection {k}',
                         'text': f'The {phrase} shall comply with requirement {k}. {topic} detail {k} applies to every '
                                 f'building of this type and the {topic} shall be maintained.'}
    return dict(sorted(arts.items()))


def overlap(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


class FakeJev:
    """``jev_ask`` for RunContext: ``FakeJev()(model)`` returns an ``ask`` callable."""

    def __init__(self, fail_on: set[int] | None = None):
        self.calls = 0
        self.fail_on = fail_on or set()
        self.models: list[str] = []

    def __call__(self, model: str) -> Callable:
        self.models.append(model)

        def ask(state, questions, timeout):
            self.calls += 1
            if self.calls in self.fail_on:
                raise RuntimeError('fake jev outage')
            answers = {}
            for qname, q in questions.items():
                label = re.search(r'Article (A\d+)', q['instructions']).group(1)
                p = overlap(state['proposal'], state['articles'][label])
                answers[qname] = {'noul': round(min(0.99, p * 3), 2)}
            chars = len(json.dumps(state)) + len(json.dumps(dict(questions)))
            return {'answers': answers, 'usage': {'input_tokens': chars // 4, 'output_tokens': 2 * len(questions)},
                    'latency_ms': 5}
        return ask


def _candidates(user: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r'<article id="([^"]+)">\n(.*?)\n</article>', user, re.S)}


def _proposal(user: str) -> str:
    return re.search(r'<proposal>\n(.*?)\n</proposal>', user, re.S).group(1)


def fake_openai_http(mode: str = 'honest'):
    """Returns an ``Http`` callable; its ``.calls`` list holds the request bodies it received."""
    state = {'n': 0}
    calls: list[dict] = []

    def usage(prompt: str, completion: int = 200, reasoning: int = 120) -> dict:
        return {'prompt_tokens': len(prompt) // 4, 'completion_tokens': completion,
                'completion_tokens_details': {'reasoning_tokens': reasoning},
                'prompt_tokens_details': {'cached_tokens': 0}}

    def reply(body: dict, content: str, finish: str = 'stop', refusal: str | None = None) -> tuple:
        prompt = body['messages'][0]['content'] + body['messages'][1]['content']
        message = {'role': 'assistant', 'content': content, 'refusal': refusal}
        return 200, {'x-request-id': f'req_fake_{state["n"]}'}, {
            'id': f'chatcmpl-fake-{state["n"]}', 'model': body['model'], 'service_tier': 'default',
            'choices': [{'index': 0, 'message': message, 'finish_reason': finish}], 'usage': usage(prompt)}

    def honest_picks(body: dict) -> str:
        user = body['messages'][1]['content']
        cands, proposal = _candidates(user), _proposal(user)
        if not cands:
            return json.dumps({'picks': []})
        best = max(cands, key=lambda a: overlap(proposal, cands[a]))
        quote = ' '.join(re.sub(r'^.*?\): ', '', cands[best]).split()[:8])
        return json.dumps({'picks': [{'article': best, 'quote': quote, 'reason': 'matches the described design',
                                      'confidence': 0.9}]})

    def scores(body: dict) -> str:
        user = body['messages'][1]['content']
        cands, proposal = _candidates(user), _proposal(user)
        return json.dumps({'scores': [{'article': a, 'probability': round(min(1.0, overlap(proposal, t) * 3), 2)}
                                      for a, t in cands.items()]})

    def http(url: str, headers, body: dict, timeout: float):
        state['n'] += 1
        calls.append(body)
        is_picks = body['response_format']['json_schema']['name'] == 'picks'
        good = honest_picks(body) if is_picks else scores(body)
        if mode == 'honest':
            return reply(body, good)
        if mode == 'liar':
            cands = _candidates(body['messages'][1]['content'])
            first = next(iter(cands), '9.1.1.1.')
            return reply(body, json.dumps({'picks': [
                {'article': '9.99.99.99.', 'quote': 'invented article', 'reason': 'x', 'confidence': 0.99},
                {'article': first, 'quote': 'this sentence is not in the article text', 'reason': 'x', 'confidence': 0.95},
                *json.loads(good)['picks'], *json.loads(good)['picks']]}))
        if mode == 'rate_limit':
            if state['n'] <= 2:
                return 429, {'retry-after': '0'}, {'error': {'message': 'rate limited'}}
            return reply(body, good)
        if mode == 'always_429':
            return 429, {}, {'error': {'message': 'rate limited'}}
        if mode == 'timeout':
            raise TimeoutError('read timed out')
        if mode == 'refusal':
            return reply(body, '', refusal='I cannot help with that.')
        if mode == 'truncated':
            return reply(body, '{"picks": [', finish='length')
        if mode == 'garbage':
            return reply(body, 'not json at all')
        if mode == 'no_usage':
            return 500, {}, {'error': {'message': 'boom'}}
        raise ValueError(mode)

    http.calls = calls
    return http
