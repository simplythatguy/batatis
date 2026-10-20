"""Whether a building-code variance is indicated, and when the request belongs to another regime.

`redirect` is the gold intake action for a request outside the building code's technical scope
(plumbing, electrical, gas, private sewage). No-departure is a separate field, `variance_needed`,
and is never called compliance.
"""
from __future__ import annotations

NOT_INDICATED = ('not_indicated',
                 'No departure from the acceptable solution has been identified; if the design follows '
                 'the cited acceptable solution, a variance may not be needed. Confirm with your '
                 'Safety Codes Officer.')
LIKELY = ('likely',
          'The description treats the design as doing something other than the cited acceptable solution. '
          'A variance is the application that asks the Safety Codes Officer to consider that alternative. '
          'This identification does not decide whether the alternative performs as well.')
UNKNOWN = ('unknown',
           'It is not yet known whether the design departs from an acceptable solution. '
           'The open questions stay open, and nothing here is assumed. Confirm with your Safety Codes Officer.')

# Phrases tied to the out-of-scope development cases. A house that merely contains a bathroom
# or a gas appliance does not match these.
REDIRECTS = (
    (('air admittance valve', 'plumbing variance', 'vent through the roof'),
     'Plumbing Code Regulation / National Plumbing Code (plumbing permit and plumbing safety codes officer)'),
    (('electrical panel', 'electrician', 'aluminum feeder', 'electrical feeder'),
     'Electrical Code Regulation / Canadian Electrical Code (electrical permit and electrical safety codes officer)'),
    (('gas fitter', 'natural gas supply', 'gas supply installation', 'gas installation only'),
     'Gas Code Regulation / gas permit authority and gas safety codes officer'),
    (('septic', 'disposal field', 'disposal-field', 'private sewage'),
     'Private Sewage Disposal Systems Regulation / private sewage permit authority and private sewage safety codes officer'),
)

DEPARTURE_CUES = (
    'instead', 'rather than', 'in place of', 'skip the', 'without the', 'no fire damper',
    'variance', 'alternative', 'does not meet', "doesn't meet", 'do not meet', "don't meet",
    'cannot meet', "can't meet", 'not provide', 'want to use',
)

_UNKNOWN_ANSWERS = {
    'not sure', 'not-sure', 'not_sure', 'unsure', 'unknown', "i don't know", 'i dont know',
    'idk', 'n/a', 'na', '?', 'tbd', "don't know", 'do not know', 'unsure yet',
}


def is_unknown_answer(text: str | None) -> bool:
    if text is None:
        return True
    norm = ' '.join(str(text).lower().replace('_', ' ').split())
    if not norm:
        return True
    return norm in _UNKNOWN_ANSWERS or norm.startswith('not sure') or norm.startswith('unknown')


def detect_redirect(prose: str) -> str | None:
    low = prose.lower()
    for phrases, dest in REDIRECTS:
        if any(p in low for p in phrases):
            return dest
    return None


def _facts(facts) -> list[dict]:
    out = []
    for fact in facts or []:
        out.append(fact.model_dump() if hasattr(fact, 'model_dump') else dict(fact))
    return out


def _departure_confirmed(facts: list[dict]) -> bool | None:
    """True, False, or None when a departure answer is present but unknown."""
    seen = None
    for fact in facts:
        field = str(fact.get('field') or '')
        if field not in {'departure', 'variance.departure'} and not field.startswith('candidate.'):
            continue
        if fact.get('status') in ('open', 'unknown') or is_unknown_answer(fact.get('value') if isinstance(fact.get('value'), str) else None):
            if fact.get('status') in ('open', 'unknown'):
                return None
        value = str(fact.get('value') or '').strip().lower()
        if value in {'yes', 'departs', 'departure'}:
            seen = True
        elif value in {'no', 'follows', 'acceptable'}:
            seen = False if seen is None else seen
    return seen


def assess_variance(prose: str, facts=None) -> tuple[str, str]:
    """`variance_needed` and a plain explanation. Never uses the word compliance."""
    prose = prose or ''
    if detect_redirect(prose):
        dest = detect_redirect(prose)
        return 'unknown', (f'This request reads as {dest}. It is outside the building-code variance '
                           f'this tool prepares. Confirm the responsible Safety Codes Officer.')
    flag = _departure_confirmed(_facts(facts))
    if flag is True:
        return LIKELY
    if flag is None:
        return UNKNOWN
    if any(cue in prose.lower() for cue in DEPARTURE_CUES):
        return LIKELY
    if flag is False:
        return NOT_INDICATED
    return NOT_INDICATED
