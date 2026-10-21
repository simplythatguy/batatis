"""Turn an applicant's answer to an identify question into a case fact.

Ported from PR #12. Dev's facts have only `confirmed` and `unconfirmed` statuses, so an unknown or
"not sure" answer is stored as an unconfirmed fact with no value (it does not stop identification),
and a real answer is stored unconfirmed so the applicant confirms it later. Replaces an earlier
answer to the same question.
"""
from __future__ import annotations

import re

from engine.models import Fact, Source

_UNKNOWN = re.compile(r"^\s*(?:not sure|unsure|unknown|don'?t know|do not know|no idea|n/?a|\?+|idk)\s*\.?\s*$", re.I)


def is_unknown_answer(text: str | None) -> bool:
    return not (text or '').strip() or bool(_UNKNOWN.match(text or ''))


def apply_answers(case, answers) -> list[Fact]:
    created: list[Fact] = []
    for answer in answers or []:
        data = answer.model_dump() if hasattr(answer, 'model_dump') else dict(answer)
        raw = '' if data.get('answer') is None else str(data.get('answer'))
        field = data.get('field') or data.get('question_id') or 'identify.answer'
        unknown = is_unknown_answer(raw)
        case.facts = [fact for fact in case.facts if fact.field != field]
        fact = Fact(field=field, value=None if unknown else raw.strip(), kind='pointed',
                    source=Source(type='user_text', ref='identify answer', quote=raw.strip() or 'unknown'),
                    status='unconfirmed')
        case.facts.append(fact)
        created.append(fact)
    return created
