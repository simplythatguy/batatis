"""One intake run on a case: read the description and the dropped files, then update the ledger.

What the applicant already gave is used as read (see `settle`), so the deck asks only what is
missing or unclear. A re-run replaces the facts the previous run left unconfirmed and keeps
everything confirmed. A fact whose value is already confirmed is not added again. The description
itself is stored as the applicant's own confirmed words (`project.description`), as the web does.
"""
from __future__ import annotations

import hashlib
import re

from ..identify.answers import is_unknown_answer
from ..identify.title import short_title, title_should_replace
from ..models import Case, Fact, Source
from ..models_intake import FactPointer, FieldConflict, IntakeRecord
from . import model as model_pass
from . import review as review_pass
from .extract import DESCRIPTION, DESCRIPTION_REF, Extraction, Origin, Outbound, read_file, read_text, scrubbed
from .plan import OVERRIDDEN, SCOPE_FIELD, build_plan, description, overridden
from .questions import PROBE_BY_FIELD, issued_questions
from .rules import ENUMS, FIELDS, LEGAL_PARTS, PERSONAL, ROLES, read
from .scope import classify
from .text import NUMBER, number


def _run(text, files, codes, outbound, transport, status, cache=None) -> Extraction:
    out = Extraction()
    if text and text.strip():
        out.merge(read_text(text, Origin(DESCRIPTION), codes=codes, outbound=outbound,
                            transport=transport, status=status))
    for file_id, name, data in files:
        out.merge(read_file(file_id, name, data, codes=codes, outbound=outbound, transport=transport,
                            status=status, cache=cache))
    return out


def run(text: str | None, files: list[tuple[str, str, bytes]], *, codes=None,
        outbound: Outbound = scrubbed, transport: model_pass.Transport | None = None,
        status: str = 'off', review_transport: review_pass.Transport | None = None,
        review_status: str = 'off') -> Extraction:
    """Extraction over the description and each (file id, name, bytes). No ledger change.

    With a model, the rules and form passes run over every source first, so a name or address read
    from one file is scrubbed from every text the model sees. The document review reads every page."""
    cache: dict = {}                                  # each PDF is parsed once across both passes
    first = _run(text, files, codes, outbound, None, status, cache)
    if transport is None and review_transport is None:
        return first
    sources = ([review_pass.read_source(file_id, name, data) for file_id, name, data in files]
               if transport is not None else None)
    candidates = [(f.field, f.value) for f in first.facts]
    candidates += [(c.field, value) for c in first.conflicts for value in c.values]
    personal = [str(value) for field, value in candidates if field in PERSONAL and str(value).strip()
                and not (field in LEGAL_PARTS and str(value).isdigit() and len(str(value)) < 5)]
    if sources is not None:
        personal += review_pass.personal_values([text or '', *(s.name for s in sources),
                                                *(t for s in sources for _, t in s.pages)])
    out = first
    if transport is not None:
        out = _run(text, files, codes, lambda s, own: outbound(s, personal), transport, status, cache)
        if out.model.status == 'off':
            out.model.status = 'not_needed'
    if review_transport is not None:
        out.review = review_pass.run(text or '', files, outbound=lambda s, own: outbound(s, [*own, *personal]),
                                     transport=review_transport, status=review_status, codes=codes, sources=sources)
    return out


def _latest(case: Case, name: str) -> Fact | None:
    return next((fact for fact in reversed(case.facts)
                 if fact.field == name or (name == 'storeys' and fact.field == 'building.storeys')), None)


CONTEXT = ('statement.', 'claimed_provision')     # quoted sentences and cited articles: context, never a choice


