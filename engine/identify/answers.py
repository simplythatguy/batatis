"""Turn an applicant's answer to an identify question into a case fact.

"Not sure" and unknown stay on the case as status `unknown` and do not stop identification.
A real answer is stored unconfirmed so the next question asks to confirm it.

Answering "is that one site or many?" with a province-wide or multi-site phrase sets
the jurisdiction-wide scope field.
"""
from __future__ import annotations

import re

from engine.identify.departure import is_unknown_answer
from engine.models import Fact, Source

# Phrases for the site question. "multiple sites" is jurisdiction-wide.
# "province-wide" and "across Alberta" are the province-wide scope.
_PROVINCE = re.compile(r'\b(?:province[-\s]?wide|across alberta)\b', re.I)
_MULTI_SITE = re.compile(r'\bmultiple sites\b', re.I)
SCOPE_FIELD = 'scope'
JURISDICTION_WIDE = 'jurisdiction'
PROVINCE_WIDE = 'province-wide'


def jurisdiction_wide_value(answer: str | None) -> str | None:
    """Canonical scope value, or None when the answer is not a multi-site phrase."""
    text = answer or ''
    if _PROVINCE.search(text):
        return PROVINCE_WIDE
    if _MULTI_SITE.search(text):
        return JURISDICTION_WIDE
    return None


def _upsert_scope(case, value: str, quote: str) -> Fact:
    case.facts = [fact for fact in case.facts if fact.field != SCOPE_FIELD]
    fact = Fact(
        field=SCOPE_FIELD, value=value, kind='pointed', status='unconfirmed',
        source=Source(type='user_text', ref='identify answer', quote=quote),
    )
    case.facts.append(fact)
    return fact


def apply_answers(case, answers) -> list[Fact]:
    created: list[Fact] = []
    for answer in answers or []:
        data = answer.model_dump() if hasattr(answer, 'model_dump') else dict(answer)
        raw = '' if data.get('answer') is None else str(data.get('answer'))
        field = data.get('field') or data.get('question_id') or 'identify.answer'
        unknown = is_unknown_answer(raw)
        wide = None if unknown else jurisdiction_wide_value(raw)
        value = None if unknown else (wide if field == SCOPE_FIELD and wide else raw.strip())
        case.facts = [fact for fact in case.facts if fact.field != field]
        fact = Fact(
            field=field,
            value=value,
            kind='pointed',
            source=Source(type='user_text', ref='identify answer', quote=raw.strip() or 'unknown'),
            status='unknown' if unknown else 'unconfirmed',
        )
        case.facts.append(fact)
        created.append(fact)
        if wide and field != SCOPE_FIELD:
            created.append(_upsert_scope(case, wide, raw.strip()))
    return created
