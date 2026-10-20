"""Jurisdiction form notices. Administrative only.

The Calgary sentence does not say the City accepts the Safety Codes Council form.
It points at the City's own request form and leaves the choice with the officer.
"""
from __future__ import annotations

from .models import Case

# City of Calgary, Guide to Applying for an Alternative Solution (Variance),
# 23 November 2023, step 3 under "How to obtain a variance":
# "Refer to the Request for Specific Variance form (attached). In accordance with
# SCC policy, the form must be completed and submitted for all variance
# applications regardless of what formal documentation is also submitted."
# https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf
# Listed from https://www.calgary.ca/development/permits/building-regulation-advisories.html
CALGARY_FORM_NOTICE = (
    "Calgary's guide asks for its own Request for Specific Variance form. "
    "Confirm with your Safety Codes Officer which form they accept."
)
CALGARY_FORM_SOURCE = (
    'https://www.calgary.ca/content/dam/www/tools-and-resources/'
    'guide-to-applying-for-an-alternative-solution.pdf'
)


def calgary_form_notice(case: Case) -> str | None:
    """The verified Calgary sentence when Case.jurisdiction.id is calgary. Otherwise none."""
    jurisdiction = case.jurisdiction
    if jurisdiction is None or jurisdiction.id.strip().casefold() != 'calgary':
        return None
    return CALGARY_FORM_NOTICE
