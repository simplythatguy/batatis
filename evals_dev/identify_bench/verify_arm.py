"""Labeler arm: GPT Luna reads the full text of a small article pool and labels each article.

Labels (recall-first, for an alternative-solution application under NBC(AE) 2023 2nd printing):
  applies   the proposal departs from the article's acceptable solution, or a complete application
            must cite it because the proposal must meet or relies on it
  check     may be required depending on facts the description does not state, or the closest
            related requirement
  unlikely  a different subject

Every `applies` must carry a quote that occurs verbatim (whitespace-normalized) in the article's full
text, checked with engine.identify.verify.check_quotes. An `applies` whose quote fails is downgraded
to `check` and counted; it is never kept silently. The labeler never judges compliance.

The evaluation here is DIAGNOSTIC: it measures the labeler on pools that are guaranteed to contain
every gold article (gold + context + hard negatives from rank_articles), not the end-to-end pipeline.

  .venv/bin/python -m evals_dev.identify_bench.verify_arm run        # tune experiments + one test run
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from engine.identify.corpus import articles, card
from engine.identify.verify import Pick, check_quotes

from . import cases as bench_cases
from . import live, metrics

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'codedb' / 'build' / 'codedb.sqlite'
RESULTS = Path(__file__).resolve().parent / 'results'
POOL_SIZE = 25
BUDGET_USD = 2.00
TAG = 'w4-verify'
RANK = {'unlikely': 0, 'check': 1, 'applies': 2}
RETRIES = 2                 # transport failures only (unbilled); every retry is counted in the results
TRANSIENT = {'ReadError', 'ConnectError', 'RemoteProtocolError', 'ReadTimeout', 'ConnectTimeout', 'WriteError'}

SYSTEM = """You help prepare Alberta alternative-solution (variance) applications under the National Building \
Code - 2023 Alberta Edition (2nd printing), Division B. You are given a proposal and a pool of candidate \
articles with their full text. Label EVERY article in the pool exactly once, in the order listed:

- applies: the proposal departs from this article's acceptable solution, or a complete application must cite \
this article because the proposal must meet it or relies on it.
- check: this article may be required depending on facts the proposal does not state, or it is the closest \
related requirement to what the proposal changes.
- unlikely: the article is about a different subject than the proposal.

Missing a required article is far worse than flagging an extra one: when unsure between applies and check, \
choose check; when unsure between check and unlikely, choose check.

For applies, copy one sentence or phrase word for word from that article's text as the quote that shows the \
requirement; do not paraphrase, abbreviate, or join separate passages. For check and unlikely the quote may be \
empty. Give a one-sentence reason and a confidence from 0 to 1. Use only article ids from the pool. Do not judge \
whether the design complies or is safe."""

SECOND_PASS = """You help prepare Alberta alternative-solution (variance) applications under the National \
Building Code - 2023 Alberta Edition (2nd printing), Division B. A first reviewer judged the articles below \
NOT clearly required for this proposal. Re-read each one and look for any reason a complete application must \
cite it: the proposal departs from its acceptable solution, must still meet it, relies on it, or it governs \
the same element, space, assembly or hazard under facts the proposal leaves open. Label EVERY article listed \
exactly once:

- applies: a complete application must cite it (departs from, must meet, or relies on it).
- check: it may be required depending on facts not stated, or it is the closest related requirement.
- unlikely: a different subject.

For applies, copy one sentence or phrase word for word from that article's text as the quote; for check and \
unlikely the quote may be empty. Give a one-sentence reason and a confidence from 0 to 1. Use only article ids \
listed. Do not judge whether the design complies or is safe."""


def schema(pool_ids: list[str]) -> dict:
    item = {'type': 'object', 'additionalProperties': False,
            'required': ['article', 'label', 'quote', 'reason', 'confidence'],
            'properties': {'article': {'type': 'string', 'enum': list(pool_ids)},
                           'label': {'type': 'string', 'enum': list(metrics.LABELS)},
                           'quote': {'type': 'string'}, 'reason': {'type': 'string'},
                           'confidence': {'type': 'number'}}}
    return {'type': 'object', 'additionalProperties': False, 'required': ['labels'],
            'properties': {'labels': {'type': 'array', 'items': item}}}


def prompt(description: str, pool_ids: list[str], arts: dict, chars: int | None = None) -> str:
    listed = '\n\n'.join(f'<article id="{a}">\n{card(arts[a], chars)}\n</article>' for a in pool_ids)
    return f'<proposal>\n{description}\n</proposal>\n\n<pool count="{len(pool_ids)}">\n{listed}\n</pool>'