def settle(case: Case, extraction: Extraction) -> None:
    """Use what the applicant gave without asking again; leave at most one thing to check per field.

    A value whose words were found and checked in the source is confirmed as read: quoted context
    sentences and cited articles always, any other field when everything read agrees and no earlier
    answer the applicant gave says otherwise. Repeats collapse to the first. Where the sources disagree, the
    applicant's own description wins; failing that, a field the planner can ask about becomes one
    conflict question, and any other keeps its first reading to check. A guess the model could not
    point to stays a proposal only while the field has nothing better. A computed value follows its inputs.
    """
    checked = {p.fact_id for p in extraction.pointers if p.verified}
    conflicted = {c.field for c in extraction.conflicts}
    key = lambda fact: repr(fact.value)                                  # noqa: E731
    by_field: dict[str, list[Fact]] = {}
    for fact in extraction.facts:
        if fact.kind != 'computed':
            by_field.setdefault(fact.field, []).append(fact)
    kept: dict[str, Fact] = {}                                           # id -> fact kept
    for field, facts in by_field.items():
        sure = [f for f in facts if f.kind == 'pointed' and f.id in checked]
        unique = list({key(f): f for f in reversed(sure)}.values())[::-1]   # first reading of each value
        prior = _latest(case, field)
        # Only what the applicant answered or clicked outranks a new reading; an earlier reading does not.
        given = prior is not None and prior.status == 'confirmed' and prior.source.type != 'file' \
            and prior.source.ref != DESCRIPTION_REF
        agrees = lambda f: not given or prior.value == f.value          # noqa: E731
        if field.startswith(CONTEXT):
            chosen, confirm = unique, True
        elif not sure:
            chosen, confirm = facts[:1], False
        else:
            own = list({key(f): f for f in reversed(sure) if f.source.type == 'user_text'}.values())[::-1]
            if len(unique) == 1 and field not in conflicted and agrees(unique[0]):
                chosen, confirm = unique, True
            elif len(own) == 1 and agrees(own[0]):
                chosen, confirm = own, True
            elif given:
                chosen, confirm = [f for f in unique if f.value != prior.value][:1], False
            elif field in PROBE_BY_FIELD:
                # Short values become one "You wrote two things" choice; long passages get the plain question.
                if field not in conflicted and all(len(str(f.value)) <= 60 for f in unique):
                    extraction.conflicts.append(FieldConflict(
                        field=field, values=[f.value for f in unique][:6], quotes=[f.source.quote or '' for f in unique][:6],
                        source_ref=unique[0].source.ref or '', page=unique[0].source.page))
                chosen, confirm = [], False
            else:
                chosen, confirm = unique[:1], False
        for fact in chosen:
            if confirm:
                fact.status = 'confirmed'
            kept[fact.id] = fact
    for fact in extraction.facts:
        if fact.kind == 'computed' and fact.inputs and all(i in kept for i in fact.inputs):
            if all(kept[i].status == 'confirmed' for i in fact.inputs):
                fact.status = 'confirmed'
            kept[fact.id] = fact
    extraction.facts = [fact for fact in extraction.facts if fact.id in kept]
    extraction.pointers = [pointer for pointer in extraction.pointers if pointer.fact_id in kept]


def apply(case: Case, text: str | None, extraction: Extraction, *, role: str | None = None) -> list[Fact]:
    """Write this run to the case. Returns the facts added by the run."""
    previous_text = description(case)
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
    settle(case, extraction)
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
    # An identical rough-B reading reuses the fact, and must also keep its known automatic provenance.
    pointers += [pointer.model_copy(update={'fact_id': same[pointer.fact_id]}) for pointer in extraction.pointers
                 if pointer.field == 'alternative_description' and pointer.fact_id in same
                 and same[pointer.fact_id] in previous]
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
        unresolved_citations=extraction.unresolved, plan=previous_plan, review=extraction.review)
    # Only sent/saved applicant context can name an untitled or legacy sentence-seeded
    # record. Keep an existing subject name, and always honor an explicit rename.
    generated = case.identify.title if case.identify else None
    name_text = text if text and text.strip() else description(case)
    if any(title_should_replace(case.title, prose, generated, manual=case.title_is_manual)
           for prose in (name_text, previous_text)):
        title = short_title(text or '', case.facts, None)
        if title != 'Variance application':
            case.title = title
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
    """Only questions issued for this case, including earlier plans. Validate the whole batch before writing."""
    plan = case.intake.plan if case.intake else None
    asked = {}
    if plan and plan.scope.status != 'redirect':
        asked = {q.id: q.field for q in issued_questions(case.facts, plan)}
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
            # Withdrawing a saved answer must not leave its old confirmed value in force.
            previous = _latest(case, field)
            if previous is None or previous.value in (None, ''):
                continue
        else:
            case.intake.plan.not_sure = [q for q in case.intake.plan.not_sure if q != qid]
        fact = Fact(field=field, value=value, kind='pointed', status='confirmed',
                    source=Source(type='user_text', ref='intake answer', quote=raw.strip()))
        # The answer settles the field: readings still waiting on it are no longer asked.
        case.facts = [f for f in case.facts if not (f.field == field and f.status == 'unconfirmed')]
        case.facts.append(fact)
        created.append(fact)
    refresh(case)
    return created


def _drop_redirects(case: Case) -> None:
    """Remove earlier computed redirects (and their pointers): each override or re-check supersedes them, and an
    unconfirmed one left behind would keep blocking export."""
    gone = {f.id for f in case.facts if f.field == SCOPE_FIELD and f.kind == 'computed'}
    if not gone:
        return
    case.facts = [f for f in case.facts if f.id not in gone]
    if case.intake is not None:
        case.intake.pointers = [p for p in case.intake.pointers if p.fact_id not in gone]


def override_scope(case: Case, building_code: bool) -> Fact:
    """The applicant says this is (or, undoing that, may not be) a building-code question. Their own click,
    always confirmed, so the click itself never blocks export; a redirect read again is a computed fact."""
    _drop_redirects(case)
    case.facts.append(Fact(
        field=SCOPE_FIELD, value=OVERRIDDEN if building_code else 'checked', kind='pointed', status='confirmed',
        source=Source(type='user_click', ref='intake:scope',
                      quote='This is a building-code question.' if building_code else 'Check the scope again.')))
    fact = case.facts[-1]
    if not building_code:
        found = _scope_fact(case)
        if found is not None:
            fact, start, end = found
            if case.intake is None:
                case.intake = IntakeRecord()
            case.intake.pointers.append(FactPointer(fact_id=fact.id, field=SCOPE_FIELD, method='rules',
                                                    source_ref=DESCRIPTION, start=start, end=end))
    refresh(case)
    return fact
