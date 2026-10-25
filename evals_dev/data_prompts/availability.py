"""One-time label for facts whose wording only partly matches the attachments (overlap 0.3 to 0.6).

For each such fact the three best-matching pages (or the prompt) are shown to the model, which says
whether those pages state the fact, with a supporting excerpt that must occur in them. The labels are
written to availability.json and read by gold.py; they never depend on a run of the system under test.

    .venv/bin/python -m evals_dev.data_prompts.availability
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from . import corpus, gold, judge, ledger, sut, texts

OUT = Path(__file__).with_name('availability.json')
MODEL, EFFORT = 'gpt-6.1-sol', 'low'
SYSTEM = """You check whether source pages state a fact. The fact was written by a person who read the
source; it may paraphrase. Answer "stated" true only when the pages themselves state the fact's central
claim and its key values (numbers, names, dates, article numbers). If the fact depends on information
that is not in these pages (a catalogue entry, another document, an image, a later decision), answer
false. When true, give the shortest exact excerpt (at most 300 characters) from the pages that supports
it, copied character for character; when false, give an empty excerpt."""


def schema() -> dict:
    return {'type': 'object', 'additionalProperties': False, 'required': ['stated', 'excerpt'],
            'properties': {'stated': {'type': 'boolean'}, 'excerpt': {'type': 'string'}}}


def windows(case: corpus.Case) -> list[tuple[str, str]]:
    out = [('request text', case.prompt)]
    for attachment in case.attachments:
        pages = texts.pages(case, attachment)
        out += [(f'{attachment.filename} p.{i + 1}', t) for i, t in enumerate(pages)]
        out += [(f'{attachment.filename} pp.{i + 1}-{i + 2}', a + '\n' + b) for i, (a, b) in enumerate(zip(pages, pages[1:]))]
    return out


def label(case: corpus.Case, index: int, fact: str) -> dict:
    want = gold.tokens(fact)
    ranked = sorted(windows(case), key=lambda w: -len(want & gold.tokens(w[1])))[:3]
    user = json.dumps({'fact': fact, 'pages': [{'where': w, 'text': t[:9000]} for w, t in ranked]}, ensure_ascii=False)
    body = {'model': MODEL, 'reasoning_effort': EFFORT, 'max_completion_tokens': 4000,
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
            'response_format': {'type': 'json_schema', 'json_schema': {'name': 'stated', 'strict': True, 'schema': schema()}}}
    with httpx.Client(timeout=300) as client:
        response = client.post(judge.URL, json=body, headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']})
        response.raise_for_status()
        answer = json.loads(response.json()['choices'][0]['message']['content'])
    supported = bool(answer.get('stated')) and judge.found(answer.get('excerpt') or '', '\n'.join(t for _, t in ranked))
    return {'case_id': case.id, 'fact': index, 'available': supported, 'excerpt': (answer.get('excerpt') or '')[:300]}


def main() -> int:
    sut.load_env()
    ledger.install()
    todo = []
    for case in corpus.load():
        for i, fact in enumerate(case.facts):
            if gold.LABEL_RANGE[0] <= gold.availability(case, fact.text) < gold.LABEL_RANGE[1]:
                todo.append((case, i, fact.text))
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        with ThreadPoolExecutor(8) as pool:
            rows = list(pool.map(lambda t: label(*t), todo))
    finally:
        ledger.CURRENT.reset(token)
    labels: dict[str, dict[str, bool]] = {}
    for row in rows:
        labels.setdefault(row['case_id'], {})[str(row['fact'])] = row['available']
    OUT.write_text(json.dumps({'model': f'{MODEL}:{EFFORT}', 'range': list(gold.LABEL_RANGE), 'labels': labels},
                              indent=1, sort_keys=True) + '\n')
    print(f'{len(rows)} labelled, {sum(r["available"] for r in rows)} available, '
          f'${ledger.UNATTRIBUTED.summary()["usd"] + book.summary()["usd"]:.4f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