@dataclass
class Labels:
    labels: dict[str, dict]                 # article -> {label, quote, reason, confidence, quote_ok, flag}
    usage: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)

    def plain(self) -> dict[str, str]:
        return {a: v['label'] for a, v in self.labels.items()}


def parse(payload: dict, pool_ids: list[str], arts: dict) -> tuple[dict[str, dict], dict]:
    """Model rows -> one label per pool article. Unknown and duplicate rows are dropped, missing articles
    become `check` (recall-first) with flag 'missing', and an `applies` with a quote not found in the
    article's full text becomes `check` with flag 'quote_downgraded'. Every case is counted."""
    counts = {'rows': 0, 'unknown': 0, 'duplicate': 0, 'missing': 0, 'quote_downgraded': 0, 'bad_label': 0}
    pool, out = set(pool_ids), {}
    rows = payload.get('labels') if isinstance(payload, dict) else None
    for row in rows if isinstance(rows, list) else []:
        counts['rows'] += 1
        if not isinstance(row, dict):
            counts['unknown'] += 1
            continue
        a = row.get('article')
        if a not in pool or a not in arts:
            counts['unknown'] += 1
            continue
        if a in out:
            counts['duplicate'] += 1
            continue
        label = row.get('label')
        if label not in RANK:
            counts['bad_label'] += 1
            label = 'check'
        quote = str(row.get('quote') or '')
        try:
            confidence = min(1.0, max(0.0, float(row.get('confidence') or 0)))
        except (TypeError, ValueError):
            confidence = 0.0
        pick = Pick(article=a, quote=quote, reason=str(row.get('reason') or ''), confidence=confidence)
        quote_ok = bool(check_quotes([pick], [a], arts)[0])
        flag = None
        if label == 'applies' and not quote_ok:
            label, flag = 'check', 'quote_downgraded'
            counts['quote_downgraded'] += 1
        out[a] = {'label': label, 'quote': quote, 'reason': pick.reason, 'confidence': confidence,
                  'quote_ok': quote_ok, 'flag': flag}
    for a in pool_ids:
        if a not in out:
            counts['missing'] += 1
            out[a] = {'label': 'check', 'quote': '', 'reason': '', 'confidence': 0.0, 'quote_ok': False,
                      'flag': 'missing'}
    return {a: out[a] for a in pool_ids}, counts


def _call(system: str, description: str, ids: list[str], arts: dict, *, effort, model, chars, tag) -> Labels:
    payload, usage = live.openai_json('pool_labels', schema(ids), system, prompt(description, ids, arts, chars),
                                      model=model, effort=effort, max_output_tokens=32000, tag=tag)
    labels, counts = parse(payload, ids, arts)
    return Labels(labels, dict(usage), counts)


def label_pool(description: str, pool_ids: list[str], *, effort: str = 'high', model: str = 'gpt-6-luna',
               chars: int | None = None, two_pass: bool = False, arts: dict | None = None,
               tag: str = TAG) -> Labels:
    """Label every pool article applies / check / unlikely (see module docstring)."""
    arts = arts if arts is not None else articles(DB)
    ids = list(dict.fromkeys(a for a in pool_ids if a in arts))
    first = _call(SYSTEM, description, ids, arts, effort=effort, model=model, chars=chars, tag=tag)
    first.counts['unknown_input'] = len(pool_ids) - len(ids)
    if not two_pass:
        return first
    rest = [a for a in ids if first.labels[a]['label'] != 'applies']
    if not rest:
        return first
    second = _call(SECOND_PASS, description, rest, arts, effort=effort, model=model, chars=chars, tag=tag + '-2')
    merged, raised = dict(first.labels), 0
    for a, v in second.labels.items():          # the second pass may only raise a label
        if v['flag'] != 'missing' and RANK[v['label']] > RANK[merged[a]['label']]:
            merged[a] = {**v, 'flag': 'raised_by_second_pass'}
            raised += 1
    usage = {k: (first.usage.get(k) or 0) + (second.usage.get(k) or 0) for k in ('input_tokens', 'output_tokens',
                                                                                    'usd', 'seconds')}
    counts = {k: first.counts.get(k, 0) + second.counts.get(k, 0) for k in first.counts}
    counts['raised'] = raised
    return Labels(merged, usage, counts)


# ---------------------------------------------------------------- diagnostic evaluation

def build_pool(case, db=DB, size: int = POOL_SIZE, ranked: list[str] | None = None,
               arts: dict | None = None) -> list[str]:
    """gold + context + top non-gold rank_articles hits, up to `size` (gold always kept), shuffled by case id."""
    arts = arts if arts is not None else articles(db)
    pool = [a for a in dict.fromkeys(list(case.gold) + list(case.context)) if a in arts]
    if ranked is None:
        from engine.identify.search_rank import rank_articles
        ranked = rank_articles(case.description, db, limit=150)
    for a in ranked:
        if len(pool) >= size:
            break
        if a in arts and a not in pool:
            pool.append(a)
    seed = int(hashlib.sha256(case.id.encode()).hexdigest(), 16)
    random.Random(seed).shuffle(pool)
    return pool


