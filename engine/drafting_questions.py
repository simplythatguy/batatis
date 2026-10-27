"""Stable unresolved drafting questions for completeness and the separate question-flow owner.

This module supplies data, never question order. A sourced answer is a confirmed pointed fact at
`drafting.questions.<draft_id>.<zero-based index>`; accepting prose does not create that answer.
"""
from __future__ import annotations

from dataclasses import dataclass

from .identify.answers import is_unknown_answer
from .models import Case
from .models_drafting import DraftQuestion
from .process_fields import ApplicantText, latest_fact
from .drafting_sources import aliases
from .reference_selection import _within


@dataclass(frozen=True)
class OpenDraftQuestion:
    id: str
    draft_id: str
    field: str
    draft_field: str
    question: DraftQuestion


def open_questions(case: Case, *, accepted_only: bool = False) -> list[OpenDraftQuestion]:
    out = []
    for draft in case.drafting.drafts if case.drafting else []:
        if draft.status == 'rejected' or (accepted_only and draft.status != 'accepted'):
            continue
        if draft.field.startswith('section_c.') and draft.field.endswith('.explanation'):
            provision = draft.field.removeprefix('section_c.').removesuffix('.explanation')
            if not any(_within(provision, selected) for selected in case.provisions):
                continue
        if draft.status == 'accepted':
            current = latest_fact(case, *aliases(draft.field))
            if (current is None or current.id != draft.accepted_fact_id or current.status != 'confirmed'
                    or current.value != draft.text or current.source.ref != 'applicant-draft:' + draft.id):
                continue  # Historical writing retains its questions, but no longer controls this field.
        for index, question in enumerate(draft.questions):
            field = f'drafting.questions.{draft.id}.{index}'
            answer = latest_fact(case, field)
            try:
                answered = (answer is not None and not answer.source.ref.startswith('applicant-draft:')
                            and not is_unknown_answer(str(answer.value))
                            and bool(ApplicantText.from_fact(answer).value.strip()))
            except ValueError:
                answered = False
            if not answered:
                out.append(OpenDraftQuestion(id=f'draft-question:{draft.id}:{index}', draft_id=draft.id,
                    field=field, draft_field=draft.field, question=question))
    return out
