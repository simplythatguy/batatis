"""Product acceptance versus a site variance, shown to manufacturers and jurisdiction-wide requests.

Ported from PR #44 (`engine/route_notice.py`): the sourced bullets. The summary is reworded so the two
halves stay distinct (SCC presentation): the variance is the officer's legal authorization under the
Safety Codes Act, s.38; the alternative solution is the proponent's evidence under NBC(AE) Division C,
2.3.1 of at least Division B performance. NBC sentences are cited by provision and page, not quoted.
"""
from __future__ import annotations

from ..models_intake import PlanSource, RouteBullet, RouteNotice

SUMMARY = (
    'Product acceptance and a variance answer different questions. Acceptance for use anywhere in Alberta comes '
    'from an evaluation report (CCMC, or an evaluator the Provincial Building Administrator has approved). A variance '
    'is for one building or site: the safety codes officer issues it under the Safety Codes Act, s.38, on the strength '
    'of an alternative solution, your evidence under NBC(AE) Division C, 2.3.1 that the design achieves at least the '
    'level of performance required by Division B in the attributed objectives and functions. A province-wide variance '
    'from the Provincial Building Administrator is for a province-wide issue, not one company\'s product. So a pilot '
    'building can go ahead on a site variance while an evaluation report is pursued.'
)
SCA = 'https://kings-printer.alberta.ca/documents/Acts/S01.pdf'
IB_2025 = ('https://ebs.safetycodes.ab.ca/documents/webdocs/SR/'
           'IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf')
# NBC(AE) citations here; a test checks each resolves in the code database.
NBC_CITED = (('A', '1.2.2.1.(2)'), ('C', '2.2.1.2.(1)'))

BULLETS = (
    RouteBullet(claim='CCMC (NRC) evaluates construction products against the codes to help manufacturers get market acceptance.',
                citations=[PlanSource(title='NRC, Canadian Construction Materials Centre',
                                      url='https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre')]),
    RouteBullet(claim='NBC(AE) recognises evaluation reports from CCMC and from organizations the Provincial Building '
                      'Administrator has approved as a way to show that a product meets the code.',
                citations=[PlanSource(title='NBC(AE) 2023 2nd printing, Div A 1.2.2.1.(2), PDF p.38')]),
    RouteBullet(claim='A province-wide variance is requested from the Provincial Building Administrator and must address a '
                      'province-wide issue; these are published as STANDATA variances.',
                citations=[PlanSource(title='NBC(AE) 2023 2nd printing, Div C 2.2.1.2.(1), PDF p.729'),
                           PlanSource(title='STANDATA 23-BCV-001, Window opening control devices (2024-04)',
                                      url='https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/'
                                          '01b622f0-f4a1-426d-b15f-ffc25e725949/download/'
                                          'ma-standata-variance-building-23-bcv-001-2024-04.pdf')]),
    RouteBullet(claim='A site variance is a written authorization a safety codes officer or an Administrator may issue '
                      'under the Safety Codes Act, s.38; an officer who issues one notifies an Administrator.',
                citations=[PlanSource(title='Safety Codes Act, RSA 2000 c S-1, s.38(1) and (3)', url=SCA)]),
    RouteBullet(claim='For building, the officer documents the alternative solution as Division C requires and sends each '
                      'variance to the Safety Codes Council within 10 days.',
                citations=[PlanSource(title='SCC Information Bulletin IB-2025-11-18, Mandatory Documentation of Variances',
                                      url=IB_2025)]),
)


def route_notice(role: str | None, scope: str | None) -> RouteNotice | None:
    """For a manufacturer, or any request for acceptance across the jurisdiction. Otherwise none."""
    if role != 'manufacturer' and scope != 'jurisdiction':
        return None
    return RouteNotice(summary=SUMMARY, bullets=list(BULLETS))