def unit_spent(prefix: str = 'w4-') -> float:
    _, _, spend = live._stores()
    return round(sum(r['response']['usd'] for r in spend.rows() if str(r['response'].get('tag', '')).startswith(prefix)), 6)


def run_config(cs, pools, *, effort, two_pass=False, reverse=False, workers=8, arts) -> list[dict]:
    def one(case):
        ids = list(reversed(pools[case.id])) if reverse else pools[case.id]
        if unit_spent() >= BUDGET_USD - 0.05:
            return {'case': case.id, 'error': 'unit budget reached'}
        t0 = time.monotonic()
        retries = []
        for attempt in range(RETRIES + 1):
            try:
                res = label_pool(case.description, ids, effort=effort, two_pass=two_pass, arts=arts)
                break
            except Exception as error:      # counted, never hidden: a final failure scores as nothing surfaced
                msg = f'{type(error).__name__}: {str(error)[:200]}'
                if type(error).__name__ not in TRANSIENT or attempt == RETRIES:
                    return {'case': case.id, 'error': msg, 'retries': retries}
                retries.append(msg)
                time.sleep(5 * (attempt + 1))
        return {'case': case.id, 'labels': res.labels, 'usage': res.usage, 'counts': res.counts,
                'retries': retries, 'wall': round(time.monotonic() - t0, 2)}
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(one, cs))


def summarize(cs, rows) -> dict:
    by = {c.id: c for c in cs}
    outcomes, errors, counts, usd, secs, unlikely_gold = [], 0, {}, [], [], []
    retries = sum(len(r.get('retries') or []) for r in rows)
    for r in rows:
        case = by[r['case']]
        labels = {a: v['label'] for a, v in (r.get('labels') or {}).items()}
        if 'error' in r:
            errors += 1
        else:
            for k, v in r['counts'].items():
                counts[k] = counts.get(k, 0) + v
            usd.append(r['usage'].get('usd') or 0)
            secs.append(r['usage'].get('seconds') or 0)
        outcomes.append(metrics.label_outcome(labels, case.gold, case.context))
        for g in case.gold:
            if labels.get(g, 'unlikely') == 'unlikely':
                v = (r.get('labels') or {}).get(g) or {}
                unlikely_gold.append({'case': case.id, 'article': g, 'label': labels.get(g, 'error'),
                                      'reason': v.get('reason', r.get('error', '')),
                                      'confidence': v.get('confidence')})
    s = metrics.label_summary(outcomes)
    s.update({'errors': errors, 'transport_retries': retries, 'counts': counts,
              'usd_per_case': round(statistics.mean(usd), 5) if usd else None,
              'usd_total': round(sum(usd), 4),
              'latency_s_mean': round(statistics.mean(secs), 1) if secs else None,
              'latency_s_max': round(max(secs), 1) if secs else None,
              'gold_unlikely': unlikely_gold})
    return s


def agreement(a_rows, b_rows) -> dict:
    a = {r['case']: r.get('labels') or {} for r in a_rows}
    same = total = 0
    for r in b_rows:
        for art, v in (r.get('labels') or {}).items():
            if art in a.get(r['case'], {}):
                total += 1
                same += a[r['case']][art]['label'] == v['label']
    return {'articles': total, 'agreement': round(same / total, 4) if total else None}


def _row(name, s):
    return (f"| {name} | {s['cases']} | {s['complete_surfaced']} | {s['complete_applies']} | {s['recall_surfaced']} | "
            f"{s['recall_applies']} | {s['applies_precision_lb']} | {s['mean_applies']} | {s['mean_check']} | "
            f"{s['errors']} | {s['counts'].get('missing', 0)}/{s['counts'].get('unknown', 0)}/"
            f"{s['counts'].get('duplicate', 0)} | {s['counts'].get('quote_downgraded', 0)} | {s['usd_per_case']} | "
            f"{s['latency_s_mean']} |")


