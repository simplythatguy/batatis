"""End-to-end candidate retrieval -> optional Elephant scoring -> full-text verifier.

`run` is cache-only unless --live is explicit; --elephant additionally bounds live Elephant attempts.
`report --input saved.json` recomputes metrics from saved records only, without corpus/case loading,
credential access, cache writes or provider dispatch. Every attempted case, including errors, is saved.
Only benchmark-kind positives enter final recall. Verifier-only gold-injected diagnostics are separate.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from engine.identify.corpus import articles

from . import live, metrics
from .cache import Store, atomic_json, corpus_fingerprint, request_key
from .cases import Case, all_cases, select
from .groups import clean_test, duplicate_groups

DB = Path(__file__).resolve().parents[2] / 'codedb' / 'build' / 'codedb.sqlite'
RESULTS = Path(__file__).resolve().parent / 'results'


@dataclass(frozen=True)
class Recipe:
    toc_effort: str | None = 'medium'      # None: no table-of-contents read
    toc_picks: int = 40
    lex_size: int = 40                     # lexical pool (0: none)
    lex_seeds: int = 8
    lex_mode: str = 'out'
    lex_sib: int = 3
    hyde: bool = False
    size: int = 60                         # final pool cap
    label_effort: str = 'high'
    two_pass: bool = False
    elephant_variant: str = 'production'


RECIPES = {
    'toc40-lex': Recipe(),
    'toc40-lex-xhigh': Recipe(label_effort='xhigh'),
    'toc40-lex-2pass': Recipe(two_pass=True),
    'toc80-lex': Recipe(toc_picks=80, size=90),
    'toc40-high-lex': Recipe(toc_effort='high'),
    'lex-only': Recipe(toc_effort=None, lex_size=60),
    'toc40-only': Recipe(lex_size=0, size=40),
}


_LEX = None
_LEX_CORPUS = None
_LEX_LOCK = threading.Lock()


def _lexical_pool(description: str, r: Recipe) -> list[str]:
    """Bind deterministic retrieval to the actual DB (including WAL), not just the proposal/recipe."""
    global _LEX, _LEX_CORPUS
    from . import candidates_lexical as lex
    with _LEX_LOCK:
        fingerprint = corpus_fingerprint(DB)
        if fingerprint != _LEX_CORPUS:
            for function in (lex.build_graph, articles):
                clear = getattr(function, 'cache_clear', None)
                if clear:
                    clear()
            _LEX_CORPUS = fingerprint
        if _LEX is None:
            _LEX = Store('lexical-pools')
        key = request_key('lexical-pool-v2', {
            'corpus_sha256': fingerprint, 'text': description, 'size': r.lex_size, 'seeds': r.lex_seeds,
            'mode': r.lex_mode, 'sib': r.lex_sib, 'base': 'bm25_v3@200'})
        with _LEX.claim(key):
            hit = _LEX.get(key)
            if hit is None:
                base = lex.bm25_v3(description, 200, db_path=DB)
                hit = lex.pool(base, r.lex_size, seeds=r.lex_seeds, mode=r.lex_mode,
                               sibling_top=r.lex_sib, g=lex.build_graph(DB))
                if corpus_fingerprint(DB) != fingerprint:
                    raise live.ProviderFailure('invalid_request')
                _LEX.put(key, hit, corpus_sha256=fingerprint)
        return list(hit)


def candidate_pool(case: Case, r: Recipe, arts: dict) -> tuple[list[str], dict]:
    from . import candidates_llm as llm
    lists, info = [], {}
    if r.toc_effort:
        toc = llm.luna_toc(case.description, effort=r.toc_effort, picks=r.toc_picks, tag=f'e2e-toc-{r.toc_effort}')
        lists.append(toc['ranked'])
        info['toc'] = {'returned': toc['returned'], 'invalid': len(toc['invalid']), 'roles': toc['roles'],
                       'usd': toc['usage'].get('usd')}
    if r.hyde:
        hy = llm.luna_hyde(case.description, tag='e2e-hyde')
        lists.append(hy['ranked'][:r.lex_size or 40])
        info['hyde'] = {'usd': hy['usage'].get('usd')}
    if r.lex_size:
        lists.append(_lexical_pool(case.description, r))
    pool = [a for a in llm.interleave(*lists) if a in arts][:r.size]
    info['sources'] = {a: [i for i, ranked in enumerate(lists) if a in ranked] for a in pool}
    return pool, info


def _case_record(case: Case) -> dict:
    return {'case': case.id, 'source': case.source, 'kind': case.kind, 'fold': case.fold,
            'gold': list(case.gold), 'context': list(case.context),
            **{k: case.meta[k] for k in ('evaluation_scope', 'evaluation_exclusion') if case.meta.get(k)}}


def run_case(case: Case, r: Recipe, arts: dict, *, elephant_budget=None, use_elephant=False) -> dict:
    """Keep metadata and any completed stages even when a later stage fails."""
    from . import verify_arm
    record = _case_record(case)
    stage = 'pool'
    try:
        pool, info = candidate_pool(case, r, arts)
        record.update(pool=pool, pool_info=info)
        if use_elephant:
            stage = 'elephant'
            from . import elephant_arm
            if pool:
                scores, einfo = elephant_arm.score_pool(case.description, pool, variant=r.elephant_variant,
                                                        budget=elephant_budget, bound='calibrated',
                                                        tag=f'e2e-{r.elephant_variant}-{case.id}')
            else:
                scores, einfo = {}, {'requests': 0}
            record.update(elephant=scores, elephant_info=einfo)
        stage = 'labels'
        if pool:
            labels = verify_arm.label_pool(case.description, pool, effort=r.label_effort, two_pass=r.two_pass,
                                           arts=arts, tag=f'e2e-label-{r.label_effort}{"-2p" if r.two_pass else ""}')
            record.update(labels=labels.labels, label_counts=labels.counts, label_usage=labels.usage)
        else:
            record.update(labels={}, label_counts={}, label_usage={})
        record['status'] = 'completed'
    except Exception as error:
        record.update(error=live.error_tag(error), error_stage=stage, status='error')
        if isinstance(getattr(error, 'usage', None), dict):
            record['failure_usage'] = error.usage
    return record


def final_labels(rec: dict, rule: str) -> dict[str, str]:
    """Only explicit labels/scores. An absent candidate/score never becomes confidently unlikely."""
    labels = {a: v['label'] for a, v in (rec.get('labels') or {}).items()
              if isinstance(v, dict) and v.get('label') in metrics.LABELS}
    if rule == 'luna':
        return labels
    if rule.startswith('luna+elephant@'):
        threshold = float(rule.split('@')[1])
        scores = rec.get('elephant') or {}
        return {a: ('check' if label == 'unlikely' and a in scores and scores[a] >= threshold else label)
                for a, label in labels.items()}
    if rule.startswith('elephant-bands@'):
        x, y = (float(v) for v in rule.split('@')[1].split(','))
        return {a: 'applies' if p >= y else 'check' if p >= x else 'unlikely'
                for a, p in (rec.get('elephant') or {}).items()}
    if rule == 'pool':
        return {a: 'check' for a in rec.get('pool') or []}
    raise ValueError('unknown combination rule')


def _failed(record: dict) -> bool:
    return bool(record.get('error') or record.get('elephant_error'))


def _rule_error(record: dict, rule: str) -> bool:
    if _failed(record) or 'pool' not in record:
        return True
    pool = set(record['pool'])
    if rule.startswith(('luna', 'elephant')) and rule != 'luna':
        scores = record.get('elephant')
        if not isinstance(scores, dict) or not pool <= scores.keys() or any(
                type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in scores.values()):
            return True
    if rule.startswith('luna'):
        if not isinstance(record.get('labels'), dict) or not pool <= final_labels(record, 'luna').keys():
            return True
    return False


def summarize(records: list[dict], rules: list[str]) -> dict:
    """Headline includes every attempted benchmark positive; diagnostic kinds stay outside it."""
    positive = [r for r in records if r.get('kind', 'benchmark') == 'benchmark' and r.get('gold')]
    completed = [r for r in positive if not _failed(r)]
    n = len(records)
    errors = sum(_failed(r) or any(_rule_error(r, rule) for rule in rules) for r in records)
    out = {'cases': n, 'attempted': n, 'completed': n - errors,
           'errors': errors, 'positive_cases': len(positive),
           'kind_counts': dict(Counter(r.get('kind', 'benchmark') for r in records)),
           'metric_scope': 'end_to_end_attempted_positives', 'attempts_known': True, 'headline_valid': True,
           'conditional_completed': {}}
    ks = (10, 20, 40, 60, 90)
    out['pool_ranking'] = metrics.ranking_summary([
        ([] if _failed(r) else r.get('pool') or [], r['gold']) for r in positive], ks=ks)
    out['conditional_completed']['pool_ranking'] = metrics.ranking_summary([
        (r.get('pool') or [], r['gold']) for r in completed], ks=ks)
    for rule in rules:
        outcomes = [metrics.label_outcome({} if _rule_error(r, rule) else final_labels(r, rule),
                                         r['gold'], r.get('context') or [], failed=_rule_error(r, rule))
                    for r in positive]
        out[rule] = metrics.label_summary(outcomes, scope='end_to_end_attempted_positives', attempt_counts=True)
        out['conditional_completed'][rule] = metrics.label_summary(
            [o for o in outcomes if not o.failed], scope='end_to_end_completed_only', attempt_counts=True)
    # Report money attributed to cases separately from the durable live ledger (which also holds
    # conservative failure/crash charges). Unknown usage is never represented as successful zero work.
    usd, unknown = 0.0, 0
    for r in records:
        usages = [r.get('label_usage') or {}, r.get('failure_usage') or {}]
        usages += [(r.get('pool_info') or {}).get(k) or {} for k in ('toc', 'hyde')]
        for usage in usages:
            value = usage.get('usd')
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                usd += value
        unknown += int(_failed(r) and not r.get('failure_usage') or
                       bool((r.get('failure_usage') or {}).get('unknown_usage')))
    out.update(attributed_usd=round(usd, 6), usd_per_case=round(usd / n, 5) if n else None,
               failures_with_unknown_usage=unknown)
    return out


def misses(records: list[dict], rule: str) -> list[dict]:
    rows = []
    for r in records:
        if r.get('kind', 'benchmark') != 'benchmark':
            continue
        fl = {} if _rule_error(r, rule) else final_labels(r, rule)
        for gold in r.get('gold') or []:
            if fl.get(gold) in ('applies', 'check'):
                continue
            lab = (r.get('labels') or {}).get(gold) or {}
            failure = ('case_error' if _failed(r) else 'not_retrieved' if gold not in (r.get('pool') or [])
                       else 'stage_unavailable' if _rule_error(r, rule) else 'verifier_unlikely')
            rows.append({'case': r['case'], 'gold': gold, 'in_pool': gold in (r.get('pool') or []),
                         'label': lab.get('label'), 'reason': lab.get('reason'), 'failure': failure,
                         'elephant': (r.get('elephant') or {}).get(gold)})
    return rows


def _rules(use_elephant: bool) -> list[str]:
    return ['pool', 'luna'] + (['luna+elephant@0.5', 'luna+elephant@0.3', 'luna+elephant@0.1',
                               'elephant-bands@0.1,0.8', 'elephant-bands@0.3,0.9'] if use_elephant else [])


def _report(saved: dict) -> dict:
    records = saved['records']
    if not isinstance(records, list) or any(not isinstance(r, dict) or 'case' not in r for r in records):
        raise ValueError('invalid saved records')
    if len({r['case'] for r in records}) != len(records):
        raise ValueError('duplicate saved records')
    records = [dict(r) for r in records]
    for record in records:
        for field in ('error', 'elephant_error'):
            if record.get(field):
                record[field] = live.ProviderFailure(record[field]).code
    manifest = saved.get('selected_cases')
    if manifest is not None:
        by_id = {r['case']: r for r in records}
        manifest_ids = {c['case'] for c in manifest}
        if len(manifest_ids) != len(manifest) or any(r['case'] not in manifest_ids for r in records):
            raise ValueError('saved selection mismatch')
        records = [by_id.get(c['case']) or {**c, 'error': 'internal_error', 'error_stage': 'not_recorded'}
                   for c in manifest]
    rules = saved.get('rules') or _rules(any('elephant' in r for r in records))
    summary = summarize(records, rules)
    known = saved.get('schema_version', 1) >= 2
    summary.update(attempts_known=known, headline_valid=known)
    if not known:
        summary['metric_scope'] = 'saved_records_only_attempt_history_unknown'
        for rule in rules:
            summary[rule]['metric_scope'] = summary['metric_scope']
    return {**saved, 'records': records, 'rules': rules, 'summary': summary, 'misses_luna': misses(records, 'luna')}


def _exit_code(report: dict) -> int:
    summary = report['summary']
    return int(bool(summary['errors'] or any(summary[rule]['errors'] for rule in report['rules'])))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('cmd', choices=('run', 'report'))
    ap.add_argument('--input', type=Path, help='saved JSON to summarize; report only')
    ap.add_argument('--name', choices=tuple(RECIPES), default='toc40-lex')
    ap.add_argument('--fold', choices=('tune', 'test', 'all'), default='tune')
    ap.add_argument('--clean', action='store_true', help='unique test groups with no twin in any tune source/kind')
    ap.add_argument('--sources', default='dev,precedent,web-ab,web-ca')
    ap.add_argument('--kinds', default='benchmark')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--live', action='store_true', help='explicitly allow uncached provider calls')
    ap.add_argument('--elephant', type=int, default=0, help='maximum live Elephant attempts (also requires --live)')
    ap.add_argument('--with-elephant', action='store_true', help='include Elephant scores; replay cache by default')
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args(argv)
    if a.workers < 1 or a.elephant < 0 or (a.limit is not None and a.limit < 0):
        ap.error('workers must be positive; attempt and case limits must be nonnegative')
    use_elephant = a.with_elephant or bool(a.elephant)
    tag = f'{a.name}_{"clean-test" if a.clean else a.fold}{"_elephant" if use_elephant else ""}'
    path = RESULTS / f'e2e_{tag}.json'
    # This branch MUST precede corpus, cases, stores and live setup. Reporting never reruns a stage.
    if a.cmd == 'report':
        try:
            report = _report(json.loads((a.input or path).read_text()))
            print(json.dumps(report, allow_nan=False, indent=1))
            return _exit_code(report)
        except Exception as error:
            print(json.dumps({'error': live.error_tag(error)}, allow_nan=False))
            return 2
    if a.input is not None:
        ap.error('--input is only valid for saved report mode')
    if a.elephant and not a.live:
        ap.error('--elephant requires explicit --live; use --with-elephant for cache replay')
    try:
        recipe = RECIPES[a.name]
        cases = all_cases()
        chosen = select(cases, fold=None if a.clean else a.fold, kinds=tuple(a.kinds.split(',')),
                        sources=tuple(a.sources.split(',')))
        if a.clean:
            keep = {c.id for c in clean_test(cases)}
            chosen = [c for c in chosen if c.id in keep]
        if a.limit is not None:
            chosen = chosen[:a.limit]
        groups = duplicate_groups(cases)
        manifest = [{**_case_record(c), 'group': groups[c.id]} for c in chosen]
        fingerprint = corpus_fingerprint(DB) if chosen else None
        # Corpus helpers memoize by path. Clear those views before each CLI run so a changed DB
        # cannot produce an old prompt under a new report fingerprint in a reused Python process.
        if chosen:
            from . import candidates_llm as llm
            for function in (articles, llm._rows, llm.article_ids, llm._retrieve):
                clear = getattr(function, 'cache_clear', None)
                if clear:
                    clear()
            if use_elephant:
                from . import elephant_arm
                elephant_arm.sentences.cache_clear()
        arts = articles(DB) if chosen else {}
        budget = live.ElephantBudget(reserve=4, max_calls=a.elephant) if a.elephant else None

        def safe(case):
            try:
                return run_case(case, recipe, arts, elephant_budget=budget, use_elephant=use_elephant)
            except Exception as error:
                return {**_case_record(case), 'status': 'error', 'error': live.error_tag(error),
                        'error_stage': 'case'}

        with live.live_mode(a.live):
            if use_elephant:
                records = []
                for case in chosen:
                    records.append(safe(case))
                    print(f'attempts {len(records)}/{len(chosen)}', file=sys.stderr, flush=True)
            else:
                with ThreadPoolExecutor(max_workers=a.workers) as pool:
                    records = list(pool.map(safe, chosen))
        if chosen and corpus_fingerprint(DB) != fingerprint:
            records = [{**rec, 'error': 'corpus_changed', 'error_stage': 'corpus', 'status': 'error'}
                       for rec in records]
        report = _report({'schema_version': 2, 'recipe': asdict(recipe), 'rules': _rules(use_elephant),
                          'corpus_sha256': fingerprint, 'selected_cases': manifest,
                          'selection_sha256': request_key('case-selection', manifest), 'records': records,
                          'selection': {'fold': 'clean-test' if a.clean else a.fold,
                                        'sources': a.sources.split(','), 'kinds': a.kinds.split(','),
                                        'limit': a.limit, 'live': a.live}})
        atomic_json(path, report)
        print(json.dumps(report, allow_nan=False, indent=1))
        return _exit_code(report)
    except Exception as error:
        print(json.dumps({'error': live.error_tag(error)}, allow_nan=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
