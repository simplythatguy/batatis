"""SCC Information Bulletin citations. Titles and links only.

Index: https://www.safetycodes.ab.ca/council-information/information-bulletins/
No licence is claimed. Bulletin paragraphs are not copied into this module.
Links and reminder wording ported from PR 11 at 006e1fc. Not refreshed here;
this saved-case slice does not change the canonical completeness/export gates.
"""
from __future__ import annotations

INDEX_URL = 'https://www.safetycodes.ab.ca/council-information/information-bulletins/'
PORTAL_URL = 'https://ovp.safetycodes.ab.ca/'

# IB-2026-10-01: from 2026-12-01 the Orders and Variances Portal is the sole
# method; only a safety codes officer registers; registration is not Council
# approval; each variance is for one specific location; supporting documentation
# is included when the officer registers; IB-2025-11-18 remains in effect;
# unnecessary personal information is removed or redacted.
# IB-2025-11-18: the officer documents a building, fire, or plumbing alternative
# solution under Division C, Section 2.3.1, sends a copy of each variance (not
# the supporting file) to the Safety Codes Council within 10 days of issuance,
# and keeps supporting documents to supply on request.
# IB-2026-10-16: the authority having jurisdiction is the accredited
# organisation or the Alberta Safety Codes Authority, not the individual officer.
BULLETINS = {
    'IB-2026-10-01': {
        'title': 'Orders and Variances Registration Changes',
        'url': 'https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf',
    },
    'IB-2025-11-18': {
        'title': 'Mandatory Documentation of Variances',
        'url': 'https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf',
    },
    'IB-2026-10-16': {
        'title': 'Clarifying Authority Having Jurisdiction (AHJ) Under the Safety Codes Act',
        'url': 'https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf',
    },
}
