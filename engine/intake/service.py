"""One intake run on a case: read the description and the dropped files, then update the ledger.

A re-run replaces the facts the previous run left unconfirmed and keeps everything the applicant
confirmed. A fact whose value the applicant already confirmed is not added again. The description
itself is stored as the applicant's own confirmed words (`project.description`), as the web does.
"""
from __future__ import annotations

import hashlib
from ..models import Case, Fact, Source
from ..models_intake import IntakeRecord
from . import model as model_pass
from .extract import DESCRIPTION, DESCRIPTION_REF, Extraction, Origin, Outbound, read_file, read_text, scrubbed
from .rules import ROLES


def run(text: str | None, files: list[tuple[str, str, bytes]], *, codes=None,
        outbound: Outbound = scrubbed, transport: model_pass.Transport | None = None,
        status: str = 'off') -> Extraction:
    """Extraction over the description and each (file id, name, bytes). No ledger change."""
    out = Extraction()
    if text and text.strip():
        out.merge(read_text(text, Origin(DESCRIPTION), codes=codes, outbound=outbound,
                            transport=transport, status=status))
    for file_id, name, data in files:
        out.merge(read_file(file_id, name, data, codes=codes, outbound=outbound, transport=transport,
                            status=status))
    if transport is not None and out.model.status == 'off':
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
    case.intake = IntakeRecord(
        text_sha256=hashlib.sha256(text.encode()).hexdigest() if text else None,
        pointers=[pointer for pointer in extraction.pointers if pointer.fact_id in kept_ids],
        files=extraction.files, model=extraction.model, conflicts=extraction.conflicts,
        unresolved_citations=extraction.unresolved)
    return added
