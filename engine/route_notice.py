"""Tell a manufacturer, or a province-wide request, which application this tool prepares.

The notice is informational. It does not switch the variance form. Every route named
here is one the repo's research already documents, and each public page is a link
already recorded there. A route the research does not name is not invented.
"""
from __future__ import annotations

import re

from .models import Case

# evals/demo-cases/sources.md W12. Product evaluation, not a site variance.
CCMC_URL = (
    'https://nrc.canada.ca/en/certifications-evaluations-standards/'
    'canadian-construction-materials-centre'
)
# evals/demo-cases/sources.md W23, and docs/implementation-plan.md. A CCMC assessment
# is not a mandatory requirement.
CCMC_PAS_URL = (
    'https://nrc.canada.ca/en/certifications-evaluations-standards/'
    'canadian-construction-materials-centre/ccmc-publications/document.html?id=PAS-001&type=policy'
)
# evals/demo-cases/sources.md W11. A new product's alternative solution is submitted
# with the building permit and is site- and project-specific.
CALGARY_PRODUCT_URL = (
    'https://www.calgary.ca/content/dam/www/pda/pd/documents/building/advisories/'
    'b23-014-new-products-materials-and-systems-in-building-construction.pdf'
)
# research/facts/process-and-admin.md. Div C Article 2.2.1.2 and Note A-2.2.1.2.
# The code has no separate public URL in the repo; the citation is the documented source.
PROVINCIAL_ROUTE = (
    'NBC(AE) 2023 Division C Article 2.2.1.2 and Note A-2.2.1.2'
)
ASK_WHICH_ROUTE = 'ask the Safety Codes Officer or the province which route applies'

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
    """Plain notice, or None when this case is a single-site application by someone else."""
    if not is_manufacturer(case) and not is_province_wide(case):
        return None
    return (
        'Province-wide product acceptance is a different route from a single-site variance. '
        'This tool prepares a site variance application. '
        f'A CCMC evaluation is a product-acceptance route, not this site variance ({CCMC_URL}). '
        'Division A Sentence 1.2.2.1.(2) lets an evaluation report from the Canadian Construction '
        'Materials Centre be used in determining compliance. A CCMC assessment is not a mandatory '
        f'requirement ({CCMC_PAS_URL}). '
        f'A province-wide variance is a written request to the Provincial Building Administrator under '
        f'{PROVINCIAL_ROUTE}: the request has to show a province-wide issue, and an issued variance '
        'applies throughout Alberta. '
        'Calgary describes a new product\'s alternative solution as site- and project-specific, '
        f'submitted with the building permit ({CALGARY_PRODUCT_URL}). '
        f'For a route this research does not name, {ASK_WHICH_ROUTE}.'
    )
