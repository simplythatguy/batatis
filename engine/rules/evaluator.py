"""Coded rules: the authoritative evaluator.

A rule is data (`engine/data/rules/<id>.json`): its provisions with citations from the code database, the
inputs it reads (shared vocabulary in `index.json`), derived values, and an ordered outcome table. The first
outcome whose `when` holds decides the state: `follows`, `departs` or `not_applicable`. A `when` that cannot be
decided because an input is missing gives `needs_info` with the questions for exactly those inputs (or, for an
outcome marked `if_unknown: "assume"`, records the assumption and moves on). Nothing is guessed.

Logic is three-valued (true, false, unknown). Before asking, an undecided `when` whose missing inputs are all
yes/no or a fixed list of choices is tried with every combination; if every combination agrees, the answer
does not matter and nothing is asked.

The TypeScript evaluator in `web/src/rules/evaluate.ts` implements the same semantics line for line. Both run
`evals_dev/rules/vectors.json`, and the full outputs must match `evals_dev/rules/outputs.json`.

Wording: a result says the design "follows" or "departs from" the acceptable solution. It never says the
design complies, is safe, approved or adequate.
"""
from __future__ import annotations

import itertools
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / 'data' / 'rules'
EPS = 1e-9
MAX_SPLIT = 64
STATES = ('follows', 'departs', 'needs_info', 'not_applicable')
_PLACEHOLDER = re.compile(r'\{([a-z0-9_]+)\}')


class RuleError(Exception):
    """A rule definition is malformed, or no outcome matched (a data bug, never a user answer)."""


