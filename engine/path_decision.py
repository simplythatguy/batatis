"""Which package the applicant is on.

A firm coded check decides: follows is the acceptable path, departs is the alternative path,
and not applicable stops with no package. A labeled assumption is not a firm check. When the
check is not firm, a recorded pathway wins, then the wording fork. An unknown fork does not
open the alternative package. Identify decisions are not an answer to the fork.

Objectives, functional statements, and intent are never asked here. A Division B sentence is
named only when the firm check returned it. Section C for that id is a database lookup.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .intake.fork import assess
from .intake.plan import description, overridden
from .intake.scope import classify
from .models import Case, Fact
from .rules.case import case_rules
from .rules.evaluator import load_rules
from .rules.models import RuleResult

PathName = Literal['acceptable', 'alternative', 'not_applicable', 'unresolved', 'redirect']
PathSource = Literal['redirect', 'coded_check', 'recorded', 'wording', 'unresolved']

BUILDING_WIDE = frozenset({
    'occupancy', 'storeys', 'building_area_m2', 'dwelling_unit_above_another', 'sprinklered',
    'fire_response_over_10_min', 'adjacent_rooms_sprinklered', 'industrial_hazard',
})
KEYWORDS = (
    ('glazed-openings-houses', ('glazed', 'glazing', 'window')),
    ('unprotected-openings', ('unprotected opening', 'unprotected')),
    ('soffits-houses', ('soffit', 'overhang')),
    ('firewall-suite-rowhouses', ('firewall', 'secondary suite', 'row house', 'townhouse')),
    ('fire-dampers', ('fire damper', 'damper', 'duct')),
)
_STATE = {'follows': 'acceptable', 'departs': 'alternative', 'not_applicable': 'not_applicable'}


@dataclass(frozen=True)
class PathDecision:
    path: PathName
    rule_id: str | None = None
    article: str | None = None
    missing: tuple[str, ...] = ()
    firm: bool = False
    source: PathSource = 'unresolved'
    asks_rule_inputs: bool = False


def decide_path(case: Case) -> PathDecision:
    text = _design_text(case)
    if not overridden(case) and classify(text).status == 'redirect':
        return PathDecision(path='redirect', source='redirect')
    rules = load_rules()
    by_id = {result.rule_id: result for result in case_rules(case).results}
    named = _select_rule(text, rules)
    if named:
        result = by_id[named]
        if _firm(result):
            return _from_check(result)
        missing = _needs(result, next(rule for rule in rules if rule['id'] == named))
        return _fallback(case, text, rule_id=named, missing=missing)
    playing = [by_id[rule['id']] for rule in rules if _in_play(by_id[rule['id']])]
    firm = [result for result in playing if _firm(result)]
    departed = next((result for result in firm if result.state == 'departs'), None)
    if departed is not None:
        return _from_check(departed)
    if playing and len(firm) == len(playing) and {result.state for result in firm} <= {'follows'}:
        return _from_check(firm[0])
    if playing and len(firm) == len(playing) and {result.state for result in firm} == {'not_applicable'}:
        return _from_check(firm[0])
    missing: list[str] = []
    for result in playing:
        if _firm(result):
            continue
        missing.extend(_needs(result, next(rule for rule in rules if rule['id'] == result.rule_id)))
    return _fallback(case, text, missing=tuple(dict.fromkeys(missing)))


def _from_check(result: RuleResult) -> PathDecision:
    return PathDecision(
        path=_STATE[result.state], rule_id=result.rule_id, article=result.provision.id,
        firm=True, source='coded_check')


def _fallback(case: Case, text: str, *, rule_id: str | None = None, missing: tuple[str, ...] = ()) -> PathDecision:
    recorded = _recorded(case)
    if recorded:
        return PathDecision(path=recorded, rule_id=rule_id, missing=missing, source='recorded',
                            asks_rule_inputs=bool(missing))
    wording = _wording(text)
    if wording:
        return PathDecision(path=wording, rule_id=rule_id, missing=missing, source='wording',
                            asks_rule_inputs=bool(missing))
    return PathDecision(path='unresolved', rule_id=rule_id, missing=missing, source='unresolved',
                        asks_rule_inputs=bool(missing))


def _firm(result: RuleResult) -> bool:
    return result.state in _STATE and not result.assumptions


def _needs(result: RuleResult, rule: dict) -> tuple[str, ...]:
    missing = [item.field for item in result.missing]
    if result.assumptions:
        known = {item.field for item in result.inputs if item.value is not None}
        missing.extend(field for field in rule['inputs'] if field not in known and field not in missing)
    return tuple(missing)


def _in_play(result: RuleResult) -> bool:
    return any(item.field not in BUILDING_WIDE and item.value is not None for item in result.inputs)


def _keyword_hit(text: str, token: str) -> bool:
    if ' ' in token:
        return token in text
    return re.search(rf'\b{re.escape(token)}s?\b', text) is not None


def _select_rule(text: str, rules: list[dict]) -> str | None:
    by_title = [rule['id'] for rule in rules if rule['title'] in text]
    if len(by_title) == 1:
        return by_title[0]
    low = text.lower()
    scores = [(sum(_keyword_hit(low, token) for token in tokens), rule_id) for rule_id, tokens in KEYWORDS]
    scores = [(score, rule_id) for score, rule_id in scores if score]
    if not scores:
        return None
    best = max(score for score, _ in scores)
    tied = [rule_id for score, rule_id in scores if score == best]
    return tied[0] if len(tied) == 1 else None


def _design_text(case: Case) -> str:
    text = description(case)
    alternative = _latest(case, 'alternative_description', 'alternative')
    read = alternative.value if alternative is not None and isinstance(alternative.value, str) else ''
    if read and read not in text:
        text = f'{text}\n{read}'.strip()
    return text


def _latest(case: Case, *fields: str) -> Fact | None:
    return next((fact for fact in reversed(case.facts) if fact.field in fields), None)


def _confirmed(case: Case, *fields: str):
    fact = _latest(case, *fields)
    if fact and fact.status == 'confirmed' and fact.kind != 'proposed' and fact.value is not None:
        return fact.value
    return None


def _recorded(case: Case) -> Literal['acceptable', 'alternative'] | None:
    value = _confirmed(case, 'pathway', 'path')
    if value in ('acceptable', 'acceptable_solution'):
        return 'acceptable'
    if value in ('alternative', 'variance'):
        return 'alternative'
    route = _confirmed(case, 'journey.route')
    if route == 'standard':
        return 'acceptable'
    if route in ('variance', 'different'):
        return 'alternative'
    return None


def _wording(text: str) -> Literal['acceptable', 'alternative'] | None:
    needed = assess(text).variance_needed
    if needed == 'likely':
        return 'alternative'
    if needed == 'not_indicated':
        return 'acceptable'
    return None
