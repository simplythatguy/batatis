"""Current identification inputs, independent of persistence and provider transports.

The fingerprint covers source bytes as well as the fact ledger. Reading a saved
result never calls a provider. Document text is context, never confirmed authority.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

from engine.intake.rules import PERSONAL


@dataclass(frozen=True)
class CaseInput:
    text: str
    sha256: str
    gaps: tuple[str, ...]


def active_facts(case):
    # Only the latest value for a field is active, including an empty replacement.
    latest = {fact.field: fact for fact in case.facts}
    confirmed = {fact.field: fact for fact in case.facts if fact.status == 'confirmed' and fact.kind != 'proposed'}
    out = []
    for name, fact in sorted(latest.items()):
        if name in PERSONAL or name.startswith('citation.'):
            continue
        prior = confirmed.get(name)
        # A new model guess cannot erase a different applicant-confirmed value.
        if fact.value not in (None, '') and fact.status != 'confirmed' and prior is not None \
                and prior.value != fact.value:
            out.append(prior)
        out.append(fact)
    return out


def _files(case, store):
    if store is None:
        return []
    return [(meta, store.get_file(case.id, meta['id'])) for meta in (store.list_files(case.id) or [])]


def fingerprint(case, store=None) -> str:
    """All current identification inputs; excludes generated results and titles."""
    return _fingerprint(case, _files(case, store))


def _fingerprint(case, files) -> str:
    # What identification reads from a fact: its value, whether it is confirmed and how it was derived.
    # Re-confirming the same value ("Looks right") gives the fact a new id and a click source; that is
    # not an input change and must not make the result stale.
    payload = {
        'facts': [fact.model_dump(include={'field', 'value', 'status', 'kind', 'formula'})
                  for fact in active_facts(case)],
        'jurisdiction': case.jurisdiction.model_dump() if case.jurisdiction else None,
        'files': [{**meta, 'sha256': hashlib.sha256(saved['data']).hexdigest() if saved else None}
                  for meta, saved in files],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def compose(case, store=None, *, prose: str | None = None) -> CaseInput:
    """Use every readable page and label facts by status and origin, without truncation.

    Extraction uses intake's supported reader and reports its limits. It does not
    run a model, OCR, or treat a document's claimed code edition as current law.
    """
    from engine.intake.review import MAX_PAGES, read_source

    parts = []
    if prose and prose.strip():
        parts.append('Applicant description for this run:\n' + prose.strip())
    facts = active_facts(case)
    for fact in facts:
        if fact.value is None or fact.value == '':
            continue
        if prose is not None and fact.field == 'project.description':
            continue
        origin = f'{fact.source.type}:{fact.source.ref}'
        if fact.source.page is not None:
            origin += f':page {fact.source.page}'
        parts.append(f'Fact {fact.field} [{fact.status}; {fact.kind}; {origin}]: '
                     + json.dumps(fact.value, ensure_ascii=False))
    fields = [fact.field for fact in facts]
    gaps = [f'Conflicting supplied values for {name}; applicability requires confirmation.'
            for name in sorted(set(fields)) if fields.count(name) > 1]
    files = _files(case, store)
    for meta, saved in files:
        file_id = meta['id']
        if saved is None:
            gaps.append(f'Attachment {file_id} is unavailable.')
            continue
        source = read_source(file_id, meta['name'], saved['data'])
        if source.unread:
            gaps.append(f'Attachment {file_id}: {source.unread}.')
        if source.page_count > MAX_PAGES:
            gaps.append(f'Attachment {file_id}: pages after {MAX_PAGES} were not read.')
        if len(source.pages) < min(source.page_count, MAX_PAGES):
            gaps.append(f'Attachment {file_id}: some pages have no readable text.')
        for page, text in source.pages:
            if text.strip():
                parts.append(f'Unconfirmed document context [{file_id}; page {page}]:\n{text}')
    return CaseInput('\n\n'.join(parts), _fingerprint(case, files), tuple(gaps))


def is_requirement_run(result) -> bool:
    from .compact import requirement_screen
    return requirement_screen(result)


def refresh(case, store, codes, *, force=False):
    """Refresh locally after an input mutation, inside the caller's existing CAS.

    Historical provider profiles stay explicit-only. This calls the deterministic
    requirement path, never starts a job, never calls a model (the last model order
    carries over) and never writes storage itself.
    """
    if case.identify is not None and not is_requirement_run(case.identify):
        return
    from engine.identify.config import load_config
    from engine.identify.pipeline import run
    config = load_config()
    if config.screen != 'requirements':
        return
    if codes is None:
        if case.identify is not None:
            case.identify.stale = True
        return
    if not force and case.identify is not None and getattr(case.identify, 'input_sha256', None) == fingerprint(case, store):
        return
    started = time.monotonic()
    context = compose(case, store)
    if not context.text.strip():
        return
    previous = case.identify
    input_seconds = time.monotonic() - started
    output = run(context.text, codes=codes, config=config, facts=active_facts(case),
                 previous=previous, confirmed_provisions=case.provisions, rank=False)
    result = output.result
    result.trace.seconds = round(result.trace.seconds + input_seconds, 3)
    result.input_sha256 = context.sha256
    result.input_coverage_gaps = list(context.gaps)
    result.decisions = dict(previous.decisions) if previous else {}
    from .compact import compact_identify
    case.identify = compact_identify(result)
