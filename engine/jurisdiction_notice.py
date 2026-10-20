"""Jurisdiction form notices. Administrative only.

The Calgary sentence says the City form is an addition to this SCC form.
It prints the City guide URL and leaves whether both are wanted with the officer.
It does not say the City accepts the Safety Codes Council form.
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
CALGARY_FORM_SOURCE = (
    'https://www.calgary.ca/content/dam/www/tools-and-resources/'
    'guide-to-applying-for-an-alternative-solution.pdf'
)


def calgary_form_notice_text(source: str = CALGARY_FORM_SOURCE) -> str:
    """The Calgary sentence. The link is filled from the source argument, which defaults to the City URL."""
    return (
        "Calgary also asks for its own Request for Specific Variance form "
        f"(in the City's Guide to Applying for an Alternative Solution: {source}). "
        "Keep this SCC form and appendix; ask your Safety Codes Officer whether they want both."
    )


CALGARY_FORM_NOTICE = calgary_form_notice_text()


def calgary_form_notice(case: Case) -> str | None:
    """The verified Calgary sentence when Case.jurisdiction.id is calgary. Otherwise none."""
    jurisdiction = case.jurisdiction
    if jurisdiction is None or jurisdiction.id.strip().casefold() != 'calgary':
        return None
    return CALGARY_FORM_NOTICE
