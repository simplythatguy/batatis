"""Product approval versus a site variance, as data the UI renders.

The summary and bullets are the sourced record in product_approval_vs_variance.
NBC sentences are cited by provision and page. Their text is not pasted, so the
notice carries no quoted code text. The unverified notes in that record are not
stated: no Act section creating a product approval, and nothing about whether a
CCMC listing counts in place of an evaluation report.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

# Plain summary from that record. It is the card's lead sentence.
SUMMARY = (
    'A product approval and a variance answer different questions. Product approval is market-wide: '
    'a CCMC evaluation report, or one from an evaluator the Provincial Building Administrator has '
    'approved, can be used anywhere in Alberta to show the product meets the code. A variance '
    '(alternative solution) is a decision about one building or site: a safety codes officer accepts '
    'it when it gives about the same or better safety, documents it under Division C 2.3.1, and '
    'registers it with the Safety Codes Council. A province-wide STANDATA variance from the Provincial '
    'Building Administrator is the exception, but it needs a province-wide issue, not one company\'s '
    'product. So a manufacturer wanting "approval across Alberta" needs an evaluation report; a pilot '
    'house can go ahead on a site variance in the meantime.'
)

_ROLE_FIELDS = ('role', 'applicant.role', 'applicant_type')
_SCOPE_FIELDS = ('scope', 'jurisdiction_wide')
_PROVINCE = re.compile(r'\b(?:province[-\s]?wide|across alberta)\b', re.I)


class RouteCitation(BaseModel):
    """One source for a bullet. `excerpt` is omitted for NBC code text."""

    model_config = ConfigDict(extra='forbid')
    source: str
    page: int | None = None
    url: str | None = None
    excerpt: str | None = None


class RouteBullet(BaseModel):
    model_config = ConfigDict(extra='forbid')
    claim: str
    citations: list[RouteCitation]


class RouteNotice(BaseModel):
    """Summary plus the sourced bullets. The UI renders these fields."""

    model_config = ConfigDict(extra='forbid')
    summary: str
    bullets: list[RouteBullet]


def _cite(source: str, *, page: int | None = None, url: str | None = None,
          excerpt: str | None = None) -> RouteCitation:
    # NBC code text is cited, not quoted. Other excerpts are the source's own words.
    if source.startswith('NBC'):
        excerpt = None
    return RouteCitation(source=source, page=page, url=url, excerpt=excerpt)


_BULLETS = (
    RouteBullet(
        claim='CCMC (NRC) evaluates construction products for code compliance to help manufacturers get market acceptance.',
        citations=[_cite(
            'NRC, Canadian Construction Materials Centre (web page)',
            url='https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre',
            excerpt='The Canadian Construction Materials Centre (CCMC) assesses compliance with Canadian building, energy and safety codes.',
        )],
    ),
    RouteBullet(
        claim=('Alberta recognises CCMC evaluation reports, and those of organizations approved by the '
               'Provincial Building Administrator, as a way to show code compliance.'),
        citations=[_cite('NBC(AE) 2023 2nd printing, Div A 1.2.2.1.(2)', page=38)],
    ),
    RouteBullet(
        claim=('The PBA approves other evaluators by STANDATA (e.g. QAI Laboratories, 23-BCI-005; '
               'also 23-BCI-006, -007, -013, -040 per the local STANDATA set).'),
        citations=[_cite(
            'STANDATA 23-BCI-005, Approved organization - QAI Laboratories (May 2024)',
            page=1,
            url=('https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/'
                 '57cebce9-5fe6-4583-a0bd-f2e4c7eedec9/download/ma-23-bci-005-approved-organization-qai-laboratories.pdf'),
            excerpt=('This interpretation recognizes QAI Laboratories as an approved organization that issues '
                     'evaluation reports that may be used to determine compliance with the requirements of the NBC(AE).'),
        )],
    ),
    RouteBullet(
        claim=('A province-wide variance is requested from the Provincial Building Administrator, applies '
               'everywhere in Alberta, and must address a province-wide issue; these are published as '
               'STANDATA variances (23-BCV series).'),
        citations=[
            _cite('NBC(AE) 2023 2nd printing, Div C 2.2.1.2.(1)', page=729),
            _cite('NBC(AE) 2023 2nd printing, Div C Note A-2.2.1.2.', page=743),
            _cite(
                'STANDATA 23-BCV-001, Window opening control devices (2024-04)',
                page=3,
                url=('https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/'
                     '01b622f0-f4a1-426d-b15f-ffc25e725949/download/ma-standata-variance-building-23-bcv-001-2024-04.pdf'),
                excerpt='This VARIANCE is applicable throughout the Province of Alberta.',
            ),
        ],
    ),
    RouteBullet(
        claim=('A site-specific variance is issued by a safety codes officer (or an Administrator) when the '
               'alternative gives approximately equivalent or greater safety; the officer must notify an Administrator.'),
        citations=[
            _cite(
                'Safety Codes Act, RSA 2000 c S-1, s.38(1)',
                page=31,
                url='https://kings-printer.alberta.ca/documents/Acts/S01.pdf',
                excerpt=('An Administrator or a safety codes officer may issue a written variance with respect to any '
                         'thing, process or activity to which this Act applies if the Administrator or officer is of '
                         'the opinion that the variance provides approximately equivalent or greater safety performance'),
            ),
            _cite(
                'Safety Codes Act s.38(3)',
                page=31,
                url='https://kings-printer.alberta.ca/documents/Acts/S01.pdf',
                excerpt='A safety codes officer on issuing a variance shall notify an Administrator.',
            ),
        ],
    ),
    RouteBullet(
        claim=('For building, the officer must document the alternative solution per Division C 2.3.1 and send '
               'each variance to the Safety Codes Council within 10 days.'),
        citations=[
            _cite(
                'SCC Information Bulletin IB-2025-11-18, Mandatory Documentation of Variances',
                page=2,
                url='https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf',
                excerpt='Submit a copy of each variance to the Safety Codes Council within 10 days of issuance.',
            ),
            _cite(
                'IB-2025-11-18',
                page=2,
                url='https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf',
                excerpt='Document alternative solutions as required by Division C of the applicable code.',
            ),
        ],
    ),
    RouteBullet(
        claim=('From December 1, 2026 variances are registered through the SCC Orders and Variances Portal; '
               'registration is not Council approval.'),
        citations=[
            _cite(
                'SCC Information Bulletin IB-2026-10-01, Orders and Variances Registration Changes',
                page=2,
                url='https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf',
                excerpt='Variances must be registered in OVP at the time of issuance or as soon as reasonably practicable thereafter.',
            ),
            _cite(
                'IB-2026-10-01',
                page=1,
                url='https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf',
                excerpt='Registration of an order or variance through OVP does not constitute Council approval of that order or variance',
            ),
        ],
    ),
    RouteBullet(
        claim='The Act lets an Administrator record a variance and the location it applies to (variance register).',
        citations=[_cite(
            'Safety Codes Act s.62',
            page=51,
            url='https://kings-printer.alberta.ca/documents/Acts/S01.pdf',
            excerpt=('An Administrator may place an entry on the relevant information system that briefly indicates '
                     'the subject-matter of a variance and the location of the thing, process or activity to which '
                     'the variance applies.'),
        )],
    ),
)


def _latest(case, fields: tuple[str, ...]):
    return next((fact for fact in reversed(case.facts) if fact.field in fields), None)


def is_manufacturer(case) -> bool:
    fact = _latest(case, _ROLE_FIELDS)
    return fact is not None and 'manufacturer' in str(fact.value or '').casefold()


def is_province_wide(case) -> bool:
    """The jurisdiction scope is a province-wide request, not a single site."""
    fact = _latest(case, _SCOPE_FIELDS)
    if fact is None or fact.value is None:
        return False
    return bool(_PROVINCE.search(str(fact.value)))


def route_notice(case) -> RouteNotice | None:
    """The card as soon as the role is a manufacturer, or the scope is province-wide."""
    if not is_manufacturer(case) and not is_province_wide(case):
        return None
    return RouteNotice(summary=SUMMARY, bullets=list(_BULLETS))
