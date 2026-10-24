"""Division C 2.3.1.1 file completeness, "demonstrate, don't assert" prompts and the peer-review signal.

All administrative: a check finds whether an item is present in the documentation,
never whether it is adequate. Missing items are named findings worded so the
information request can ask the applicant. The peer-review signal is routed to
the officer and is never a decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models_review import Finding, Pointer

Corpus = list[tuple[str, int | None, str]]     # (file, 1-based page or None, text)


@dataclass(frozen=True)
class Item:
    key: str
    label: str
    provision: str            # Division C provision the item comes from
    pattern: re.Pattern
    message: str


# Present means the documentation names the item (heading or phrase). Adequacy is not assessed.
FILE_ITEMS = (
    Item('div_c.code_analysis', 'code analysis with the attributed objectives and functions', '2.3.1.1.(3)',
         re.compile(r'\b(?:code analysis|objectives? and function(?:al statement)?s?|O[SHPAE]\d(?:\.\d+)*)\b', re.I),
         'No code analysis identifying the attributed objectives and functional statements was found.'),
    Item('div_c.testing_procedures', 'testing procedures', '2.3.1.1.(3)',
         re.compile(r'\b(?:testing procedures?|test procedures?|test methods?|tested (?:to|in accordance with)|'
                    r'testing (?:to|in accordance with)|engineering stud(?:y|ies))\b', re.I),
         'No testing procedures, test methods or engineering studies supporting the code analysis were named.'),
    Item('div_c.qualifications', 'qualifications of the people responsible', '2.3.1.1.(4)',
         re.compile(r'\b(?:qualifications?|experience and background|P\.\s?Eng\.?|registered professional|'
                    r'professional engineer|architect)\b', re.I),
         'No information about the qualifications, experience and background of the people responsible was found.'),
    Item('div_c.maintenance', 'maintenance, operation and commissioning needs', '2.3.1.1.(2)(b)',
         re.compile(r'\b(?:maintenance|maintain(?:ed)?|commissioning|operational requirements?|inspection interval)\b',
                    re.I),
         'No information about special maintenance, operation or commissioning requirements was found. If there '
         'are none, the documentation can say so.'),
)
COORDINATOR = re.compile(r'\b(?:co-?ordinat(?:or|e|es|ing|ion))\b', re.I)

# "Demonstrate, don't assert": the documentation should say what it assumes when things go wrong.
DEMONSTRATE = (
    Item('demonstrate.failure_conditions', 'performance under failure conditions', '2.3.1.1.(3)',
         re.compile(r'\b(?:fail(?:s|ure|ed|ing)?|malfunction|impair(?:ed|ment)?|out of service|loss of)\b', re.I),
         'The documentation does not mention how the alternative performs if a component fails or is impaired.'),
    Item('demonstrate.lapsed_maintenance', 'what happens if maintenance lapses', '2.3.1.1.(2)(b)',
         re.compile(r'\b(?:laps(?:e|es|ed)|not maintained|neglect(?:ed)?|deferred maintenance|without maintenance|'
                    r'missed inspections?)\b', re.I),
         'The documentation does not mention what is assumed if maintenance or inspection lapses.'),
    Item('demonstrate.emergency_response', 'emergency-services response assumptions', '2.3.1.1.(3)',
         re.compile(r'\b(?:fire (?:department|service|fighters?|response)|emergency (?:services?|responders?|response)|'
                    r'response time|responders?)\b', re.I),
         'The documentation does not state what it assumes about emergency-services response (for example an '
         'assumed fire-service response time).'),
)
PEER_REVIEW = 'Peer review may be warranted'


def _find(corpus: Corpus, pattern) -> Pointer | None:
    for file, page, text in corpus:
        match = pattern.search(text or '')
        if match:
            line = text[text.rfind('\n', 0, match.start()) + 1:].split('\n', 1)[0].strip()[:300]
            return Pointer(file=file, page=page, quote=line or match.group(0))
    return None


def _citation(codes, provision: str) -> list[str]:
    if codes is None:
        return []
    try:
        found = codes.citation(provision, 'C')
    except Exception:  # noqa: BLE001
        return []
    return [found] if found else []


def _missing(item: Item, where: Pointer, codes, *, demonstrate: bool, uncertain: bool = False) -> Finding:
    message = item.message + (' Ask the applicant to state it; the review does not judge adequacy.'
                              if demonstrate else ' Ask the applicant to include it.')
    if uncertain:
        message = (f'The {item.label} could not be established because part of the package could not be read. '
                   'Check the indicated pages.')
    return Finding(key=f'{item.key}:not_mentioned' if demonstrate else f'{item.key}:presence',
                   section='process', field=item.key, label=item.label,
                   status='not_found' if uncertain else ('unclear' if demonstrate else 'missing'), problem='not_mentioned' if demonstrate else 'absent',
                   message=message, severity='warning' if demonstrate else 'blocking',
                   pointers=[where], citations=_citation(codes, item.provision))


def file_findings(corpus: Corpus, where: Pointer, codes, *, responsible: list[str], skip: set[str] = frozenset(),
                  on_alternative_path: bool = True, uncertain: bool = False) -> list[Finding]:
    """Div C 2.3.1.1 file items, the single co-ordinator, and the "demonstrate" prompts.

    `uncertain`: part of the package could not be read, so an absent item is "not found" (ask the officer)."""
    if not on_alternative_path:
        return []
    out = []
    for item in FILE_ITEMS:
        if item.key not in skip and _find(corpus, item.pattern) is None:
            out.append(_missing(item, where, codes, demonstrate=False, uncertain=uncertain))
    people = sorted({re.sub(r'\s+', ' ', name).strip().casefold() for name in responsible if name and name.strip()})
    if len(people) > 1 and _find(corpus, COORDINATOR) is None:
        out.append(Finding(
            key='div_c.coordinator:presence', section='process', field='div_c.coordinator',
            label='single co-ordinator for the design', status='not_found' if uncertain else 'missing', problem='absent',
            message=('The single co-ordinator could not be established because part of the package could not be read. '
                     'Check the indicated pages.' if uncertain else
                     f'{len(people)} different people or firms take responsibility for parts of the design, and no '
                     'single person is identified to co-ordinate the design, code analysis and documentation. '
                     'Ask the applicant to name one.'),
            severity='blocking', pointers=[where], citations=_citation(codes, '2.3.1.1.(6)')))
    if any(text.strip() for _f, _p, text in corpus):
        for item in DEMONSTRATE:
            if _find(corpus, item.pattern) is None:
                out.append(_missing(item, where, codes, demonstrate=True, uncertain=uncertain))
    return out


def peer_review_finding(*, professional_required: bool, provisions: list[str], rungs: list[str],
                        novel_product: bool, where: Pointer) -> Finding | None:
    """Non-decisional signal for the officer. Never asked of the applicant and never counted as a gap."""
    signals = []
    if professional_required:
        signals.append('a registered professional is stated to be required')
    part3 = sorted({pid for pid in provisions if re.match(r'^3\.\d', pid)})
    if part3:
        signals.append('a Part 3 provision is cited (' + ', '.join(part3) + ')')
    if novel_product and 'CCMC evaluation' not in rungs:
        signals.append('a product is relied on with no CCMC evaluation among the documents')
    if not signals:
        return None
    return Finding(key='peer_review:signal', section='D', field='peer_review', label='peer review',
                   status='unclear', problem='peer_review_may_be_warranted',
                   message=f'{PEER_REVIEW}: ' + '; '.join(signals) + '. This is the officer\'s call; it is not a '
                   'finding about the design.', routed_to='officer', pointers=[where])


NOVEL = re.compile(r'\b(?:new product|novel|proprietary|innovative|patented|manufacturer\'?s? (?:system|product)|'
                   r'product literature|brochure)\b', re.I)
