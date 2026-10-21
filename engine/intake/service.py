"""One intake run on a case: read the description and the dropped files, then update the ledger.

A re-run replaces the facts the previous run left unconfirmed and keeps everything the applicant
confirmed. A fact whose value the applicant already confirmed is not added again. The description
itself is stored as the applicant's own confirmed words (`project.description`), as the web does.
"""
from __future__ import annotations

import hashlib
import re

from ..identify.answers import is_unknown_answer
from ..models import Case, Fact, Source
from ..models_intake import FactPointer, IntakeRecord
from . import model as model_pass
from .extract import DESCRIPTION, DESCRIPTION_REF, Extraction, Origin, Outbound, read_file, read_text, scrubbed
from .plan import OVERRIDDEN, SCOPE_FIELD, build_plan, description, overridden
from .rules import ENUMS, FIELDS, PERSONAL, ROLES, read
from .scope import classify
from .text import NUMBER, number


def _run(text, files, codes, outbound, transport, status) -> Extraction:
    out = Extraction()
    if text and text.strip():
        out.merge(read_text(text, Origin(DESCRIPTION), codes=codes, outbound=outbound,
                            transport=transport, status=status))
    for file_id, name, data in files:
        out.merge(read_file(file_id, name, data, codes=codes, outbound=outbound, transport=transport,
                            status=status))
    return out


def run(text: str | None, files: list[tuple[str, str, bytes]], *, codes=None,
        outbound: Outbound = scrubbed, transport: model_pass.Transport | None = None,
        status: str = 'off') -> Extraction:
    """Extraction over the description and each (file id, name, bytes). No ledger change.

    With a model, the rules and form passes run over every source first, so a name or address read
    from one file is scrubbed from every text the model sees."""
    first = _run(text, files, codes, outbound, None, status)
    if transport is None:
        return first
    personal = [str(f.value) for f in first.facts if f.field in PERSONAL and len(str(f.value)) >= 3]
    out = _run(text, files, codes, lambda s, own: outbound(s, [*own, *personal]), transport, status)
    if out.model.status == 'off':
        out.model.status = 'not_needed'
    return out


def _latest(case: Case, name: str) -> Fact | None:
    return next((fact for fact in reversed(case.facts) if fact.field == name), None)


def apply(case: Case, text: str | None, extraction: Extraction, *, role: str | None = None) -> list[Fact]:
    """Write this run to the case. Returns the facts added by the run."""
    previous = {pointer.fact_id for pointer in (case.intake.pointers if case.intake else [])}
    case.facts = [fact for fact in case.facts if not (fact.id in previous and fact.status == 'unconfirmed')]
    if text and text.strip():
        current = _latest(case, 'project.description')
        if current is None or current.value != text:
            case.facts.append(Fact(field='project.description', value=text, kind='pointed', status='confirmed',
                                   source=Source(type='user_text', ref=DESCRIPTION_REF, quote=text)))
    if role in ROLES:
        current = _latest(case, 'applicant_role')
        if current is None or current.value != role or current.status != 'confirmed':
            case.facts.append(Fact(field='applicant_role', value=role, kind='pointed', status='confirmed',
                                   source=Source(type='user_click', ref='intake:role', quote=role)))
    added, kept_ids, same = [], set(), {}
    for fact in extraction.facts:
        if role in ROLES and fact.field == 'applicant_role':
            continue                                 # the role the applicant picked wins over a guess
        current = _latest(case, fact.field)
        if current is not None and current.status == 'confirmed' and current.value == fact.value:
            same[fact.id] = current.id
            continue
        if fact.kind == 'computed':
            fact.inputs = [same.get(i, i) for i in fact.inputs]
        case.facts.append(fact)
        added.append(fact)
        kept_ids.add(fact.id)
    # A computed fact needs its input in the ledger, and the pointer list only names stored facts.
    stored = {fact.id for fact in case.facts}
    for fact in list(added):
        if fact.kind == 'computed' and not all(i in stored for i in fact.inputs):
            case.facts.remove(fact)
            added.remove(fact)
            kept_ids.discard(fact.id)
    pointers = [pointer for pointer in extraction.pointers if pointer.fact_id in kept_ids]
    redirect = _scope_fact(case)
    if redirect is not None:
        fact, start, end = redirect
        added.append(fact)
        pointers.append(FactPointer(fact_id=fact.id, field=SCOPE_FIELD, method='rules', source_ref=DESCRIPTION,
                                    start=start, end=end))
    previous_plan = case.intake.plan if case.intake else None
    case.intake = IntakeRecord(
        text_sha256=hashlib.sha256(text.encode()).hexdigest() if text else None,
        pointers=pointers, files=extraction.files, model=extraction.model, conflicts=extraction.conflicts,
        unresolved_citations=extraction.unresolved, plan=previous_plan)
    refresh(case)
    return added


