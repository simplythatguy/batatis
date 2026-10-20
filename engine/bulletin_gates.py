"""Administrative gates drawn from SCC Information Bulletins.

IB-2025-11-18: when issuing a variance, the safety codes officer documents the
alternative solution under Division C Section 2.3.1, sends a copy of each variance
(not the supporting file) to the Safety Codes Council within 10 days, and keeps
supporting documents to supply on request.
IB-2026-10-01: only a safety codes officer registers, for one specific location.
Registration is not Council approval.
The 10-day copy is a reminder, not a verdict and not an export blocker.
Bulletin text is not copied here.
"""
from __future__ import annotations

import re

from .bulletins import BULLETINS, INDEX_URL, PORTAL_URL
from .process_fields import alternative_path, confirmed_value

_PLACEHOLDERS = {'tbd', 'tobedetermined', 'tobeprovided', 'unknown', 'pending', 'na', 'notprovided',
                 'placeholder', 'none'}
_EXTRA_LOCATION = ('additional_location', 'second_location', 'extra_location')
DOC_FIELDS = ('division_c_2_3_1', 'division_c_documentation', 'div_c_2_3_1')
DOC_FIX = (
    'Include the Division C Section 2.3.1 documentation the safety codes officer needs to issue and '
    'register this variance. Do not draft it. IB-2025-11-18 places that documentation with the officer; '
    'it is not an applicant duty under the bulletin.'
)
LOC_FIX = (
    'Ask which single location this variance is for. A safety codes officer registers each variance for '
    'one specific location. Do not choose a location. IB-2026-10-01.'
)


def _missing(value) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    return re.sub(r'\W', '', value.casefold()) in _PLACEHOLDERS


def location_parts(civic: str, extras: list[str]) -> list[str]:
    """One civic value may list several locations only when split by ';' or a new line."""
    parts = [part.strip() for part in re.split(r'[;\n]', civic or '') if not _missing(part)]
    for extra in extras:
        if not _missing(extra):
            parts.append(extra.strip())
    return parts


def case_locations(case) -> list[str]:
    civic = confirmed_value(case, 'civic_address', 'municipal_address', 'municipalAddress', 'address') or ''
    primary = confirmed_value(case, 'civic_address')
    municipal = confirmed_value(case, 'municipal_address', 'municipalAddress')
    extras = []
    if (isinstance(primary, str) and isinstance(municipal, str)
            and not _missing(primary) and not _missing(municipal) and primary.strip() != municipal.strip()):
        civic = primary
        extras.append(municipal)
    for key in _EXTRA_LOCATION:
        value = confirmed_value(case, key)
        if isinstance(value, str):
            extras.append(value)
    return location_parts('' if civic is None else str(civic), extras)


def documentation_value(case):
    return confirmed_value(case, *DOC_FIELDS)


def applicant_reminder() -> dict:
    """IB-2025-11-18 copy of the issued variance. IB-2026-10-01: the officer registers."""
    return {
        'verdict': 'reminder',
        'bulletin_ids': ['IB-2025-11-18', 'IB-2026-10-01'],
        'text': (
            'Reminder, not a completeness verdict. IB-2025-11-18: the safety codes officer submits a copy '
            'of each variance to the Safety Codes Council within 10 days of issuance. That copy is the '
            'issued variance, not the supporting documentation. Supporting documents are retained and made '
            'available on request by an Administrator. IB-2026-10-01 keeps those requirements in effect. '
            'From 2026-12-01 the Orders and Variances Portal '
            f'({PORTAL_URL}) is the sole method, and only a safety codes officer registers an order or a '
            'variance there. Registration is not Council approval of the variance and does not transfer '
            'responsibility for the decision. This reminder does not decide that the application is complete.'
        ),
        'links': [INDEX_URL, BULLETINS['IB-2025-11-18']['url'], BULLETINS['IB-2026-10-01']['url'], PORTAL_URL],
    }


def bulletin_gaps(case) -> list:
    """Blocking administrative gaps. The copy deadline is not one of them."""
    from .completeness import Gap

    if not alternative_path(case):
        return []
    gaps = []
    if _missing(documentation_value(case)):
        gaps.append(Gap(
            id='IB-DOC:division_c_2_3_1', severity='blocking', section='B', field='division_c_2_3_1',
            message=('Your application appears to be missing the Division C Section 2.3.1 documentation '
                     'the safety codes officer needs to issue and register (IB-2025-11-18).'),
            fix_hint=DOC_FIX, citation='IB-2025-11-18'))
    if len(case_locations(case)) > 1:
        gaps.append(Gap(
            id='IB-LOC:single_location', severity='blocking', section='B', field='single_location',
            message=('Your application appears to be missing a single location for this variance; '
                     'more than one location is listed (IB-2026-10-01).'),
            fix_hint=LOC_FIX, citation='IB-2026-10-01'))
    return gaps
