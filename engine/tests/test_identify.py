"""Identify module. Offline tests use fake adapters; live tests run only when their credentials are present."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.codes import default_db
from engine.identify import JEV_MODEL, Judge, articles, bm25_rank, identify
from engine.identify.verify import ClaudeVerifier, Pick, Picks, check_quotes

DB = default_db()
CASES = Path(__file__).resolve().parents[2] / 'docs/research/2026-10-20-vision/jev-benchmark/data/cases.json'


def fake_ask(favour):
    """Jev stand-in: high probability when the card mentions `favour`."""
    calls = []

    def ask(state, questions, timeout):
        calls.append(len(questions))
        arts = state['articles']
        answers = {q: {'noul': 0.9 if favour in arts[f'A{q[1:]}'].lower() else 0.01} for q in questions}
        return {'answers': answers, 'usage': {'input_tokens': 10}}
    ask.calls = calls
    return ask


def test_corpus_has_every_division_b_article():
    arts = articles(DB)
    assert len(arts) > 2000 and '9.10.15.5.' in arts and all(a.count('.') == 4 for a in arts)
    assert arts['9.9.10.1.']['part'] == 9


def test_bm25_baseline_finds_bedroom_egress():
    assert '9.9.10.1.' in bm25_rank('bedroom egress window opening', DB)[:10]


def test_screen_batches_and_rerank_is_one_request():
    ask = fake_ask('limiting distance')
    judge = Judge(ask, workers=2)
    res = identify('wall too close to the property line', DB, judge, parts={9})
    assert len(res.screen) == sum(1 for a in articles(DB).values() if a['part'] == 9)
    assert res.usage['rerank_requests'] == 1 and len(ask.calls) > 2
    assert res.ranked[0][1] == 0.9 and len(res.ranked) == 60
    assert res.model == JEV_MODEL == 'jev-1.13.0'


def test_quote_check_drops_paraphrase_and_unlisted_articles():
    arts = articles(DB)
    text = arts['9.9.10.1.']['text']
    verbatim = ' '.join(text.split()[:12])
    spaced = verbatim.replace(' ', '\n  ', 2)                     # whitespace differences are tolerated
    picks = [Pick(article='9.9.10.1.', quote=spaced, reason='r', confidence=0.9),
             Pick(article='9.8.8.1.', quote='guards shall be provided everywhere', reason='r', confidence=0.5),
             Pick(article='3.1.18.5.', quote=verbatim, reason='r', confidence=0.4)]
    keep, dropped = check_quotes(picks, ['9.9.10.1.', '9.8.8.1.'], arts)
    assert [p.article for p in keep] == ['9.9.10.1.']
    assert [why for _, why in dropped] == ['quote not found in article text', 'article not in candidate list']


def test_claude_verifier_uses_full_text_and_checks_quotes():
    arts = articles(DB)
    verbatim = ' '.join(arts['9.9.10.1.']['text'].split()[-10:])
    sent = {}

    class FakeMessages:
        def parse(self, **kw):
            sent.update(kw)
            out = Picks(picks=[Pick(article='9.9.10.1.', quote=verbatim, reason='r', confidence=0.8),
                               Pick(article='9.8.8.1.', quote='made up words', reason='r', confidence=0.3)])
            return SimpleNamespace(parsed_output=out, stop_reason='end_turn',
                                   usage=SimpleNamespace(input_tokens=1, output_tokens=1))

    v = ClaudeVerifier(DB, client=SimpleNamespace(messages=FakeMessages()))
    res = v.verify('bedroom window opening limiter', ['9.9.10.1.', '9.8.8.1.'])
    assert [p.article for p in res.picks] == ['9.9.10.1.'] and len(res.dropped) == 1
    assert sent['model'] == 'claude-sonnet-5-5'
    assert arts['9.9.10.1.']['text'][-200:] in sent['messages'][0]['content']   # full text, not cut at 700


@pytest.mark.skipif(not os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('BATATIS_LIVE') != '1'
                    or not os.environ.get('OPENAI_API_KEY'),
                    reason='needs BATATIS_LIVE=1, OPENAI_API_KEY, and ANTHROPIC_API_KEY')
def test_live_claude_verifier():
    case = next(c for c in json.load(open(CASES)) if c['id'] == 'standata-nbc2023-variance-23-bcv-001')
    res = ClaudeVerifier(DB).verify(case['query'], ['9.8.8.1.', '9.9.10.1.', '9.7.2.1.', '9.6.1.3.'])
    assert res.picks and {p.article for p in res.picks} <= {'9.8.8.1.', '9.9.10.1.', '9.7.2.1.', '9.6.1.3.'}


@pytest.mark.skipif(os.environ.get('BATATIS_LIVE_JEV') != '1' or os.environ.get('BATATIS_LIVE') != '1'
                    or not os.environ.get('OPENAI_API_KEY'),
                    reason='set BATATIS_LIVE_JEV=1, BATATIS_LIVE=1, and OPENAI_API_KEY for a live Jev call')
def test_live_jev_screen():
    case = next(c for c in json.load(open(CASES)) if c['id'] == 'standata-nbc2023-variance-23-bcv-001')
    res = identify(case['query'], DB)
    assert res.usage['errors'] == 0 and res.ranked
