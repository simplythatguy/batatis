"""Human application-scope decisions, independent from retrieval and departure."""
from __future__ import annotations

from engine.models import now


def record(result, requirement_id, body, codes):
    item = next((r for r in result.requirements if r.id == requirement_id), None)
    if item is None:
        raise KeyError(requirement_id)
    if item.source_status != 'verified' or not item.provision_id or not item.division:
        raise ValueError('A missing source cannot be confirmed into existence')
    source = codes.provision(item.provision_id, item.division)
    if source is None or 'NBC(AE) 2023 p2' not in (source.get('citation') or ''):
        raise ValueError('Requirement must resolve to NBC(AE) 2023 second printing')
    from .requirement_corpus import load, SourceUnavailable
    try:
        current_source = load(codes.db_path).source
    except SourceUnavailable as error:
        raise ValueError(str(error)) from None
    if result.requirement_coverage.source != current_source:
        raise ValueError('The code source changed; rerun identification before deciding applicability')
    if not body.reason.strip():
        raise ValueError('Record the facts or conditions behind this decision')
    if body.role == 'admin' and item.division == 'B':
        raise ValueError('Division B is not an administrative division')
    if body.role == 'varied' and item.division != 'B':
        raise ValueError('A varied benchmark must be a Division B requirement')
    if body.disposition == 'include' and body.role == 'unresolved':
        raise ValueError('Keep unresolved applicability in review')
    if body.disposition == 'include' and body.role == 'varied' and (result.benchmark.provision != item.provision_id
                                 or result.benchmark.departure_status != 'confirmed'):
        raise ValueError('Confirm the benchmark and departure before assigning the varied role')
    item.disposition = body.disposition
    item.role = body.role
    item.applicability = 'unknown' if body.disposition == 'review' else 'confirmed'
    item.human_confirmed = body.disposition != 'review'
    item.confirmation_fingerprint = result.input_fingerprint if item.human_confirmed else None
    item.confirmation_reason = body.reason.strip()
    item.confirmed_at = now()
    item.needs_review = body.disposition == 'review'
    item.review_reasons.append(f'Applicant {body.disposition} decision at {now()}: {body.reason.strip()}')
    result.requirement_coverage.human_confirmed = sum(r.human_confirmed for r in result.requirements)
    # Full applicability remains undetermined even if this one record was reviewed.
    return item


def departure(result, article, decision, *, reason=None):
    """A no-departure response never deletes supporting requirements."""
    for item in result.requirements:
        if item.division != 'B' or item.provision_id != article:
            continue
        if decision == 'yes':
            item.role, item.disposition, item.applicability = 'varied', 'include', 'confirmed'
            item.human_confirmed, item.needs_review = True, False
            item.confirmation_fingerprint = result.input_fingerprint
            item.confirmation_reason = reason or 'Applicant confirmed that the design departs from this requirement.'
            item.confirmed_at = now()
        elif item.role == 'varied':
            item.role = 'supporting'
            item.confirmation_reason = 'Applicant withdrew the departure; the supporting requirement is retained.'
            item.confirmed_at = now()
            if decision == 'not_sure':
                item.disposition, item.applicability = 'review', 'unknown'
                item.human_confirmed, item.needs_review = False, True
                item.confirmation_fingerprint = None
        result.requirement_coverage.human_confirmed = sum(r.human_confirmed for r in result.requirements)
