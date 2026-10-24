"""Read-only contextual applicant questions. An answer is never a technical determination.

Completeness gaps deliberately do not contain every uncertainty. Keep these question identities
and their actual answer fields independent of gaps so a return can request clarification.
"""
from __future__ import annotations

from .identify.answers import is_unknown_answer
from .identify.decisions import stable_id
from .intake.questions import PROBE_BY_FIELD
from .models import Case, Fact
from .process_fields import latest_fact

_ALIASES = {
    'owner_name': ('owner_name', 'owner', 'section_a.owner_name'),
    'municipal_address': ('municipal_address', 'municipalAddress', 'civic_address', 'address'),
    'mailing_address': ('mailing_address', 'mailingAddress'),
    'legal_description': ('legal_description', 'legalDescription', 'section_b.legal_description'),
    'alternative_description': ('alternative_description', 'alternative'),
    'storeys': ('storeys', 'building.storeys'),
}


def _answer(fact: Fact | None, *, abstained: bool = False) -> tuple[str | None, str]:
    if fact is None:
        return ('Not sure', 'not_sure') if abstained else (None, 'unanswered')
    if fact.source.ref == 'Answer withdrawn by applicant' or (fact.value == '' and fact.status == 'unconfirmed'):
        return None, 'withdrawn'
    raw = '' if fact.value is None else str(fact.value).strip()
    normalized = raw.replace('_', ' ').replace('-', ' ').replace('’', "'").lower().removeprefix('i ').rstrip('.!?').removesuffix(' yet')
    if raw and is_unknown_answer(normalized):
        return 'Not sure', 'not_sure'
    if fact.value is None and fact.source.quote and is_unknown_answer(fact.source.quote):
        return 'Not sure', 'not_sure'
    if not raw:
        return None, 'unanswered'
    label = {'yes': 'Yes', 'no': 'No', 'True': 'Yes', 'False': 'No'}.get(raw, raw)
    return label, 'answered' if fact.status == 'confirmed' and fact.kind != 'proposed' else 'unconfirmed'


def _source(fact: Fact | None, default: str) -> tuple[str, str | None]:
    if fact is None:
        return default, None
    if fact.source.type == 'file':
        label = f'Applicant file{f", page {fact.source.page}" if fact.source.page is not None else ""}'
    else:
        label = fact.source.ref or default
    return label, fact.source.quote


def review_questions(case: Case) -> list[dict]:
    """Saved decisions, legacy description-card answers, intake abstentions and matching questions.

    The original planner drops Not sure questions from its next plan. Its stable probe supplies
    their wording; a later saved answer changes the displayed state without deleting the question.
    This read neither runs a provider nor changes the ledger, provisions, gaps or decisions.
    """
    out = []
    latest = {fact.field: fact for fact in case.facts}
    for field, fact in latest.items():
        if not field.startswith('codecheck.'):
            continue
        answer, state = _answer(fact)
        # New clicks retain the question as their source quote. Old clicks quoted just the answer.
        quote = (fact.source.quote or '').strip()
        if quote.endswith('?') and quote not in {'?', '??'}:
            text = quote
        elif field == 'codecheck.desc-storeys':
            text = 'How many storeys is the building?'
        else:
            text = 'Which part of the proposed design needs clarification?'
        source, excerpt = _source(fact, 'Applicant code check')
        if text.startswith('Which part of the proposed design'):
            description = latest.get('project.description')
            if description and description.value:
                excerpt = f'Saved click: {fact.source.quote or answer}. Current project description: {description.value}'
        out.append(dict(id=field, field=field, text=text, provision_id=None, answer=answer, state=state,
                        source=source, source_detail=excerpt, origin='code_check'))

    result = case.identify
    if result:
        for article, decision in result.decisions.items():
            card = next((card for card in result.articles if card.provision == article), None)
            title = f' ({card.title})' if card and card.title else ''
            out.append(dict(
                id=decision.open_question_id or stable_id(case.id, 'oq', article), field=f'identify.{article}',
                text=f'Does your design differ from Article {article}{title}?',
                provision_id=card.provision_id or article if card else article,
                answer={'yes': 'Yes', 'no': 'No', 'not_sure': 'Not sure'}[decision.decision],
                state='not_sure' if decision.decision == 'not_sure' else 'answered',
                source='Applicant code check', source_detail=f'Selected by the applicant · {decision.decided_at}',
                origin='code_check'))
        for question in result.open_questions:
            fact = latest_fact(case, *_ALIASES.get(question.field, (question.field,)))
            answer, state = _answer(fact)
            source, excerpt = _source(fact, 'Code identification question · unanswered by applicant')
            out.append(dict(id=question.id, field=question.field, text=question.text,
                            provision_id=question.provision, answer=answer, state=state, source=source,
                            source_detail=excerpt or question.why, origin='code_matching'))

    plan = case.intake.plan if case.intake else None
    for qid in dict.fromkeys(plan.not_sure if plan else []):
        field = qid.removeprefix('intake.')
        probe = PROBE_BY_FIELD.get(field)
        stored = next((q for q in plan.questions if q.id == qid), None)
        if not probe and not stored:
            # An old or imported unknown is still visible, with a readable fallback, never its raw id.
            text = 'What information about the project still needs clarification?'
        else:
            text = stored.text if stored else probe.text
            conflict = next((item for item in case.intake.conflicts if item.field == field), None)
            if not stored and conflict:
                said = ', '.join(f'"{quote}"' for quote in dict.fromkeys(conflict.quotes))
                text = f'You wrote {said}. {probe.text}'
        fact = latest_fact(case, *_ALIASES.get(field, (field,)))
        answer, state = _answer(fact, abstained=True)
        source, excerpt = _source(fact, 'Applicant intake answer · Not sure')
        out.append(dict(id=qid, field=field, text=text, provision_id=stored.provision if stored else None,
                        answer=answer, state=state, source=source,
                        source_detail=excerpt or (f'Question context: {probe.why}' if probe else None), origin='intake'))
    # A later identification can drop a candidate. Its officer-requested clarification is still
    # part of the returned record, with the original wording, until a person reviews the response.
    known = {question['id'] for question in out}
    decisions = [*case.decision_history, *([case.decision] if case.decision else [])]
    for decision in reversed(decisions):
        if decision.outcome != 'return':
            continue
        for item in decision.items:
            if not item.field or not item.field.startswith('clarification.'):
                continue
            qid = item.field.removeprefix('clarification.')
            if qid in known:
                continue
            known.add(qid)
            out.append(dict(id=qid, field=item.field, text=item.note, provision_id=None,
                            answer=None, state='unanswered', source='Officer clarification request',
                            source_detail=f'{decision.by_name} · {decision.at}', origin='officer_request'))
    for question in out:
        clarification = latest.get(f"clarification.{question['id']}")
        if clarification is not None:
            answer, state = _answer(clarification)
            source, excerpt = _source(clarification, 'Applicant clarification')
            question['clarification'] = dict(answer=answer, state=state, source=source, source_detail=excerpt)
    return out
