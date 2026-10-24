"""Submission history and a factual diff, never a claim that a requested fix is sufficient."""
import json

from .account_models import ReviewSnapshot, Submission, SubmissionChange
from .models import Case
from .process_fields import PROCESS_ALIASES

_ALIASES = {
    'owner_name': ('owner_name', 'owner', 'section_a.owner_name'),
    'application_date': ('application_date', 'request_date', 'date', 'section_a.date'),
    'civic_address': ('civic_address', 'municipal_address', 'municipalAddress', 'address'),
    'legal_description': ('legal_description', 'legalDescription', 'section_b.legal_description'),
    'representative': ('representative', 'owner_rep_name', 'applicant_name'),
    'mailing_address': ('mailing_address', 'mailingAddress'),
    'alternative_description': ('alternative_description', 'alternative'),
    **{key: (*aliases, *(f'process.{alias}' for alias in aliases)) for key, aliases in PROCESS_ALIASES.items()},
}
_FIELD = {alias: key for key, aliases in _ALIASES.items() for alias in aliases}


def comparison_values(values: dict[str, str]) -> dict[str, str]:
    """One change per saved value, including snapshots made before this projection.

    Evidence writes retain facts and an EvidenceItem. Equal representations describe
    one edit. Conflicting legacy values stay separate so the comparison loses nothing.
    The original return snapshot remains unchanged.
    """
    def listing(key):
        return key.startswith('evidence.') and '.listing.' in key

    result = {key: value for key, value in values.items() if not listing(key)}
    for key, value in values.items():
        if not listing(key):
            continue
        canonical = key.replace('.listing.', '.', 1)
        if canonical not in result:
            result[canonical] = value
        elif result[canonical] != value:
            result[key] = value
    return result


def snapshot(case: Case, returned_at: str) -> ReviewSnapshot:
    values = {'title': case.title or '', 'authority': case.authority or '',
              'jurisdiction': case.jurisdiction.name if case.jurisdiction else '',
              'provisions': ', '.join(case.provisions)}
    for fact in case.facts:
        value = fact.value if isinstance(fact.value, str) else json.dumps(fact.value, ensure_ascii=False)
        # A new fact id or user-click source alone is not a changed answer.
        values[_FIELD.get(fact.field, fact.field)] = value + (' (unconfirmed)' if fact.status != 'confirmed' or fact.kind == 'proposed' else '')
    for item in case.evidence:
        for field, value in item.model_dump(exclude={'id', 'kind'}).items():
            values[f'evidence.{item.id}.listing.{field}'] = str(value) if value is not None else ''
    return ReviewSnapshot(returned_at=returned_at, authority=case.authority, values=comparison_values(values))


def remember_decision(case: Case) -> None:
    """Backfill a legacy current decision before replacing it; never recreate a claim from it."""
    if case.decision and case.decision not in case.decision_history:
        case.decision_history.append(case.decision.model_copy(deep=True))


def submit_round(case: Case, store, at: str) -> int:
    number = max(case.submission_number, 1 if case.status == 'returned' else 0) + 1
    baseline = case.return_snapshot if case.status == 'returned' else None
    before = comparison_values(baseline.values) if baseline else {}
    after = snapshot(case, at).values
    changes = [SubmissionChange(field=field, before=before.get(field), after=after.get(field))
               for field in sorted(before.keys() | after.keys()) if before.get(field) != after.get(field)] if baseline else []
    remember_decision(case)
    case.submissions.append(Submission(number=number, at=at, by_id=case.owner_id, authority=case.authority,
        returned_at=case.decision.at if case.decision and case.decision.outcome == 'return' else None,
        comparison_available=baseline is not None, changes=changes))
    # Preserve only the current reservation, after checking its present privileges.
    # An earlier decision/reviewer name never gives someone a new exclusive claim.
    claimant = store.get_user(case.claim.reviewer_id) if case.claim else None
    if not (claimant and claimant.onboarded and claimant.role == 'reviewer'
            and claimant.authority == case.authority and claimant.id != case.owner_id):
        case.claim = None
    case.decision = None
    return number
