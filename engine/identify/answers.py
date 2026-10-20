"""Turn an applicant's answer to an identify question into a case fact.

"Not sure" and unknown stay on the case as status `unknown` and do not stop identification.
A real answer is stored unconfirmed so the next question asks to confirm it.
"""
from __future__ import annotations

from engine.identify.departure import is_unknown_answer
from engine.models import Fact, Source


def apply_answers(case, answers) -> list[Fact]:
    created: list[Fact] = []
    for answer in answers or []:
        data = answer.model_dump() if hasattr(answer, 'model_dump') else dict(answer)
        raw = '' if data.get('answer') is None else str(data.get('answer'))
        field = data.get('field') or data.get('question_id') or 'identify.answer'
        unknown = is_unknown_answer(raw)
        case.facts = [fact for fact in case.facts if fact.field != field]
        fact = Fact(
            field=field,
            value=None if unknown else raw.strip(),
            kind='pointed',
            source=Source(type='user_text', ref='identify answer', quote=raw.strip() or 'unknown'),
            status='unknown' if unknown else 'unconfirmed',
        )
        case.facts.append(fact)
        created.append(fact)
    return created
