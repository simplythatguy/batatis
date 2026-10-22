"""Deterministic information request built from findings, and the re-upload diff.

Every generated item asks the applicant for something. It never supplies the
missing value, never rewrites the applicant's text, never states compliance and
never records a decision. Officer edits are kept as officer-authored text.
"""
from __future__ import annotations

import hashlib
import re

from ..models_review import (DiffEntry, EditedItem, Finding, InformationRequest, InformationRequestItem,
                             ReviewDiff)

INTRO = ('To continue the administrative review of this variance application, please provide or confirm the '
         'items below. This request concerns completeness only; it is not a decision on the application.')

# Findings that are the officer's own documentation or registration duty are not asked of the applicant.
OFFICER_ONLY = {'division_c_2_3_1'}

# Generated text must never contain these (C5). Disclaimers are not generated into items.
FORBIDDEN = re.compile(
    r'\b(?:complies|compliant|in compliance|code-compliant|conforms to|is safe|approved|approve|'
    r'meets the code|satisfies the code|we have (?:filled|entered|added|corrected))\b', re.I)


def _where(finding: Finding) -> str:
    pointer = finding.pointers[0] if finding.pointers else None
    parts = []
    if finding.section in 'ABCD':
        parts.append(f'Section {finding.section}')
    if pointer is not None:
        if pointer.form_field:
            parts.append(f'field "{pointer.form_field}"')
        if pointer.page:
            parts.append(f'page {pointer.page} of {pointer.file}')
    return ', '.join(parts)


# Finding messages are written for the officer ("Ask the applicant to …"). The request is addressed to
# the applicant, so those officer-facing sentences are dropped from the copied message.
_OFFICER_SENTENCE = re.compile(r'\s*Ask the applicant\b[\s\S]*?\.(?=\s|$)')


def _ask(finding: Finding) -> str:
    return _OFFICER_SENTENCE.sub('', _ask_text(finding)).strip()


def _ask_text(finding: Finding) -> str:
    where = _where(finding)
    at = f' ({where})' if where else ''
    label = finding.label
    if finding.status == 'blank':
        return f'Please provide the {label}{at}. The field is blank.'
    if finding.status == 'not_found':
        return f'Please provide or point to the {label}{at}. The review could not find it.'
    if finding.problem in ('placeholder',):
        return f'Please replace the placeholder in the {label}{at} with the actual information.'
    if finding.problem in ('wrong_pair', 'pair_mismatch', 'no_table_row_pair'):
        return (f'Please check the objective and function for {label}{at} against the Division B attribution '
                f'table. {finding.message}')
    if finding.problem in ('nonexistent_provision', 'not_found_in_code'):
        return f'Please confirm the provision number for {label}{at}. {finding.message}'
    if finding.problem in ('superseded_edition',):
        return (f'Please confirm which NBC(AE) 2023, 2nd printing provision you are citing for {label}{at}, or label '
                'the earlier-edition number as historical context.')
    if finding.problem in ('page_mismatch',):
        return f'Please confirm the page reference for {label}{at}. {finding.message}'
    if finding.problem in ('intent_label',):
        return (f'Please label the intent statement{at} as national NBC 2020 explanatory material; '
                'it is not Alberta law.')
    if finding.problem in ('contradiction',):
        return f'Please confirm which value is correct{at}. {finding.message}'
    if finding.problem in ('no_responsible',):
        return f'Please name the person or organisation responsible for {label}{at}.'
    if finding.problem in ('no_date',):
        return f'Please give the issue or revision date of {label}{at}.'
    if finding.problem in ('generic', 'thin', 'unrelated', 'stated_as_fact'):
        return (f'Please expand the {label}{at} so it addresses this specific departure, written by you. '
                f'{finding.message}')
    if finding.problem in ('missing_row',):
        return f'Please add a Section C row for {label}. {finding.message}'
    if finding.problem in ('not_mentioned',):
        return (f'Please state in the documentation {label}{at}, or say that it does not apply. '
                f'{finding.message}')
    if finding.problem in ('absent',):
        return f'Please include the {label}{at}. {finding.message}'
    if finding.problem in ('signature_unread',):
        return f'Please confirm that the application is signed and dated{at}.'
    return f'Please provide or confirm the {label}{at}. {finding.message}'


def item_id(key: str) -> str:
    return 'ir_' + hashlib.sha256(key.encode()).hexdigest()[:10]


def render(request: InformationRequest) -> str:
    lines = [request.intro.strip(), '']
    number = 0
    for item in request.items:
        if item.included:
            number += 1
            lines.append(f'{number}. {item.text.strip()}')
    return '\n'.join(lines).strip()


def build(findings: list[Finding]) -> InformationRequest:
    items = []
    seen = set()
    for finding in findings:
        if finding.field in OFFICER_ONLY or finding.routed_to == 'officer':
            continue
        if finding.key in seen:
            continue
        seen.add(finding.key)
        text = _ask(finding)
        if FORBIDDEN.search(text):
            # A message carried from a finding must not smuggle verdict language into a request.
            text = f'Please provide or confirm the {finding.label}.'
        items.append(InformationRequestItem(
            id=item_id(finding.key), finding_key=finding.key, section=finding.section, field=finding.field,
            text=text, included=finding.status != 'not_found', officer_check=finding.status == 'not_found'))
    request = InformationRequest(intro=INTRO, items=items)
    request.text = render(request)
    return request


def edit(request: InformationRequest, items: list[EditedItem], intro: str | None) -> InformationRequest:
    """Replace the item list. Existing ids keep their link; new ids are officer items."""
    by_id = {item.id: item for item in request.items}
    out = []
    for index, change in enumerate(items):
        current = by_id.get(change.id) if change.id else None
        if change.id and current is None:
            raise KeyError(change.id)
        if current is None:
            out.append(InformationRequestItem(id=f'ir_officer_{index}_{item_id(change.text)[3:9]}', text=change.text,
                                              authored_by='officer', included=change.included))
            continue
        authored = current.authored_by if change.text == current.text else 'officer'
        out.append(current.model_copy(update={'text': change.text, 'included': change.included,
                                              'authored_by': authored}))
    updated = request.model_copy(update={'items': out, 'edited': True,
                                         'intro': intro if intro is not None else request.intro})
    updated.text = render(updated)
    return updated


def open_gaps(findings: list[Finding]) -> dict[str, Finding]:
    """Applicant gaps. Not-found items are the officer's checks and officer-routed items are not the
    applicant's to resolve, so neither counts in "x of y gaps resolved"."""
    return {finding.key: finding for finding in findings
            if finding.field not in OFFICER_ONLY and finding.routed_to != 'officer' and finding.status != 'not_found'}


def diff(previous_version: int, previous: list[Finding], current: list[Finding]) -> ReviewDiff:
    before, after = open_gaps(previous), open_gaps(current)

    def entry(finding: Finding) -> DiffEntry:
        return DiffEntry(key=finding.key, section=finding.section, label=finding.label, message=finding.message)

    resolved = [entry(before[key]) for key in before if key not in after]
    still = [entry(after[key]) for key in before if key in after]
    new = [entry(after[key]) for key in after if key not in before]
    statement = f'{len(resolved)} of {len(before)} gaps resolved'
    if still:
        statement += f', {len(still)} still open'
    if new:
        statement += f', {len(new)} new'
    return ReviewDiff(previous_version=previous_version, previous_gaps=len(before), resolved=resolved,
                      still_open=still, new=new, statement=statement)