def report(out: dict) -> str:
    head = ('| config | cases | complete_surfaced | complete_applies | recall_surfaced | recall_applies | '
            'applies_prec_lb | mean_applies | mean_check | errors | missing/unknown/dup | quote_downgraded | '
            '$/case | latency s |\n|' + '---|' * 14)
    lines = ['# Labeler (GPT Luna) diagnostic — pool = gold + context + hard negatives',
             '', 'DIAGNOSTIC: pools always contain every gold article, so this measures the labeler, not the '
             'pipeline. `complete_surfaced` = every gold article labelled applies or check; precision is a lower '
             'bound (gold + context only).', '',
             f"Pool size {POOL_SIZE}, model gpt-6-luna, tune cases {out['tune_cases']}, test cases "
             f"{out['test_cases']}. Unit spend ${out['spend']['unit_after']} (this run ${out['spend']['this_run']}).",
             '', '## Tune', '', head]
    for name, s in out['tune'].items():
        lines.append(_row(name, s))
    lines += ['', f"Best (recall-first: complete_surfaced, then applies precision, then cost): **{out['best']}**", '',
              '## Position bias', '',
              f"Same pools reversed, {out['position_bias']['cases']} cases at {out['position_bias']['config']}: "
              f"label agreement {out['position_bias']['agreement']} over {out['position_bias']['articles']} articles; "
              f"reversed complete_surfaced {out['position_bias']['reversed_complete_surfaced']} vs forward "
              f"{out['position_bias']['forward_complete_surfaced']}.", '',
              '## Test (once, best config)', '', head, _row(out['best'], out['test']), '',
              '## Gold articles labelled unlikely (the misses that matter)', '']
    for fold, s in (('tune ' + out['best'], out['tune'][out['best']]), ('test ' + out['best'], out['test'])):
        lines.append(f'### {fold}')
        lines.append('')
        if not s['gold_unlikely']:
            lines.append('None.')
        for g in s['gold_unlikely']:
            lines.append(f"- `{g['case']}` **{g['article']}** ({g['label']}, conf {g['confidence']}): {g['reason']}")
        lines.append('')
    return '\n'.join(lines)


def run() -> dict:
    arts = articles(DB)
    allc = bench_cases.all_cases()
    tune = bench_cases.select(allc, fold='tune')
    test = bench_cases.select(allc, fold='test')
    pools = {c.id: build_pool(c, arts=arts) for c in tune + test}
    before = unit_spent()
    out = {'tune_cases': len(tune), 'test_cases': len(test), 'tune': {}, 'runs': {}}
    sub = tune[:20]
    for effort in ('medium', 'high', 'xhigh'):
        rows = run_config(sub, pools, effort=effort, arts=arts)
        out['runs'][f'{effort} (20)'] = rows
        out['tune'][f'{effort} (20)'] = summarize(sub, rows)
        print(effort, {k: out['tune'][f'{effort} (20)'][k] for k in ('complete_surfaced', 'applies_precision_lb',
                                                                    'errors', 'usd_per_case')}, unit_spent(), flush=True)

    def key(name):
        s = out['tune'][name]
        return (s['complete_surfaced'], s['applies_precision_lb'] or 0, -(s['usd_per_case'] or 0))
    effort = max(out['tune'], key=key).split()[0]
    for two in (False, True):
        name = f"{effort}{' two-pass' if two else ''} (all)"
        rows = run_config(tune, pools, effort=effort, two_pass=two, arts=arts)
        out['runs'][name] = rows
        out['tune'][name] = summarize(tune, rows)
        print(name, {k: out['tune'][name][k] for k in ('complete_surfaced', 'applies_precision_lb', 'errors')},
              unit_spent(), flush=True)
    full = [n for n in out['tune'] if n.endswith('(all)')]
    out['best'] = max(full, key=key)
    two = 'two-pass' in out['best']
    # position bias: same pools reversed, single pass at the chosen effort
    rev_cases = tune[:10]
    fwd = [r for r in out['runs'][f'{effort} (all)'] if r['case'] in {c.id for c in rev_cases}]
    rev = run_config(rev_cases, pools, effort=effort, reverse=True, arts=arts)
    out['position_bias'] = {'cases': len(rev_cases), 'config': f'{effort} single pass', **agreement(fwd, rev),
                            'reversed_complete_surfaced': summarize(rev_cases, rev)['complete_surfaced'],
                            'forward_complete_surfaced': summarize(rev_cases, fwd)['complete_surfaced']}
    test_rows = run_config(test, pools, effort=effort, two_pass=two, arts=arts)
    out['test'] = summarize(test, test_rows)
    out['runs']['test ' + out['best']] = test_rows
    out['spend'] = {'unit_before': before, 'unit_after': unit_spent(), 'this_run': round(unit_spent() - before, 4)}
    out['pools'] = pools
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / 'verify.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (RESULTS / 'verify.md').write_text(report(out) + '\n')
    return out


if __name__ == '__main__':
    if sys.argv[1:] == ['run']:
        o = run()
        print(json.dumps({'best': o['best'], 'test': {k: v for k, v in o['test'].items() if k != 'gold_unlikely'},
                          'position_bias': o['position_bias'], 'spend': o['spend']}, indent=1))
    else:
        print(__doc__)
