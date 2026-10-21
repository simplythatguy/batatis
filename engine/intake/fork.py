"""The NBC(AE) fork, read early: acceptable-solution path or alternative-solution path.

Ported from PR #12 (`engine/identify/departure.py`: `variance_needed` is `likely`, `not_indicated` or
`unknown`, and never says "complies"). Wording follows the organizers' SCC presentation: a variance is a
legal authorization (Safety Codes Act, s.38) that a safety codes officer or an Administrator issues; an
alternative solution is the proponent's technical evidence (NBC(AE) Division C, 2.3.1) that the design
achieves at least the level of performance required by Division B in the attributed objectives and
functions. A request for variance plus an alternative solution is what the officer decides on.
"""
from __future__ import annotations

import re

from ..models_intake import Fork, Half
from .text import is_question, sentences

HALVES = [
    Half(id='variance_request', label='Request for variance', basis='Safety Codes Act, s.38',
         who='Issued by a safety codes officer or an Administrator, who may set conditions',
         what='The legal authorization to build in a way the code does not prescribe'),
    Half(id='alternative_solution', label='Alternative solution (Div C 2.3.1)', basis='NBC(AE) Division C, 2.3.1',
         who='Prepared by the proponent, usually a design professional',
         what=('The technical evidence that the design achieves at least the level of performance required by '
               'Division B in the attributed objectives and functions')),
]

_DEPARTS = re.compile(
    r"(?i)\binstead\s+of\b|\binstead\b|\brather\s+than\b|\bin\s+place\s+of\b|\bomit(?:s|ted|ting)?\b|\bleav(?:e|ing)\s+out\b"
    r"|\bskip(?:ping)?\b|\bdrop\s+the\b|\bwithout\s+(?:the|a|any|adding|designing|checking|demonstrating|a\s+separate)\b"
    r"|\bnot\s+(?:meet|meeting|offering|providing|provide|install|use|check)\b|\b(?:doesn'?t|does\s+not|don'?t|do\s+not)\s+meet\b"
    r"|\b(?:less|fewer|smaller|thinner|shorter|lower|closer|narrower)\s+than\s+(?:the\s+)?(?:code|required|allowed|permitted|prescribed|table)"
    r"|\b(?:more|larger|longer|higher|taller|further|wider)\s+than\s+(?:the\s+)?(?:code|allowed|permitted|maximum|limit)"
    r"|\bexceed(?:s|ing)?\s+the\b|\btoo\s+close\b|\breduc(?:e|ed|ing)\b|\breplace(?:s|d)?\s+(?:the\s+)?(?:required|both)\b"
    r"|\bno\s+(?:fire\s+dampers?|sheathing|housewrap|separate|installed|rated|other)\b|\bonly\s+one\s+(?:exit|stair)\b"
    r"|\bsingle\s+(?:exit|stair(?:case)?)\b|\bdon'?t\s+fit\s+the\s+prescriptive\b|\bdo\s+not\s+want\s+to\s+add\b"
    r"|\bflagged\b|\brejected\b|\bneeds?\s+a\s+variance\b|\b(?:get|apply\s+for)\s+(?:a\s+)?variance\s+(?:for|so)\b"
    r"|\b(?:smaller|lighter|narrower|lower|shorter|thinner|less|fewer|higher|larger|wider)\s+than\s+(?:normal|usual|what|the\s+(?:minimum|maximum|required|usual))"
    r"|\b(?:below|short\s+of|under)\s+the\s+(?:\w+\s+)?(?:minimum|required)\b|\babove\s+what\b|\bcall\s+for\s+more\b"
    r"|\bno\s+(?:encapsulation|standard\s+listing|listing|connection|conformity|intervening|subsurface|Part\s+\d)\b"
    r"|\breplacing\s+the\s+required\b|\bpropos(?:e|es|ed|ing)\b|\bwants?\s+(?:the|an?|one|ordinary)\b"
    r"|\b\d+\s*%\s+(?:less|lower|fewer|smaller)\b|\b(?:just|only)\s+one\s+(?:\w+\s+)?(?:exit|stair)\b"
    r"|\bonly\b(?=.{0,40}\b(?:apart|procedure|checks?|data|test|alone|route|values?)\b)|\bpartly\b|\blet\s+the\b")
_FOLLOWS = re.compile(
    r"(?i)\b(?:meets?|meeting|follows?|following|according\s+to|per|as\s+(?:set\s+out\s+)?in|built\s+to|matches?|within)\s+"
    r"(?:the\s+|all\s+the\s+|every\s+)?(?:code|building\s+code|tables?|span\s+tables?|prescriptive|acceptable\s+solutions?|Part\s+9)"
    r"|\bstandard\s+(?:detail|assembly|construction|design)\b|\bas\s+the\s+code\s+(?:requires|says)\b|\bcode[-\s]conforming\b"
    r"|\bexactly\s+as\b|\bno\s+(?:changes?|deviations?|departures?)\b|\bnothing\s+(?:unusual|different)\b"
    r"|\bcode[-\s]minimum\b|\bmeets?\s+the\s+minimum\b|\bas\s+the\s+code\s+(?:describes|requires|says)\b"
    r"|\bprescriptive\s+(?:path|route|values?)\b|\b(?:straight\s+)?from\s+the\s+code\b|\blisted\s+in\s+the\b.{0,40}\bcode\b"
    r"|\bstandard\s+(?:loads?|stairs?|height)\b|\bstandard\s+[\w\s-]{0,20}\bdetail\b")


def _cues(pattern: re.Pattern, text: str) -> list[str]:
    out = []
    for a, b in sentences(text):
        sentence = text[a:b]
        if is_question(sentence):
            continue
        out += [m.group(0) for m in pattern.finditer(sentence)]
    return out


def assess(text: str, *, decisions: dict[str, str] | None = None) -> Fork:
    """`decisions`: identify's per-article answers ('yes', 'no', 'not_sure'), when identify has run."""
    departs, follows = _cues(_DEPARTS, text or ''), _cues(_FOLLOWS, text or '')
    decided = list((decisions or {}).values())
    if departs and not follows or (decided and 'yes' in decided):
        cue = departs[0] if departs else 'the requirement you marked as one your design departs from'
        return Fork(variance_needed='likely', cues=departs, halves=HALVES, explanation=(
            f'Your description says the design does something other than an acceptable solution ("{cue}"). '
            'That is the alternative-solution path, and it needs two things: the alternative solution, which is '
            'your technical evidence under NBC(AE) Division C, 2.3.1 that the design achieves at least the level '
            'of performance required by Division B in the attributed objectives and functions; and the request '
            'for a variance under the Safety Codes Act, s.38, which only a safety codes officer or an Administrator '
            'can issue. Batatis helps you prepare both; the officer decides.'))
    if (follows and not departs) or (decided and all(d == 'no' for d in decided)):
        return Fork(variance_needed='not_indicated', cues=follows, halves=HALVES, explanation=(
            'Nothing you have told us departs from an acceptable solution. If the design follows the acceptable '
            'solutions, you may not need a variance: the usual permit documents apply. If any part does something '
            'different, tell us what it is, and the alternative-solution path applies. Your safety codes officer decides.'))
    return Fork(variance_needed='unknown', cues=departs + follows, halves=HALVES, explanation=(
        'It is not clear yet whether the design departs from an acceptable solution. The questions below help '
        'decide; nothing is assumed.'))
