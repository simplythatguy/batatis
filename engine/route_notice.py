"""Tell a manufacturer, as soon as the role is known, which application this tool prepares.

The notice is informational. It does not switch the variance form. A sentence stays
only when codedb or IB-2026-10-01, as quoted in this repo, supports it.

- One site, and a variance that relies on a jurisdictional alternative solution:
  IB-2026-10-01, quoted in docs/implementation-plan.md. "All variances must be
  registered individually, for a specific location, including those relying on
  jurisdictional alternative solutions."
- Section B checkbox: the revised form that bulletin requires. docs/implementation-plan.md
  records the field as "has been submitted to the Safety Codes Council for review
  for jurisdictional use." The form link is the one that section cites.
- CCMC: codedb NBC(AE) Division A Sentence 1.2.2.1.(2). The database has no public
  URL for that sentence, so the notice cites the sentence id and does not add one.
"""
from __future__ import annotations

import re

from .models import Case

# docs/implementation-plan.md, the IB-2026-10-01 quotation and the form it requires.
IB_2026_10_01_URL = (
    'https://ebs.safetycodes.ab.ca/documents/webdocs/SR/'
    'IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf'
)
SCC_FORM_URL = 'https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf'
# codedb provisions, doc NBC-AE, division A, id 1.2.2.1.(2).
CCMC_SENTENCE = '1.2.2.1.(2)'

_ROLE_FIELDS = ('role', 'applicant.role', 'applicant_type')
_SCOPE_FIELDS = ('scope', 'jurisdiction_wide')
_PROVINCE = re.compile(r'\b(?:province[-\s]?wide|across alberta)\b', re.I)


def _latest(case: Case, fields: tuple[str, ...]):
    return next((fact for fact in reversed(case.facts) if fact.field in fields), None)


def is_manufacturer(case: Case) -> bool:
    fact = _latest(case, _ROLE_FIELDS)
    return fact is not None and 'manufacturer' in str(fact.value or '').casefold()


def is_province_wide(case: Case) -> bool:
    """The jurisdiction scope is a province-wide request, not a single site."""
    fact = _latest(case, _SCOPE_FIELDS)
    if fact is None or fact.value is None:
        return False
    return bool(_PROVINCE.search(str(fact.value)))


def route_notice(case: Case) -> str | None:
    """Plain notice as soon as the role is a manufacturer, or the scope is province-wide."""
    if not is_manufacturer(case) and not is_province_wide(case):
        return None
    return (
        'A variance covers one site. This tool prepares a site variance application. '
        'IB-2026-10-01 says all variances must be registered individually, for a specific location, '
        'including those relying on jurisdictional alternative solutions '
        f'({IB_2026_10_01_URL}). '
        'The revised variance form that bulletin requires has a Section B checkbox for whether '
        'the proposal has been submitted to the Safety Codes Council for review for jurisdictional use '
        f'({SCC_FORM_URL}). '
        f'Division A Sentence {CCMC_SENTENCE} lets an evaluation report from the Canadian Construction '
        'Materials Centre be used in determining compliance.'
    )