@lru_cache(maxsize=1)
def load_index() -> dict:
    return json.loads((DATA / 'index.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=None)
def load_rule(rule_id: str) -> dict:
    if rule_id not in load_index()['rules']:
        raise KeyError(rule_id)
    return json.loads((DATA / f'{rule_id}.json').read_text(encoding='utf-8'))


def load_rules() -> list[dict]:
    return [load_rule(rule_id) for rule_id in load_index()['rules']]


# ---------------------------------------------------------------- values

def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def normalize(spec: dict, value: Any) -> Any:
    """The value if it is valid for the input's type, else None (treated as missing)."""
    kind = spec['type']
    if kind == 'bool':
        return value if isinstance(value, bool) else None
    if kind == 'enum':
        return value if isinstance(value, str) and value in [c['value'] for c in spec['choices']] else None
    if not _is_num(value):
        return None
    if kind == 'int' and float(value) != math.floor(value):
        return None
    if 'min' in spec and value < spec['min']:
        return None
    return value


def fmt(value: Any) -> str:
    """Numbers to at most 2 decimals, half up, trailing zeros dropped. Same digits as the TypeScript fmt."""
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if _is_num(value):
        negative = value < 0
        hundredths = math.floor(abs(value) * 100 + 0.5)
        whole, frac = divmod(hundredths, 100)
        text = str(whole) if frac == 0 else f'{whole}.{frac // 10}' if frac % 10 == 0 else f'{whole}.{frac:02d}'
        return f'-{text}' if negative and hundredths else text
    return str(value)


# ---------------------------------------------------------------- expressions

class _Env:
    def __init__(self, rule: dict, inputs: dict, specs: dict, tables: dict):
        self.rule, self.inputs, self.specs, self.tables = rule, inputs, specs, tables
        self.derived = {d['name']: d for d in rule['derived']}
        self.memo: dict[str, tuple[Any, frozenset]] = {}

    def with_inputs(self, overrides: dict) -> '_Env':
        return _Env(self.rule, {**self.inputs, **overrides}, self.specs, self.tables)


def _equal(a: Any, b: Any) -> bool:
    if _is_num(a) and _is_num(b):
        return abs(a - b) <= EPS
    return type(a) is type(b) and a == b


def _table(env: _Env, expr: dict, row: Any, col: Any) -> float:
    table = env.tables[expr['table']]
    picked = next((r for r in table['rows'] if r['max_area'] is not None and row <= r['max_area'] + EPS),
                  next(r for r in table['rows'] if r['max_area'] is None))
    values = [100 if v is None else v for v in picked['values']]
    cols = table['columns']
    index = 0
    for i, c in enumerate(cols):
        if i == 0 or col >= c - EPS:
            index = i
    lesser = values[index]
    if expr['mode'] == 'lesser' or col <= 1.2 + EPS or index == len(cols) - 1:
        return lesser
    if expr['mode'] != 'interpolate':
        raise RuleError(f"unknown table mode {expr['mode']}")
    c0, c1, v0, v1 = cols[index], cols[index + 1], values[index], values[index + 1]
    return v0 + (v1 - v0) * (col - c0) / (c1 - c0)


def ev(expr: Any, env: _Env) -> tuple[Any, frozenset]:
    """(value, missing inputs that made it unknown). value None means unknown."""
    none: frozenset = frozenset()
    if isinstance(expr, bool) or _is_num(expr) or isinstance(expr, str):
        return expr, none
    if not isinstance(expr, dict):
        raise RuleError(f'bad expression {expr!r}')
    if 'var' in expr:
        name = expr['var']
        if name in env.specs:
            value = env.inputs.get(name)
            return (value, none) if value is not None else (None, frozenset({name}))
        if name in env.derived:
            if name not in env.memo:
                env.memo[name] = ev(env.derived[name]['expr'], env)
            return env.memo[name]
        raise RuleError(f'unknown name {name}')
    op = expr['op']
    if op == 'table':
        (row, m1), (col, m2) = ev(expr['row'], env), ev(expr['col'], env)
        if row is None or col is None:
            return None, m1 | m2
        return _table(env, expr, row, col), none
    if op == 'in':
        value, missing = ev(expr['args'][0], env)
        return (None, missing) if value is None else (value in expr['args'][1], none)
    args = [ev(a, env) for a in expr['args']]
    unknown = frozenset().union(*(m for v, m in args if v is None))
    values = [v for v, _ in args]
    if op == 'and':
        if any(v is False for v in values):
            return False, none
        return (None, unknown) if any(v is None for v in values) else (True, none)
    if op == 'or':
        if any(v is True for v in values):
            return True, none
        return (None, unknown) if any(v is None for v in values) else (False, none)
    if op == 'if':
        (cond, mc), (a, ma), (b, mb) = args
        if cond is None:
            if a is not None and b is not None and _equal(a, b):
                return a, none
            return None, mc | ma | mb
        return (a, ma) if cond else (b, mb)
    if any(v is None for v in values):
        return None, unknown
    if op == 'not':
        return (not values[0]), none
    if op in ('lt', 'le', 'gt', 'ge'):
        a, b = values
        if not (_is_num(a) and _is_num(b)):
            raise RuleError(f'{op} needs numbers')
        return {'lt': a < b - EPS, 'le': a <= b + EPS, 'gt': a > b + EPS, 'ge': a >= b - EPS}[op], none
    if op == 'eq':
        return _equal(*values), none
    if op == 'ne':
        return (not _equal(*values)), none
    if op == 'add':
        return values[0] + values[1], none
    if op == 'sub':
        return values[0] - values[1], none
    if op == 'mul':
        return values[0] * values[1], none
    if op == 'div':
        return values[0] / values[1], none
    if op == 'min':
        return min(values), none
    if op == 'max':
        return max(values), none
    raise RuleError(f'unknown op {op}')


def _domain(spec: dict) -> list | None:
    if spec['type'] == 'bool':
        return [True, False]
    if spec['type'] == 'enum':
        return [c['value'] for c in spec['choices']]
    return None


def _decide(when: Any, env: _Env, order: list[str]) -> tuple[bool | None, list[str]]:
    """True/False when decided (by the inputs, or by every completion of the missing yes/no and choice
    inputs), else None and the missing inputs in the rule's input order."""
    value, missing = ev(when, env)
    if value is not None:
        return bool(value), []
    fields = [f for f in order if f in missing]
    finite = [f for f in fields if _domain(env.specs[f]) is not None]
    domains = [_domain(env.specs[f]) for f in finite]
    if not finite or math.prod(len(d) for d in domains) > MAX_SPLIT:
        return None, fields
    results, still = [], set()
    for combo in itertools.product(*domains):
        result, left = ev(when, env.with_inputs(dict(zip(finite, combo))))
        results.append(result)
        still |= left
    if all(r is None for r in results):
        # Every completion still waits on the same numbers: ask those first.
        return None, [f for f in order if f in still]
    if all(r is not None for r in results) and len(set(results)) == 1:
        return bool(results[0]), []
    return None, fields


def _render(template: str, env: _Env) -> str:
    def value(match: re.Match) -> str:
        name = match.group(1)
        found, missing = ev({'var': name}, env)
        if found is not None:
            return fmt(found)
        if name in env.specs:
            return 'not stated'
        # A derived value that depends on an unanswered yes/no or choice the outcome did not need:
        # show every value it can take, in a fixed order ("0.3 or 0.15").
        finite = [f for f in env.rule['inputs'] if f in missing and _domain(env.specs[f]) is not None]
        if len(finite) != len(missing):
            return 'not determined'
        shown: list[str] = []
        for combo in itertools.product(*(_domain(env.specs[f]) for f in finite)):
            value, _ = ev({'var': name}, env.with_inputs(dict(zip(finite, combo))))
            if value is None:
                return 'not determined'
            if fmt(value) not in shown:
                shown.append(fmt(value))
        return ' or '.join(shown)
    return _PLACEHOLDER.sub(value, template)


def _tables(rule: dict) -> dict:
    return {t['id'] + (f"|{t['group']}" if t.get('group') else ''): t for t in rule['tables']}


def evaluate(rule: dict, given: dict, index: dict | None = None) -> dict:
    """Evaluate one rule over raw input values (field -> value). Pure: no case, no database."""
    index = index or load_index()
    specs = {f: index['inputs'][f] for f in rule['inputs']}
    inputs, ignored = {}, []
    for field, spec in specs.items():
        if given.get(field) is None:
            continue
        value = normalize(spec, given[field])
        if value is None:
            ignored.append(field)
        else:
            inputs[field] = value
    env = _Env(rule, inputs, specs, _tables(rule))
    provisions = {p['id']: p for p in rule['provisions']}
    assumptions: list[str] = []
    chosen, missing = None, []
    for outcome in rule['outcomes']:
        decided, missing = _decide(outcome['when'], env, rule['inputs'])
        if decided is None and outcome.get('if_unknown') == 'assume':
            assumptions.append(outcome['assumption'])
            continue
        if decided is None or decided:
            chosen = outcome
            break
    if chosen is None:
        raise RuleError(f"no outcome matched in rule {rule['id']}")
    needs_info = bool(missing)
    state = 'needs_info' if needs_info else chosen['state']
    provision_id = rule['provisions'][0]['id'] if needs_info else chosen['provision']
    provision = provisions[provision_id]
    if needs_info:
        message = index['needs_info_message'].replace('{provision}', provision_id)
    else:
        message = _render(chosen['message'], env)
    computed = []
    for derived in rule['derived']:
        value, _ = ev({'var': derived['name']}, env)
        computed.append({'name': derived['name'], 'label': derived['label'], 'unit': derived.get('unit'), 'value': value})
    return {
        'rule_id': rule['id'],
        'title': rule['title'],
        'article': rule['article'],
        'state': state,
        'state_label': index['states'][state],
        'outcome_id': None if needs_info else chosen['id'],
        'provision': {k: provision[k] for k in ('id', 'division', 'citation', 'pdf_page')},
        'message': message,
        'next_step': index['departs_next_step'] if state == 'departs' else None,
        'missing': [{'field': f, 'label': specs[f]['label'], 'question': specs[f]['question'], 'why': specs[f]['why']}
                    for f in missing],
        'inputs': [{'field': f, 'label': specs[f]['label'], 'unit': specs[f].get('unit'), 'value': inputs.get(f)}
                   for f in rule['inputs']],
        'ignored_inputs': ignored,
        'computed': computed,
        'assumptions': assumptions,
        'not_checked': list(rule['not_checked']),
        'reviewed': bool(rule.get('reviewed', False)),
    }


def evaluate_all(given: dict) -> list[dict]:
    index = load_index()
    return [evaluate(rule, given, index) for rule in load_rules()]
