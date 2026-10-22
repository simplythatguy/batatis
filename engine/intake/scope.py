"""Scope check: is this a building-code (NBC(AE)) question, or one for another safety-codes regime?

Ported idea: PR #12 `departure.detect_redirect` (gas, private sewage, plumbing, electrical phrases), now a
scored classifier that also covers the fire code and the energy code, and that weighs building-code
cues against the other regime's cues so a house with a bathroom or a gas fireplace stays in scope.

Redirect copy follows the organizers' SCC presentation ("Alternative Solutions Under Alberta's
Objective-Based Codes"): electrical, gas and private sewage have no equivalent mandatory Division C
alternative-solution framework, and best practice is to follow the National Model Codes approach in
principle; fire, plumbing and energy are National Model Codes with the same pathway, which Batatis does
not cover yet (roadmap, not built). Nothing here says a design complies, is safe, or is approved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models_intake import Regime, ScopeCheck

REDIRECT_AT = 2          # regime score needed to redirect
MARGIN = 2               # and by how much it must beat the building-code score


def _c(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


# (weight, pattern). 3: names the code, its permit or its officer. 2: a technical term of that regime.
# 1: a word that also turns up in building questions.
CUES: dict[str, list[tuple[int, re.Pattern]]] = {
    'plumbing': [
        (3, _c(r'\bplumbing\s+(?:code|permit|inspector|officer|variance)\b|\bNational\s+Plumbing\s+Code\b|\bNPC\b')),
        (2, _c(r'\bair\s+admittance\s+valves?\b|\bbackwater\s+valves?\b|\btrap\s+arms?\b|\bgrease\s+(?:interceptor|trap)s?\b'
               r'|\bgr[ae]ywater\b|\bbuilding\s+drain\b|\bsanitary\s+drain(?:age)?\b|\bvent\s+(?:stack|through\s+the\s+roof)\b'
               r'|\bexpansion\s+tank\b|\bdomestic\s+(?:hot\s+)?water\s+(?:supply|piping)\b|\bfixture\s+units?\b|\bfloor\s+drains?\b'
               r'|\brelief\s+valve\b|\bbackflow\s+(?:preventers?|prevention)\b|\bsewer\s+(?:line|connection)\b|\bpipe\s+slope\b'
               r'|\bvent\b(?=.{0,30}\b(?:undersized|missing)\b)|\bdrain\s+gurgles\b')),
        (1, _c(r'\bplumb(?:er|ing)\b|\bdrainage\b|\bsump\b|\bwater\s+heater\b|\btraps?\b')),
    ],
    'electrical': [
        (3, _c(r'\belectrical\s+(?:code|permit|inspector|officer)\b|\bCanadian\s+Electrical\s+Code\b|\bCEC\b')),
        (2, _c(r'\b(?:electrical\s+)?(?:service\s+)?panel\b(?=.{0,60}\b(?:electric|breaker|feeder|circuit|garage|closet|basement)\b)'
               r'|\bfeeders?\b|\bbreakers?\b|\bAFCI\b|\bGFCI\b|\breceptacles?\b|\bNMD\s?90\b|\bconduit\b|\bservice\s+mast\b'
               r'|\bwiring\b|\brapid\s+shutdown\b|\bsolar\s+PV\b|\bcircuits?\b|\baluminum\s+(?:cable|wire|wiring)\b'
               r'|\b\d+\s*amps?\b|\bmeter\s+base\b|\bdisconnect\b|\bconductors?\b|\binverters?\b|\boutlets?\b(?=.{0,60}\bGFCI\b)'
               r'|\bclearance\s+(?:is\s+required\s+)?in\s+front\s+of\s+the\s+(?:electrical\s+)?panel\b')),
        (1, _c(r'\belectrician\b|\belectrical\b')),
    ],
    'gas': [
        (3, _c(r'\bgas\s+(?:code|permit|fitter|inspector|officer|installation|supply)\b|\bB149\b')),
        (2, _c(r'\bnatural\s+gas\b|\bgas\s+(?:piping|pipe|line|meter|regulator)\b|\bregulator\s+arrangement\b|\bpipe[-\s]sizing\b')),
        (1, _c(r'\bgas\b(?!\s+station)|\bpropane\b(?!\s+cylinders?)')),
    ],
    'private_sewage': [
        (3, _c(r'\bprivate\s+sewage\b|\bsewage\s+(?:system|disposal)\b|\bPrivate\s+Sewage\s+Systems?\s+Standard\b')),
        (2, _c(r'\bseptic\s+(?:tank|field|system)\b|\bdisposal[-\s]field\b|\btreatment\s+field\b|\bholding\s+tank\b|\blagoon\b')),
        (1, _c(r'\bseptic\b')),
    ],
    'fire': [
        (3, _c(r'\bfire\s+code\b|\bNational\s+Fire\s+Code\b|\bNFC\b|\bfire\s+(?:inspector|marshal|prevention\s+officer)\b'
               r'|\bfire\s+(?:department|services?)\s+inspection\b|\bfire\s+safety\s+plan\b')),
        (2, _c(r'\bflammable\b|\bcombustible\s+(?:liquids?|storage)\b|\bhot\s+work\b|\bfire\s+watch\b'
               r'|\bposted\s+occupant\s+load\b|\boccupant\s+load\s+sign\b|\bcraft\s+fair\b|\bfestival\b'
               r'|\b(?:annual\s+|yearly\s+)?(?:testing|inspection|maintenance)\s+of\s+(?:our\s+|the\s+)?existing\b'
               r'|\b(?:yearly|annual)\s+(?:inspection|testing)\b|\bfire\s+alarm\s+panel\b|\boverdue\b|\bextinguishers?\b'
               r'|\bpropane\s+cylinders?\b|\bstore\s+\d+\s*(?:litres?|L)\b')),
        (1, _c(r'\bexisting\s+(?:office|hotel|warehouse|building|arena|store|apartment)\b|\bfire\s+(?:department|services?)\b')),
    ],
    'energy': [
        (3, _c(r'\bNECB\b|\bNational\s+Energy\s+Code\b|\benergy\s+code\b|\benergy\s+efficiency\s+rules\s+for\s+large\s+buildings\b')),
        (2, _c(r'\benergy\s+(?:model(?:ling)?|compliance|target)\b|\breference\s+building\b|\blighting\s+power\s+density\b'
               r'|\bU-value\b|\bfenestration(?:-to-wall)?\s+ratio\b|\bperformance\s+path\b|\bheat\s+recovery\b'
               r'|\bminimum\s+efficiency\b|\beconomi[sz]ers?\b|\brooftop\s+units?\b')),
        (1, _c(r'\benergy\b')),
    ],
}

# Building-code cues. 4: the building code named (or its energy section for houses). 1: a building element.
BUILDING: list[tuple[int, re.Pattern]] = [
    (4, _c(r'\bbuilding\s+code\b|\bNBC\b|\bSection\s+9\.36\b|\bPart\s+[349]\b|\bDivision\s+B\b')),
    (1, _c(r'\bfire\s+separations?\b|\bfirestop(?:ping)?\b|\brated\s+(?:wall|floor|assembly)\b|\begress\b|\bexits?\b'
           r'|\bexit\s+(?:stair|path)s?\b|\bstairs?\b|\bguards?\b|\bfootings?\b|\bfoundations?\b|\bjoists?\b|\bstuds?\b'
           r'|\bproperty\s+line\b|\bunprotected\s+openings?\b|\blimiting\s+distance\b|\bcladding\b|\bsheathing\b'
           r'|\bwindows?\b|\bsprinklers?\b|\battic\b|\bexterior\s+wall\b|\bfire\s+alarm\s+system\b|\bemergency\s+lighting\b'
           r'|\baccess\s+route\b|\bhydrants?\b|\bwater\s+closets?\b|\bexhaust\s+fans?\b|\bnotch\b|\binsulation\b(?!.{0,40}\b(?:NECB|energy\s+code)\b)'
           r'|\bcloset\s+under\s+the\s+stairs\b|\bsuites?\b|\bslab\b|\bradon\b|\bdrainage\s+layer\b')),
]
# "The question is only about X" / "not the building": whoever X names gets +3.
_FOCUS = _c(r'\b(?:question|request|this)\s+is\s+(?:only\s+)?(?:about\s+)?(?:the\s+)?(?P<x>[\w\s-]{3,60}?)(?:[;,.]|\bnot\b|$)')
_HOUSE = _c(r'\b(?:house|home|dwelling|bungalow|duplex|townhouse)s?\b')
_NOT_BUILDING = _c(r'\bno\s+building\s+(?:wall|element)|\bnot\s+(?:the\s+)?building\b|\bonly\s+(?:about\s+)?the\s+(?:plumbing|gas|electrical|sewage)')


REGIMES: dict[str, Regime] = {r.id: r for r in (
    Regime(id='plumbing', name='plumbing', framework='national_model_code', coverage='roadmap',
           code='Plumbing Code Regulation / National Plumbing Code (plumbing permit and plumbing safety codes officer)',
           route='the plumbing safety codes officer at the office that issues plumbing permits for the site'),
    Regime(id='fire', name='fire code', framework='national_model_code', coverage='roadmap',
           code='Fire Code Regulation / National Fire Code – Alberta Edition (fire safety codes officer or fire department)',
           route='the fire safety codes officer or the fire department that enforces the fire code for the site'),
    Regime(id='energy', name='energy code', framework='national_model_code', coverage='roadmap',
           code='Energy Code Regulation / National Energy Code of Canada for Buildings (building permit)',
           route='the building safety codes officer who reviews the energy-code requirements for the building permit'),
    Regime(id='electrical', name='electrical', framework='no_division_c_framework', coverage='not_covered',
           code='Electrical Code Regulation / Canadian Electrical Code (electrical permit and electrical safety codes officer)',
           route='the electrical safety codes officer at the office that issues electrical permits for the site'),
    Regime(id='gas', name='gas', framework='no_division_c_framework', coverage='not_covered',
           code='Gas Code Regulation / gas permit authority and gas safety codes officer',
           route='the gas safety codes officer at the office that issues gas permits for the site'),
    Regime(id='private_sewage', name='private sewage', framework='no_division_c_framework', coverage='not_covered',
           code='Private Sewage Disposal Systems Regulation / private sewage permit authority and private sewage safety codes officer',
           route='the private sewage safety codes officer at the office that issues private sewage permits for the site'),
)}


def redirect_message(regime: Regime) -> str:
    if regime.framework == 'no_division_c_framework':
        return (f'This reads as a {regime.name} question ({regime.code}). That regime has no equivalent mandatory '
                'Division C alternative-solution framework like the one in the building code, so Batatis does not '
                'prepare it. Best practice is to follow the National Model Codes approach in principle: name the '
                'requirement, what it is meant to achieve, and the evidence that the alternative performs at least as '
                f'well. Take the request to {regime.route}.')
    return (f'This reads as a {regime.name} question ({regime.code}). It is a National Model Code with the same '
            'alternative-solution pathway as the building code, but Batatis prepares building-code (NBC(AE)) '
            f'applications only: {regime.name} coverage is on the roadmap, not built. Take the request to {regime.route}.')


@dataclass(frozen=True)
class _Match:
    weight: int
    start: int
    end: int


def _score(text: str, cues: list[tuple[int, re.Pattern]]) -> list[_Match]:
    found: list[_Match] = []
    for weight, pattern in cues:
        for m in pattern.finditer(text):
            if any(m.start() < f.end and f.start < m.end() for f in found):
                continue
            found.append(_Match(weight, m.start(), m.end()))
    return found


def classify(text: str) -> ScopeCheck:
    """Deterministic. A redirect needs a clear lead for one regime over the building-code cues."""
    text = text or ''
    matches = {regime: _score(text, cues) for regime, cues in CUES.items()}
    scores = {regime: sum(m.weight for m in found) for regime, found in matches.items()}
    building = sum(m.weight for m in _score(text, BUILDING))
    for focus in _FOCUS.finditer(text):
        phrase = focus.group('x')
        for regime, cues in CUES.items():
            if any(p.search(phrase) for _, p in cues):
                scores[regime] += 3
        if any(p.search(phrase) for _, p in BUILDING):
            building += 3
    if _NOT_BUILDING.search(text):
        building = max(0, building - 3)
    if _HOUSE.search(text) and not CUES['energy'][0][1].search(text):
        scores['energy'] = 0                  # a house's energy efficiency is NBC(AE) Section 9.36: in scope
    scores['building'] = building
    best = max(CUES, key=lambda r: scores[r])
    runner_up = max(scores[r] for r in CUES if r != best)
    if scores[best] < REDIRECT_AT or scores[best] - building < MARGIN or scores[best] == runner_up:
        return ScopeCheck(status='in_scope', scores=scores)
    top = max(matches[best], key=lambda m: (m.weight, -m.start))
    regime = REGIMES[best]
    return ScopeCheck(status='redirect', regime=regime, message=redirect_message(regime), cue=text[top.start:top.end],
                      start=top.start, end=top.end, scores=scores)
