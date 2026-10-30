"""The officer's state, counts and acceptance gate, derived from one review and the shared rulebook.

The caller supplies check_completeness's gaps for the saved case. This module has no storage or rules
of its own; a dismissal changes the officer's record, never the automated finding or rulebook.
"""
from __future__ import annotations

from .information_request import covered as asked_already
from ..models_review import (AcceptGate, FindingState, RequestTarget, ReviewSession, ReviewTally,
                             RulebookGap, OfficerWorkspace)

PEER_SIGNAL = 'peer_review:signal'


def target(finding) -> RequestTarget:
    section = 'Alternative path' if finding.section == 'process' else f'Section {finding.section}'
    label = finding.label[:1].upper() + finding.label[1:]
    return RequestTarget(section=finding.section, field=finding.field, label=f'{section} · {label}'[:200])


def build(session: ReviewSession, case=None, gaps=(), *, codes_available: bool = True) -> OfficerWorkspace:
    findings = [f for f in session.findings if f.key != PEER_SIGNAL]
    blocking = [gap for gap in gaps if gap.severity == 'blocking'] if case is not None else []
    locked_fields = {gap.field for gap in blocking if gap.field}
    # Any finding on a rulebook field covers its gap: it is locked and counts as required (below).
    covered = {f.field for f in findings}
    rulebook = [RulebookGap(id=g.id, field=g.field, section=g.section, message=g.message)
                for g in blocking if not g.field or g.field not in covered]
    linked = {item.finding_key for item in session.information_request.items if item.finding_key}
    # A topic an open drafted question already asks is the officer's to check, not a second request.
    repeats = asked_already(findings)
    dispositions = {d.key: d for d in session.dispositions}
    states = []
    for finding in findings:
        locked = finding.field in locked_fields
        default = ('ask' if finding.routed_to == 'applicant' and finding.status != 'not_found'
                   and finding.key in linked and finding.key not in repeats else 'verify')
        disposition = dispositions.get(finding.key)
        state = FindingState(key=finding.key, state=default, locked=locked)
        if disposition is not None:
            state = FindingState(**disposition.model_dump(), locked=locked)
        # A rulebook duty cannot be cleared by an older dismissal, or an ask with no answer item.
        if locked and state.state == 'dismissed':
            state = FindingState(key=finding.key, state=default, locked=True)
        if state.state == 'ask' and finding.key not in linked:
            state = state.model_copy(update={'state': 'verify'})
        states.append(state)
    active = {s.key: s for s in states if s.state != 'dismissed'}
    tally = ReviewTally(
        required=sum((f.severity == 'blocking' or f.field in locked_fields) and f.key in active for f in findings)
        + len(rulebook),
        to_check=sum(f.severity == 'warning' and f.field not in locked_fields and f.key in active for f in findings),
        verify=sum(s.state == 'verify' for s in states), dismissed=len(states) - len(active),
        asked=sum((active[item.finding_key].state == 'ask' if item.finding_key in active else False)
                  if item.finding_key else item.included for item in session.information_request.items),
        rulebook=len(rulebook))
    current = case is not None and session.case_version == case.version
    if case is None:
        reason = 'Standalone packages cannot receive a decision'
    elif not current:
        reason = 'The application changed. Run the package review again.'
    elif not codes_available:
        reason = 'The code database is unavailable. The completeness rules could not be checked.'
    elif blocking:
        reason = 'The completeness rules still require information on the saved application'
    elif tally.required:
        reason = f'{tally.required} required {"item" if tally.required == 1 else "items"} still open'
    else:
        reason = ''
    return OfficerWorkspace(version=session.version, case_version=session.case_version, current=current, states=states,
                     rulebook=rulebook, tally=tally, gate=AcceptGate(can_accept=not reason, reason=reason))


def sync_request(session: ReviewSession, case=None, gaps=()) -> ReviewSession:
    """A linked item's inclusion and target belong to its finding, not to correspondence edits."""
    from .information_request import render
    if session.information_request.message_id:
        return session
    states = {state.key: state.state for state in build(session, case, gaps).states}
    findings = {finding.key: finding for finding in session.findings}
    items = []
    for item in session.information_request.items:
        if item.finding_key:
            finding = findings.get(item.finding_key)
            item = item.model_copy(update={'included': states.get(item.finding_key) == 'ask',
                                           'target': target(finding) if finding else None})
        items.append(item)
    request = session.information_request.model_copy(update={'items': items})
    request.text = render(request)
    return session.model_copy(update={'information_request': request})
