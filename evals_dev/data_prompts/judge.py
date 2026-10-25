"""Judged coverage of reference items, with every positive verdict tied to an exact excerpt of the report.

One request per case grades all of its items. A covered item must come with an excerpt that occurs in
the report, or it is scored as not covered (the judge cannot credit text the report does not contain).
Prohibitions (review points that say what an answer must not do) are classified by their wording.
Missing or malformed verdicts fail closed, including prohibitions.
Verdicts are cached by (judge version, model, effort, request, report, items).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass

import httpx

from . import ledger
from .gold import Item

VERSION = 'judge-v7-strict'
CACHE = ledger.CACHE.parent / 'judge'
URL = 'https://api.openai.com/v1/chat/completions'
# A review point that only says what an answer must not do. "no compliance certification" is one;
# "no drawings or calculations attached" is a fact to flag, so a "no ..." point counts only when it
# ends on one of these nouns.
PROHIBITION = re.compile(
    r"^\s*(?:whether\s+(?:it|the\s+answer)\s+(?:does\s+not|avoids?)\b|(?:do|does)\s+not\b|don'?t\b|never\b|"
    r"avoids?\b|makes?\s+no\b|not\s+(?:treat|transfer|infer|claim|convert|assume)\b|"
    r"no\s+(?:[\w,-]+\s+){0,4}?(?:certification|statement|conclusion|determination|claim|inference|calculation|"
    r"analysis|outcome|approval|transfer|assumption)s?\s*\.?\s*$)", re.I)

SYSTEM = """You grade the output of a building-code document assistant against reference items for one case.
The report is everything the assistant showed the user for the request. Grade each reference item:

- F (source fact): covered when the report states the same fact: the same subject, the same values
  (numbers, units, dates, names, article numbers) and the same status (for example existing versus
  proposed, stated versus assumed, decided versus argued).
- R (review point): what a good answer must do or address. Covered when the report clearly addresses
  that specific point, through a fact it reports, a flag or note, a question it asks, or an item it lists
  as missing. Generic text that would fit any case does not cover a specific point.
- B (boundary): covered only when the report explicitly says what the item describes.

Many items have several parts: a list of values, issues, documents, recommendations or questions. An
item is covered only when the report contains every part. If any part is missing, covered is false.
Paraphrase and equivalent forms count (38 x 140 mm framing is 2x6 framing; 4,000 sq ft is 371.6 m2), but
a related fact, a partial list, or a heading does not.

Lines under "FROM THE REQUEST TEXT" only repeat what the user wrote in the request. They can cover
an F item, but they never cover an R or B item: those need the assistant's own facts, notes, flags,
questions or missing items.

Some items are prohibitions (marked "prohibition": true): something the answer must not do. For those,
set covered to false only when the assistant itself does that thing, and put the violating excerpt in
evidence; otherwise set covered to true with no evidence. Reporting, with attribution, what a document, a
decision-maker or a party says (for example "the determination found the handrails comply" or a quoted
excerpt) is not the assistant claiming it. Presenting another jurisdiction's provision or outcome as an
NBC(AE) requirement, or as Alberta acceptance, does count as transferring it.

