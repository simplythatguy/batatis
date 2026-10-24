"""Benchmark cases: a description and the Division B articles a complete application must cite.

Sources (all public or authored from the code database; none from the judge-only held-out set):
  dev        evals_dev/cases/dev-*.json, authored from codedb. `must_cite` is the gold; `ask` cases
             carry their candidate branches (`should_cite`) as gold of kind 'branches'; `redirect`
             cases have no gold and test that nothing is labelled as applying.
  precedent  docs/research/2026-10-20-vision/jev-benchmark/data/cases.json: Alberta STANDATA
             variances, interpretations, bulletins and Calgary SPVs, article numbers replaced by [ref].
  web-ab     docs/research/2026-10-23-elephant/cases-alberta.json (researched Alberta precedents)
  web-ca     docs/research/2026-10-23-elephant/cases-canada.json (researched Canadian/product precedents)

Every case keeps its historical id-hash fold. A raw test fold is NOT leakage-free: use groups.clean_test
over the full case universe before source/kind filtering. Branch/checklist/redirect cases are diagnostics,
never final positive-recall targets.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV_DIR = ROOT / 'evals_dev' / 'cases'
PRECEDENTS = ROOT / 'docs' / 'research' / '2026-10-20-vision' / 'jev-benchmark' / 'data' / 'cases.json'
WEB = {'web-ab': ROOT / 'docs' / 'research' / '2026-10-23-elephant' / 'cases-alberta.json',
       'web-ca': ROOT / 'docs' / 'research' / '2026-10-23-elephant' / 'cases-canada.json'}
_ARTICLE = re.compile(r'(\d+\.\d+\.\d+\.\d+\.)')
TEST_SHARE = 4            # of 10 hash buckets
CHECKLIST_GOLD = 8        # more gold articles than this: a topic checklist, not one situation
DEV_IDS = frozenset(f'dev-{i:03}' for i in range(1, 61))


@dataclass(frozen=True)
class Case:
    id: str
    source: str
    description: str
    gold: tuple[str, ...]                 # articles a complete answer must surface
    context: tuple[str, ...] = ()         # helpful references; never penalised, never recall targets
    kind: str = 'benchmark'               # benchmark | branches | out_of_scope | checklist | foreign_topic
    meta: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def fold(self) -> str:
        bucket = int(hashlib.sha256(self.id.encode()).hexdigest(), 16) % 10
        return 'test' if bucket < TEST_SHARE else 'tune'


def article_of(provision: str) -> str | None:
    m = _ARTICLE.match(provision or '')
    return m.group(1) if m else None


def _unique(ids) -> tuple[str, ...]:
    return tuple(dict.fromkeys(a for a in ids if a))


def dev_cases() -> list[Case]:
    out = []
    paths = sorted(DEV_DIR.glob('dev-*.json'))
    if {p.stem for p in paths} != DEV_IDS:
        raise ValueError('development case files do not match the canonical set')
    for path in paths:
        c = json.loads(path.read_text())
        if c['id'] != path.stem:
            raise ValueError('development case file/id mismatch')
        g = c['gold']
        must = _unique(article_of(m['provision']) for m in g['must_cite'] if m['division'] == 'B')
        should = _unique(article_of(m['provision']) for m in g.get('should_cite') or [] if m['division'] == 'B')
        if g.get('out_of_scope') or g.get('intake_action') == 'redirect':
            kind, gold, context = 'out_of_scope', (), ()
        elif g.get('intake_action') == 'ask':
            kind, gold, context = 'branches', should, ()
        elif must:
            kind, gold, context = 'benchmark', must, tuple(a for a in should if a not in must)
        elif should:
            kind, gold, context = 'branches', should, ()
        else:
            continue
        out.append(Case(c['id'], 'dev', c['description'], gold, context, kind,
                        {'topic': c['topic'], 'action': g.get('intake_action'), 'part': c.get('code_part')}))
    return out


def precedent_cases() -> list[Case]:
    out = []
    for c in json.loads(PRECEDENTS.read_text()):
        out.append(Case(c['id'], 'precedent', c['query'], _unique(c['gold']), (), 'benchmark',
                        {'type': c['type'], 'edition': c['edition'], 'rewrite_of': c.get('rewrite_of'),
                         'source_url': c.get('url') or ((c.get('source') or {}).get('url')
                                                     if isinstance(c.get('source'), dict) else None),
                         'family': c.get('family')}))
    return out


def web_cases(source: str) -> list[Case]:
    path = WEB[source]
    if not path.is_file():
        return []
    out = []
    for c in json.loads(path.read_text()):
        gold = _unique(c.get('gold') or [])
        if not gold:
            continue
        # A whole-topic checklist (e.g. 47 secondary-suite articles) is not a variance; score it apart.
        kind = ('foreign_topic' if c.get('evaluation_scope') == 'foreign_topic' else
                'checklist' if len(gold) > CHECKLIST_GOLD else 'benchmark')
        out.append(Case(c['id'], source, c['description'], gold,
                        tuple(a for a in _unique(c.get('context') or []) if a not in gold), kind,
                        {'type': c.get('type'), 'edition': (c.get('source') or {}).get('edition_cited'),
                         'confidence': c.get('confidence'), 'rewrite_of': c.get('rewrite_of'),
                         'source_url': (c.get('source') or {}).get('url'),
                         'evaluation_scope': c.get('evaluation_scope'),
                         'evaluation_exclusion': c.get('evaluation_exclusion')}))
    return out


def all_cases(sources: tuple[str, ...] = ('dev', 'precedent', 'web-ab', 'web-ca')) -> list[Case]:
    loaders = {'dev': dev_cases, 'precedent': precedent_cases,
               'web-ab': lambda: web_cases('web-ab'), 'web-ca': lambda: web_cases('web-ca')}
    cases = [case for source in sources for case in loaders[source]()]
    ids = [c.id for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f'duplicate case ids: {sorted(duplicates)}')
    return cases


def select(cases: list[Case], *, fold: str | None = None, kinds: tuple[str, ...] = ('benchmark',),
           sources: tuple[str, ...] | None = None, limit: int | None = None) -> list[Case]:
    if fold not in (None, 'tune', 'test', 'all'):
        raise ValueError('unknown case fold')
    if limit is not None and limit < 0:
        raise ValueError('case limit must be nonnegative')
    chosen = [c for c in cases if (fold in (None, 'all') or c.fold == fold) and c.kind in kinds
              and (sources is None or c.source in sources)]
    return chosen[:limit] if limit is not None else chosen
