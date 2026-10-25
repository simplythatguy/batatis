"""Judged coverage of reference items, with every positive verdict tied to an exact excerpt of the report.

One request per case grades all of its items. A covered item must come with an excerpt that occurs in
the report, or it is scored as not covered (the judge cannot credit text the report does not contain).
Prohibitions (review points that say what an answer must not do) are classified by their wording, not
by the judge: they pass unless the judge shows a violating excerpt that occurs in the report.
Verdicts are cached by (judge version, model, effort, request, report, items).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import httpx

from . import ledger
from .gold import Item

VERSION = 'judge-v3'
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
  proposed, stated versus assumed, decided versus argued). Paraphrase is fine. A related fact, a partial
  fact missing its key value, or a bare heading does not cover it.
- R (review point): what a good answer must do or address. Covered when the report clearly addresses
  that specific point, through a fact it reports, a flag or note, a question it asks, or an item it lists
  as missing. Generic text that would fit any case does not cover a specific point.
- B (boundary): covered only when the report explicitly says what the item describes.

Lines under "FROM THE REQUEST TEXT" only repeat what the user wrote in the request. They can cover
an F item, but they never cover an R or B item: those need the assistant's own facts, notes, flags,
questions or missing items.

Some items are prohibitions (marked "prohibition": true): something the answer must not do. For those,
set covered to false only when the report does that thing, and put the violating excerpt in evidence;
otherwise set covered to true with empty evidence.

For every other item: when covered is true, evidence must be the shortest exact excerpt of the report
(copied character for character, at most 300 characters) that shows the coverage; when covered is false,
evidence is "". Judge only from the report. Do not fill gaps with outside knowledge. When unsure, false."""


def schema() -> dict:
    return {'type': 'object', 'additionalProperties': False, 'required': ['items'], 'properties': {
        'items': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                             'required': ['id', 'covered', 'evidence'],
                                             'properties': {'id': {'type': 'string'}, 'covered': {'type': 'boolean'},
                                                            'evidence': {'type': 'string'}}}}}}


def is_prohibition(item: Item) -> bool:
    """A point with a second clause after ';' also asks for something, so it is graded as a requirement."""
    return item.kind == 'R' and ';' not in item.text and bool(PROHIBITION.search(item.text))


def _norm(text: str) -> str:
    text = unicodedata.normalize('NFKC', text or '').casefold()
    text = re.sub(r'[‘’“”"\'`]', '', text)
    text = re.sub(r'[‐-―]', '-', text)
    return re.sub(r'\s+', ' ', text).strip(' .,;:')


def found(evidence: str, report: str) -> bool:
    excerpt = _norm(evidence)
    if len(excerpt) < 4:
        return False
    if excerpt in _norm(report):
        return True
    # A long excerpt the judge shortened with an ellipsis: every part must occur, in order.
    parts = [p for p in re.split(r'\s*(?:\.\.\.|…)\s*', excerpt) if len(p) >= 4]
    if len(parts) < 2:
        return False
    body, at = _norm(report), 0
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
    blob = json.dumps({'v': VERSION, 'm': model, 'e': effort, 'q': request, 'r': report,
                       'i': [(i.id, i.kind, i.text) for i in items]}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _call(model: str, effort: str, user: str) -> dict:
    key = (os.environ.get('OPENAI_API_KEY') or '').strip()
    body = {'model': model, 'reasoning_effort': effort, 'max_completion_tokens': 16000,
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
            'response_format': {'type': 'json_schema',
                                'json_schema': {'name': 'coverage', 'strict': True, 'schema': schema()}}}
    with httpx.Client(timeout=300, follow_redirects=False) as client:
        response = client.post(URL, json=body, headers={'Authorization': 'Bearer ' + key})
        response.raise_for_status()
        data = response.json()
    return json.loads(data['choices'][0]['message']['content'])


def grade(request: str, report: str, items: list[Item], *, model: str, effort: str,
          book: ledger.Ledger | None = None) -> list[Verdict]:
    if not items:
        return []
    key = _key(model, effort, request, report, items)
    path = CACHE / key[:2] / f'{key}.json'
    if path.exists():
        payload = json.loads(path.read_text())
    else:
        user = json.dumps({'request': request, 'report': report,
                           'items': [{'id': i.id, 'kind': i.kind, 'prohibition': is_prohibition(i), 'text': i.text}
                                     for i in items]}, ensure_ascii=False)
        token = ledger.CURRENT.set(book or ledger.Ledger())
        try:
            payload = _call(model, effort, user)
        finally:
            ledger.CURRENT.reset(token)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f'.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, path)
    by_id = {v.get('id'): v for v in payload.get('items') or [] if isinstance(v, dict)}
    out = []
    for item in items:
        v = by_id.get(item.id)
        if v is None:
            out.append(Verdict(item.id, item.kind, is_prohibition(item), '', 'missing_verdict'))
            continue
        evidence = str(v.get('evidence') or '')
        if is_prohibition(item):
            violated = (not v.get('covered')) and found(evidence, report)
            out.append(Verdict(item.id, item.kind, not violated, evidence, 'violation' if violated else ''))
        elif v.get('covered'):
            ok = found(evidence, report)
            out.append(Verdict(item.id, item.kind, ok, evidence, '' if ok else 'unverified'))
        else:
            out.append(Verdict(item.id, item.kind, False, '', ''))
    return out
