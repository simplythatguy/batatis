"""Turn an applicant's answer to an identify question into a case fact.

Ported from PR #12. An answer must name a question this case's identify run actually asked
(`question_id` from `open_questions`), and it can only fill that question's own field
(`identify.choice.<article>`). Any other id or field is rejected, so an answer can never replace
a confirmed fact such as `project.description`, `citation.*` or `evidence.*.file_ref`.

Dev's facts have only `confirmed` and `unconfirmed` statuses, so an unknown or "not sure" answer is
stored as an unconfirmed fact with no value (it does not stop identification), and a real answer is
stored unconfirmed so the applicant confirms it later. It replaces an earlier answer to the same question.
"""
from __future__ import annotations

import re

from engine.models import Fact, Source

_UNKNOWN = re.compile(r"^\s*(?:not sure|unsure|unknown|don'?t know|do not know|no idea|n/?a|\?+|idk)\s*\.?\s*$", re.I)
ANSWER_PREFIX = 'identify.'


class AnswerRejected(ValueError):
    """The answer does not belong to a question the identify flow asked on this case."""


def is_unknown_answer(text: str | None) -> bool:
    return not (text or '').strip() or bool(_UNKNOWN.match(text or ''))


def asked_fields(case) -> dict[str, str]:
    """question id -> the fact field that question fills, for the questions on the stored identify result."""
    result = getattr(case, 'identify', None)
    return {q.id: q.field for q in (result.open_questions if result else []) if q.field.startswith(ANSWER_PREFIX)}


def check_answers(case, answers) -> list[tuple[str, str]]:
    """[(field, raw answer)] or AnswerRejected. Checks every answer before any is applied."""
    asked = asked_fields(case)
    out = []
    for answer in answers or []:
        data = answer.model_dump() if hasattr(answer, 'model_dump') else dict(answer)
        question_id = data.get('question_id')
        if not question_id or question_id not in asked:
            raise AnswerRejected('answer a question this identification asked (question_id)')
        if data.get('field') not in (None, '', asked[question_id]):
            raise AnswerRejected('an answer can only fill its own question field')
        out.append((asked[question_id], '' if data.get('answer') is None else str(data.get('answer'))))
    return out


def apply_answers(case, answers) -> list[Fact]:
    created: list[Fact] = []
    for field, raw in check_answers(case, answers):
        unknown = is_unknown_answer(raw)
        case.facts = [fact for fact in case.facts if fact.field != field]
        fact = Fact(field=field, value=None if unknown else raw.strip(), kind='pointed',
                    source=Source(type='user_text', ref='identify answer', quote=raw.strip() or 'unknown'),
                    status='unconfirmed')
        case.facts.append(fact)
        created.append(fact)
    return created