For every other item: when covered is true, evidence lists exact excerpts of the report (each copied
character for character, at most 300 characters) that together show every part; when covered is false,
evidence is an empty list. Judge only from the report. Do not fill gaps with outside knowledge. When
unsure, answer false."""


def schema() -> dict:
    return {'type': 'object', 'additionalProperties': False, 'required': ['items'], 'properties': {
        'items': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                             'required': ['id', 'covered', 'evidence'],
                                             'properties': {'id': {'type': 'string'}, 'covered': {'type': 'boolean'},
                                                            'evidence': {'type': 'array',
                                                                         'items': {'type': 'string'}}}}}}}


def is_prohibition(item: Item) -> bool:
    """A point with a second clause after ';' also asks for something, so it is graded as a requirement."""
    return item.kind == 'R' and ';' not in item.text and bool(PROHIBITION.search(item.text))


def found(evidence: str, report: str) -> bool:
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    if evidence in report:
        return True
    # A long excerpt the judge shortened with an ellipsis: every part must occur, in order.
    parts = [p for p in re.split(r'\s*(?:\.\.\.|…)\s*', evidence) if p]
    if len(parts) < 2:
        return False
    body, at = report, 0
    for part in parts:
        at = body.find(part, at)
        if at < 0:
            return False
        at += len(part)
    return True


@dataclass(frozen=True)
class Verdict:
    id: str
    kind: str
    passed: bool
    evidence: str
    note: str            # '', 'unverified', 'missing_verdict', 'violation'


def _key(model: str, effort: str, request: str, report: str, items: list[Item]) -> str:
    # DPE_JUDGE_NONCE draws a fresh, separately cached set of verdicts: used to measure judge noise.
    if model.startswith('deepseek'):
        from .deepseek_review import MAX_TOKENS, URL as provider_url
    else:
        MAX_TOKENS, provider_url = 16000, URL
    blob = json.dumps({'v': VERSION, 'n': os.environ.get('DPE_JUDGE_NONCE', ''), 'm': model, 'e': effort,
                       'max_output_tokens': MAX_TOKENS, 'provider_url': provider_url,
                       'system': SYSTEM, 'schema': schema(), 'q': request, 'r': report,
                       'i': [(i.id, i.kind, i.text) for i in items]}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _call(model: str, effort: str, user: str) -> dict:
    key = (os.environ.get('OPENAI_API_KEY') or '').strip()
    body = {'model': model, 'reasoning_effort': effort, 'max_completion_tokens': 16000,
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
            'response_format': {'type': 'json_schema',
                                'json_schema': {'name': 'coverage', 'strict': True, 'schema': schema()}}}
    for attempt in range(4):                    # dropped connections and 429/5xx only; verdicts never retried
        try:
            with httpx.Client(timeout=300, follow_redirects=False) as client:
                response = client.post(URL, json=body, headers={'Authorization': 'Bearer ' + key})
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            response.raise_for_status()
            data = response.json()
            if data['choices'][0].get('finish_reason') not in (None, 'stop'):
                raise ValueError('judge completion did not finish')
            return json.loads(data['choices'][0]['message']['content'])
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout,
                httpx.RemoteProtocolError, httpx.WriteError, httpx.PoolTimeout):
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError('judge request failed')


def grade(request: str, report: str, items: list[Item], *, model: str, effort: str,
          book: ledger.Ledger | None = None) -> list[Verdict]:
    if not items:
        return []
    if len({i.id for i in items}) != len(items):
        raise ValueError('duplicate reference item ids')
    key = _key(model, effort, request, report, items)
    path = CACHE / key[:2] / f'{key}.json'
    active_book = book if book is not None else ledger.Ledger()
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get('validator_version') != VERSION:
            return [Verdict(i.id, i.kind, False, '', 'old-validator') for i in items]
        payload = cached['payload']
        ledger.replay(cached['calls'], active_book)
    else:
        user = json.dumps({'request': request, 'report': report,
                           'experiment_nonce': os.environ.get('DPE_JUDGE_NONCE', ''),
                           'items': [{'id': i.id, 'kind': i.kind, 'prohibition': is_prohibition(i), 'text': i.text}
                                     for i in items]}, ensure_ascii=False)
        before = len(active_book.calls)
        token = ledger.CURRENT.set(active_book)
        try:
            if model.startswith('deepseek'):     # a provisional judge for paired comparisons; Sol is the reference
                from .deepseek_review import chat_json
                instructions = (SYSTEM + '\n\nAnswer with one JSON object only, matching this JSON Schema exactly:\n'
                                + json.dumps(schema(), separators=(',', ':')))
                payload, _ = chat_json(model, effort, instructions, user, stage='judge')
            else:
                payload = _call(model, effort, user)
        finally:
            ledger.CURRENT.reset(token)
        ledger.write_artifact(path, json.dumps({'validator_version': VERSION, 'request_hash': key,
                                               'payload': payload,
                                               'calls': [asdict(c) for c in active_book.calls[before:]]}))
    # Validate the external boundary before interpreting any verdict. Unknown ids or malformed list
    # entries make the response ambiguous; missing/duplicate individual ids never receive credit.
    if not isinstance(payload, dict) or set(payload) != {'items'} or not isinstance(payload['items'], list):
        return [Verdict(i.id, i.kind, False, '', 'invalid_payload') for i in items]
    expected = {i.id for i in items}
    if any(not isinstance(v, dict) or not isinstance(v.get('id'), str) or v['id'] not in expected
           for v in payload['items']):
        return [Verdict(i.id, i.kind, False, '', 'invalid_ids') for i in items]
    counts = Counter(v['id'] for v in payload['items'])
    by_id = {v['id']: v for v in payload['items']}
    out = []
    for item in items:
        v = by_id.get(item.id)
        if v is None:
            out.append(Verdict(item.id, item.kind, False, '', 'missing_verdict'))
            continue
        if counts[item.id] != 1:
            out.append(Verdict(item.id, item.kind, False, '', 'duplicate_verdict'))
            continue
        if (set(v) != {'id', 'covered', 'evidence'} or type(v['covered']) is not bool
                or not isinstance(v['evidence'], list)
                or any(not isinstance(e, str) or not e.strip() for e in v['evidence'])):
            out.append(Verdict(item.id, item.kind, False, '', 'invalid_verdict'))
            continue
        excerpts = v['evidence']
        evidence = ' | '.join(excerpts)
        if is_prohibition(item):
            if v['covered']:
                out.append(Verdict(item.id, item.kind, not excerpts, evidence,
                                   'invalid_verdict' if excerpts else ''))
            else:
                verified = bool(excerpts) and all(found(e, report) for e in excerpts)
                out.append(Verdict(item.id, item.kind, False, evidence, 'violation' if verified else 'unverified'))
        elif v['covered']:
            ok = bool(excerpts) and all(found(e, report) for e in excerpts)
            out.append(Verdict(item.id, item.kind, ok, evidence, '' if ok else 'unverified'))
        else:
            out.append(Verdict(item.id, item.kind, False, '', ''))
    return out
