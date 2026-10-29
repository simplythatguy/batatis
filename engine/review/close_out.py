"""Close-out of a decided application: the 10-day copy to the Safety Codes Council and the record package.

Deterministic from the saved case and its package reviews. The officer sends the
copy and records that here; Batatis never sends, registers or decides anything.
Bulletins: IB-2025-11-18 (copy of each variance to the Council within 10 days of
issuance; supporting documents retained and supplied on request) and
IB-2026-10-01 (from 2026-12-01 the Orders and Variances Portal is the sole method;
the officer registers, for one specific location, with the supporting documentation).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..data.jurisdictions.time_zones import ALBERTA_TIME_ZONE
from ..models_review import CloseOut, Pointer, RecordItem, RecordPackage, ReviewSession
from .bulletins import BULLETINS, PORTAL_URL
from .workspace import build as workspace

DAYS = 10
# Every authority Batatis serves is in Alberta: a 7:53 PM decision on Oct 28 is dated Oct 28, not by UTC.
LOCAL = ZoneInfo(ALBERTA_TIME_ZONE)
# Outcomes that end the file; a return remains open for applicant revisions.
FINAL_OUTCOMES = {'accept', 'refuse'}


def _decided(case) -> datetime | None:
    if case.decision is None or case.decision.outcome not in FINAL_OUTCOMES:
        return None
    return datetime.fromisoformat(case.decision.at)


def _day(value: str) -> str:
    """The app's date: "Oct 28, 2026", in Alberta time."""
    moment = datetime.fromisoformat(value)
    day = (moment.astimezone(LOCAL) if moment.tzinfo else moment).date()
    return f'{day:%b} {day.day}, {day.year}'


def _count(n: int, word: str) -> str:
    return f'{"No" if n == 0 else n} {word}{"" if n == 1 else "s"}'


def build(case, sessions: list[ReviewSession], recorded, documents, *, today: date | None = None, gaps=()) -> CloseOut | None:
    decided = _decided(case)
    if decided is None:
        return None
    today = today or datetime.now(LOCAL).date()
    recorded = recorded if recorded is not None and recorded[0] == case.decision.at else None
    accepted = case.decision.outcome == 'accept'
    issued_on = recorded.issued_on if accepted and recorded else None
    due = date.fromisoformat(issued_on) + timedelta(days=DAYS) if issued_on else None
    record = f'case:{case.id}'
    sent = bool(accepted and issued_on and recorded.sent_at)
    from ..process_fields import latest_fact
    location = latest_fact(case, 'municipal_address', 'civic_address', 'address')
    sent_requests = [s for s in sessions if s.information_request.message_id]
    latest = sessions[-1] if sessions else None
    send = [
        RecordItem(label='Copy of the variance as issued',
                   detail=(f'Issued {_day(issued_on)}.' if issued_on else
                           'Administratively complete · technical review next. Record issuance when the variance is issued.'),
                   present=bool(issued_on),
                   source=Pointer(file=record)),
        RecordItem(label='The single location the variance is for',
                   detail=str(location.value) if location and location.value else 'Not in the saved case: confirm it.',
                   present=bool(location and location.value),
                   source=Pointer(file=record, quote=str(location.value)) if location and location.value else None),
    ] if accepted else []
    retain = [
        RecordItem(label='Section C code references and attributions',
                   detail='; '.join(row.citation for row in case.section_c) or 'None saved.',
                   present=bool(case.section_c), source=Pointer(file=record)),
        RecordItem(label='Supporting documents',
                   detail='; '.join(f'{row.title.value} ({"attached" if row.file else "listed only"})' for row in documents)
                   or 'None listed.', present=bool(documents), source=Pointer(file=record)),
        RecordItem(label='Information requests and applicant revisions',
                   detail=f'{_count(len(sent_requests), "request")} sent; applicant changes are in the submission history.',
                   present=True, source=Pointer(file=record)),
        RecordItem(label='Latest administrative package review',
                   detail=(f'{_day(latest.created_at)}: '
                           f'{_count(workspace(latest, case, gaps).tally.required, "required item")}, '
                           f'{workspace(latest, case, gaps).tally.to_check} to check.')
                   if latest else 'No package review was run.', present=latest is not None,
                   source=Pointer(file=record)),
        RecordItem(label='Decision record and status history',
                   detail=f'{_count(len(case.status_history), "status change")}.', source=Pointer(file=record)),
    ]
    package = RecordPackage(
        send_to_council=send, retain_on_file=retain,
        basis=[f'IB-2025-11-18 {BULLETINS["IB-2025-11-18"]["title"]}',
               f'IB-2026-10-01 {BULLETINS["IB-2026-10-01"]["title"]}', PORTAL_URL],
        note=('IB-2025-11-18: the officer sends a copy of each variance to the Safety Codes Council within 10 days of issuance; '
              'supporting documents are retained and supplied on request. IB-2026-10-01: from 2026-12-01 the '
              'officer registers through the Orders and Variances Portal, for one specific location, including the '
              'supporting documentation. Registration is not Council approval. This list is a reminder, not a '
              'determination.'))
    return CloseOut(case_id=case.id, outcome=case.decision.outcome, decided_at=case.decision.at,
                    issued_on=issued_on, issued_by_name=recorded.issued_by_name if issued_on else None,
                    due_date=due.isoformat() if due else None, days_remaining=(due - today).days if due else None,
                    overdue=bool(due and not sent and today > due), sent=sent,
                    sent_at=recorded.sent_at if sent else None,
                    sent_by_name=recorded.sent_by_name if sent else None, record_package=package)