def _scope_fact(case: Case) -> tuple[Fact, int, int] | None:
    """AC2.3: a redirect is stored as a computed fact quoting the cue. It stays unconfirmed, so export is blocked."""
    if overridden(case):
        return None
    check = classify(description(case))
    source = _latest(case, 'project.description')
    if check.status != 'redirect' or source is None:
        return None
    fact = Fact(field=SCOPE_FIELD, value=check.regime.id, kind='computed', status='unconfirmed',
                formula=f'scope check: "{check.cue}" reads as {check.regime.name}', inputs=[source.id],
                source=Source(type='user_text', ref=DESCRIPTION_REF, quote=check.cue))
    case.facts.append(fact)
    return fact, check.start, check.end


def refresh(case: Case) -> None:
    """Recompute and store the plan (after an intake run, an answer, an override or a new identification)."""
    if case.intake is None:
        case.intake = IntakeRecord()
    case.intake.plan = build_plan(case)


class AnswerRejected(ValueError):
    """The answer is not for a question this case's plan asked, or cannot be read as that field."""


def _value(field: str, raw: str):
    kind = FIELDS.get(field, ('', 'text'))[1]
    text = raw.strip()
    if kind == 'text' or field not in FIELDS:
        return text
    if kind == 'bool':
        found = {'yes': True, 'y': True, 'true': True, 'no': False, 'n': False, 'false': False}.get(text.lower().rstrip('.'))
        if found is None:
            raise AnswerRejected(f'answer yes or no for {FIELDS[field][0].lower()}')
        return found
    if kind == 'enum' and text in ENUMS[field]:
        return text
    hits = [hit for hit in read(text).hits if hit.field == field]
    if kind in ('int', 'number') and not hits:
        match = re.search(NUMBER, text, re.I)
        value = number(match.group(0)) if match else None
        if value is not None and (kind == 'number' or isinstance(value, int)):
            return value
    if hits:
        return hits[0].value
    if field == 'sprinklered' and text.lower().rstrip('.') in ('yes', 'no'):
        return text.lower().rstrip('.')
    raise AnswerRejected(f'could not read {FIELDS[field][0].lower()} from the answer')


def answer(case: Case, answers: list[dict]) -> list[Fact]:
    """Answers to the stored plan's questions only. Each fills its own field. Checked before any is written."""
    asked = {q.id: q.field for q in (case.intake.plan.questions if case.intake and case.intake.plan else [])}
    checked = []
    for item in answers:
        qid, raw = item.get('question_id'), item.get('answer') or ''
        if not qid or qid not in asked:
            raise AnswerRejected('answer a question this plan asked (question_id)')
        if item.get('field') not in (None, '', asked[qid]):
            raise AnswerRejected('an answer can only fill its own question field')
        unknown = is_unknown_answer(raw)
        checked.append((qid, asked[qid], raw, None if unknown else _value(asked[qid], raw)))
    created = []
    for qid, field, raw, value in checked:
        if value is None:
            if qid not in case.intake.plan.not_sure:
                case.intake.plan.not_sure.append(qid)
            continue
        fact = Fact(field=field, value=value, kind='pointed', status='confirmed',
                    source=Source(type='user_text', ref='intake answer', quote=raw.strip()))
        case.facts.append(fact)
        created.append(fact)
    refresh(case)
    return created


def override_scope(case: Case, building_code: bool) -> Fact:
    """The applicant says this is (or is not) a building-code question. Recorded as their own click."""
    if building_code:
        fact = Fact(field=SCOPE_FIELD, value=OVERRIDDEN, kind='pointed', status='confirmed',
                    source=Source(type='user_click', ref='intake:scope', quote='This is a building-code question.'))
        case.facts.append(fact)
    else:
        case.facts.append(Fact(field=SCOPE_FIELD, value=None, kind='pointed', status='unconfirmed',
                               source=Source(type='user_click', ref='intake:scope', quote='Check the scope again.')))
        found = _scope_fact(case)
        fact = found[0] if found else case.facts[-1]
    refresh(case)
    return fact
