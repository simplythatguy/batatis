"""Close-out of a decided application: the 10-day copy to the Safety Codes Council and the record package.

Deterministic from the saved case and its package reviews. The officer sends the
copy and records that here; Batatis never sends, registers or decides anything.
Bulletins: IB-2025-11-18 (copy of each variance to the Council within 10 days of
issuance; supporting documents retained and supplied on request) and
IB-2026-10-01 (from 2026-12-01 the Orders and Variances Portal is the sole method;
the officer registers, for one specific location, with the supporting documentation).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..models_review import CloseOut, Pointer, RecordItem, RecordPackage, ReviewSession
from .bulletins import BULLETINS, PORTAL_URL

DAYS = 10
# Outcomes that end the file; a return remains open for applicant revisions.
FINAL_OUTCOMES = {'accept', 'refuse'}


def _decided(case) -> datetime | None:
    if case.decision is None or case.decision.outcome not in FINAL_OUTCOMES:
        return None
    return datetime.fromisoformat(case.decision.at)


def build(case, sessions: list[ReviewSession], recorded, documents, *, today: date | None = None) -> CloseOut | None:
    decided = _decided(case)
    if decided is None:
        return None
    today = today or datetime.now(timezone.utc).date()
    due = decided.date() + timedelta(days=DAYS)
    record = f'case:{case.id}'
    sent = recorded is not None and recorded[0] == case.decision.at
    from ..process_fields import latest_fact
    location = latest_fact(case, 'municipal_address', 'civic_address', 'address')
    sent_requests = [s for s in sessions if s.information_request.sent_at]
    latest = sessions[-1] if sessions else None
    send = [
        RecordItem(label='Copy of the variance as decided',
                   detail=f'SCC variance form for case {case.id}, Part 1 as submitted and the officer\'s decision '
                          f'recorded {case.decision.at[:10]} ({case.decision.by_name}).',
                   source=Pointer(file=record)),
        RecordItem(label='The single location the variance is for',
                   detail=str(location.value) if location and location.value else 'Not in the saved case: confirm it.',
                   present=bool(location and location.value),
                   source=Pointer(file=record, quote=str(location.value)) if location and location.value else None),
    ]
    retain = [
        RecordItem(label='Section C code references and attributions',
                   detail='; '.join(row.citation for row in case.section_c) or 'None saved.',
                   present=bool(case.section_c), source=Pointer(file=record)),
        RecordItem(label='Supporting documents',
                   detail='; '.join(f'{row.title.value} ({row.file or "listed only"})' for row in documents)
                   or 'None listed.', present=bool(documents), source=Pointer(file=record)),
        RecordItem(label='Information requests sent and the applicant\'s replies',
                   detail=f'{len(sent_requests)} request(s) sent; replies are in the case messages.',
                   present=True, source=Pointer(file=record)),
        RecordItem(label='Latest administrative package review',
                   detail=(f'Version {latest.version} of {latest.created_at[:10]}: '
                           f'{len([f for f in latest.findings if f.status != "not_found"])} open item(s).')
                   if latest else 'No package review was run.', present=latest is not None,
                   source=Pointer(file=record)),
        RecordItem(label='Decision record and status history',
                   detail=f'{len(case.status_history)} status change(s).', source=Pointer(file=record)),
    ]
    package = RecordPackage(
        send_to_council=send, retain_on_file=retain,
        basis=[f'IB-2025-11-18 {BULLETINS["IB-2025-11-18"]["title"]}',
               f'IB-2026-10-01 {BULLETINS["IB-2026-10-01"]["title"]}', PORTAL_URL],
        note=('IB-2025-11-18: the officer sends a copy of each variance to the Safety Codes Council within 10 days; '
              'supporting documents are retained and supplied on request. IB-2026-10-01: from 2026-12-01 the '
              'officer registers through the Orders and Variances Portal, for one specific location, including the '
              'supporting documentation. Registration is not Council approval. This list is a reminder, not a '
              'determination.'))
    return CloseOut(case_id=case.id, outcome=case.decision.outcome, decided_at=case.decision.at,
                    due_date=due.isoformat(), days_remaining=(due - today).days,
                    overdue=not sent and today > due, sent=sent, sent_at=recorded[1] if sent else None,
                    sent_by_name=recorded[2] if sent else None, record_package=package)
