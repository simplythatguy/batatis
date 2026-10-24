"""Evaluate the opt-in engine's actual returned candidates, without answer injection.

Provider requests use the benchmark's private cache/budget ledger. No server, case
database, credentials file, production configuration or relevance bands are changed.
Default execution is cache-only; --live explicitly permits bounded provider calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from engine.codes import Codes
from engine.identify.config import IdentifyConfig, OPENAI_VERIFIER
from engine.identify.corpus import articles
from engine.identify.pipeline import run
from engine.identify.providers import SpendLog, Transports
from engine.identify.verify import normalize

from . import live, metrics
from .cache import atomic_json, corpus_fingerprint
from .cases import all_cases
from .groups import clean_test

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'codedb/build/codedb.sqlite'
RESULTS = Path(__file__).resolve().parent / 'results'


def selected_cases():
    """Frozen recipe selection; positive held-out groups and separate intake diagnostics."""
    cases = all_cases()
    positive = [c for c in clean_test(cases) if c.kind == 'benchmark']
    boundaries = [c for c in cases if c.source == 'dev' and c.kind in ('branches', 'out_of_scope')]
    return sorted(positive, key=lambda c: c.id) + sorted(boundaries, key=lambda c: c.id)


def source_digest() -> str:
    digest = hashlib.sha256()
    paths = [ROOT / 'engine/identify' / name for name in
             ('config.py', 'pipeline.py', 'shortlist.py', 'screen.py', 'providers.py')]
    for path in paths:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def evaluate_case(case, config: IdentifyConfig, *, live_calls: bool, elephant_budget=None) -> dict:
    log, errors = SpendLog(), []

    def failure_usage(stage, provider, model, error):
        code = live.error_tag(error)
        errors.append({'stage': stage, 'category': type(error).__name__, 'code': code})
        usage = getattr(error, 'usage', None)
        if not isinstance(usage, dict):
            return  # Pre-dispatch quota/cache errors are not provider requests.
        counts = {k: usage[k] if type(usage.get(k)) is int and usage[k] >= 0 else 0
                  for k in ('input_tokens', 'output_tokens')}
        cost = usage.get('usd')
        valid_cost = type(cost) in (int, float) and math.isfinite(cost) and cost >= 0
        unknown = bool(usage.get('unknown_usage', True)) or not valid_cost
        log.add(provider=provider, model=model, **counts, usd=cost if valid_cost else 0,
                unknown_usage=unknown, error=code)

    def request(name, schema, system, user, **kwargs):
        try:
            payload, usage = live.openai_json(name, schema, system, user, **kwargs,
                                              timeout=60, live=live_calls,
                                              tag=f'engine-heldout-{case.id}-{name}')
        except Exception as error:
            failure_usage(name, 'openai', kwargs['model'], error)
            raise
        log.add(provider='openai', model=kwargs['model'], usd=usage.get('usd') or 0,
                input_tokens=usage.get('input_tokens') or 0,
                output_tokens=usage.get('output_tokens') or 0,
                returned_model=usage.get('returned_model'))
        return payload, usage

    def score(state, questions, timeout):
        try:
            result = live.elephant_ask(state, questions, budget=elephant_budget, timeout=timeout,
                                       tag=f'engine-smoke-{case.id}')
        except Exception as error:
            failure_usage('rerank', 'elephant', config.rerank_model, error)
            raise
        usage = result['usage']
        log.add(provider='elephant', usd=0, input_tokens=usage['input_tokens'],
                output_tokens=usage['output_tokens'], returned_model=result.get('model'))
        return result

    start = time.monotonic()
    record = {'case': case.id, 'source': case.source, 'kind': case.kind,
              'gold': list(case.gold), 'context': list(case.context)}
    try:
        result = run(case.description, codes=Codes(DB), config=config,
                     transports=Transports(kind='live', openai=request, log=log,
                                           elephant=score if elephant_budget is not None else None)).result
        known = articles(DB)
        returned = [a.provision for a in result.articles]
        picks = [a.provision for a in result.articles if a.verifier == 'picked']
        quote_errors = [a.provision for a in result.articles if a.quote_source == 'verifier'
                        and (not a.quote or normalize(a.quote) not in normalize(known[a.provision]['text']))]
        invalid = [a for a in returned if a not in known]
        review_failed = result.trace.verifier.startswith(('failed:', 'not run:'))
        record.update(returned=returned, picked=picks, committed=list(result.committed),
                      mode=result.mode, exhaustive=result.trace.exhaustive,
                      review_state=result.trace.verifier,
                      stage_records=[s.model_dump() for s in result.trace.stages],
                      quote_errors=quote_errors, invalid_ids=invalid,
                      usable=not errors and not review_failed and not invalid and not quote_errors
                             and not result.committed and not result.trace.exhaustive)
    except Exception as error:
        record.update(returned=[], picked=[], committed=[], usable=False, error_category=type(error).__name__)
    record.update(provider_errors=errors, wall_seconds=round(time.monotonic() - start, 3),
                  requests=len(log.calls), usd=log.usd(),
                  returned_models=sorted({c['returned_model'] for c in log.calls if c.get('returned_model')}),
                  input_tokens=sum(c['input_tokens'] for c in log.calls),
                  output_tokens=sum(c['output_tokens'] for c in log.calls),
                  unknown_usage_requests=sum(bool(c.get('unknown_usage')) for c in log.calls))
    return record


def summarize(records: list[dict]) -> dict:
    positive = [r for r in records if r['kind'] == 'benchmark']
    branches = [r for r in records if r['kind'] == 'branches']
    outside = [r for r in records if r['kind'] == 'out_of_scope']
    usable = [r for r in positive if r['usable']]
    conservative = [(r['returned'] if r['usable'] else [], r['gold']) for r in positive]
    suggested = [(r['picked'] if r['usable'] else [], r['gold']) for r in positive]
    suggestion_count = sum(len(p) for p, _ in suggested)
    suggestion_overlap = sum(len(set(r['picked']) & (set(r['gold']) | set(r.get('context') or [])))
                             for r in positive if r['usable'])
    return {
        'attempted': len(records), 'positive_attempted': len(positive),
        'positive_usable': len(usable), 'failed_cases': sum(not r['usable'] for r in records),
        'complete_cases': sum(r['usable'] and set(r['gold']) <= set(r['returned']) for r in positive),
        'all_attempted_positive': metrics.ranking_summary(conservative, ks=(10, 20, 40, 60)),
        'returned_including_fallbacks': metrics.ranking_summary(
            [(r['returned'], r['gold']) for r in positive], ks=(10, 20, 40, 60)),
        'conditional_usable': metrics.ranking_summary(
            [(r['returned'], r['gold']) for r in usable], ks=(10, 20, 40, 60)),
        'tentative_model_suggestions': {
            **metrics.ranking_summary(suggested, ks=(5, 10, 20, 60)),
            'reference_overlap_precision_lower_bound': suggestion_overlap / suggestion_count if suggestion_count else None,
            'scope': 'Tentative picks; reference sets are incomplete and extra suggestions are not adjudicated.',
        },
        'branch_diagnostics': metrics.ranking_summary(
            [(r['returned'], r['gold']) for r in branches], ks=(10, 20, 40, 60)),
        'out_of_scope': {'cases': len(outside),
                         'cases_with_model_picks': sum(bool(r['picked']) for r in outside),
                         'mean_returned': sum(len(r['returned']) for r in outside) / len(outside) if outside else 0},
        'automatic_commits': sum(len(r['committed']) for r in records),
        'invalid_ids': sum(len(r.get('invalid_ids', [])) for r in records),
        'quote_errors': sum(len(r.get('quote_errors', [])) for r in records),
        'reported_usage_usd': round(sum(r['usd'] for r in records), 6),
        'unknown_usage_requests': sum(r.get('unknown_usage_requests', 0) for r in records),
        'usage_note': 'Token-price estimate; cached replay usage is included, not a billing receipt.',
    }


def saved_summary(document: dict) -> dict:
    """A checkpoint or truncated artifact cannot masquerade as a completed evaluation."""
    records = document['records']
    ids = [r['case'] for r in records]
    selected = document.get('selected_ids')
    if len(ids) != len(set(ids)) or not isinstance(selected, list) \
            or len(selected) != len(set(selected)) or not set(ids) <= set(selected):
        raise ValueError('invalid result manifest')
    summary = summarize(records)
    before, after = document.get('corpus_fingerprint_before'), document.get('corpus_fingerprint_after')
    corpus_valid = isinstance(before, str) and len(before) == 64 and before == after \
        and not document.get('corpus_changed_during_run', False)
    summary.update(selected_cases=len(selected), unrecorded_cases=len(set(selected) - set(ids)),
                   corpus_validated=corpus_valid,
                   headline_valid=set(ids) == set(selected) and corpus_valid
                                  and not document.get('source_changed_during_run', False))
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'report'))
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--elephant', type=int, default=0,
                        help='one-case integration smoke: maximum Elephant calls, with two quota slots reserved')
    parser.add_argument('--output', type=Path, default=RESULTS / 'engine_shortlist_heldout.json')
    args = parser.parse_args(argv)
    if args.command == 'report':
        saved = json.loads(args.output.read_text())
        summary = saved_summary(saved)
        print(json.dumps(summary, indent=2))
        return int(bool(summary['failed_cases'] or not summary['headline_valid']))
    if args.workers < 1 or (args.limit is not None and args.limit < 0):
        parser.error('workers must be positive and the case limit nonnegative')
    if args.elephant < 0 or (args.elephant and args.limit != 1):
        parser.error('Elephant smoke requires --limit 1 and a nonnegative call budget')
    config = IdentifyConfig(screen='shortlist', screen_model=OPENAI_VERIFIER,
                            rerank='elephant' if args.elephant else 'none',
                            question_style='self' if args.elephant else 'shared',
                            verifier='openai', verifier_effort='medium')
    cases = selected_cases()
    if args.limit is not None:
        cases = cases[:args.limit]
    before = source_digest()
    corpus_before = corpus_fingerprint(DB)
    document = {'scope': ('Actual engine integration smoke with optional Elephant, no gold insertion.' if args.elephant
                           else 'Actual engine, non-exhaustive opt-in, no gold insertion; Elephant disabled for quota.'),
                'configuration': config.as_dict(), 'config_hash': config.config_hash,
                'source_digest': before, 'corpus_sha256': hashlib.sha256(DB.read_bytes()).hexdigest(),
                'corpus_fingerprint_before': corpus_before,
                'selected_ids': [c.id for c in cases], 'records': []}
    args.output.parent.mkdir(exist_ok=True, parents=True)
    budget = live.ElephantBudget(reserve=2, max_calls=args.elephant) if args.elephant else None
    with live.live_mode(args.live), ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        for record in executor.map(lambda c: evaluate_case(c, config, live_calls=args.live,
                                                          elephant_budget=budget), cases):
            document['records'].append(record)
            document['summary'] = saved_summary(document)
            atomic_json(args.output, document)
            print(f'{record["case"]}: {"done" if record["usable"] else "unavailable"}', flush=True)
    document['source_changed_during_run'] = source_digest() != before
    try:
        document['corpus_fingerprint_after'] = corpus_fingerprint(DB)
    except Exception:
        document['corpus_fingerprint_after'] = None
    document['corpus_changed_during_run'] = document['corpus_fingerprint_after'] != corpus_before
    document['summary'] = saved_summary(document)
    atomic_json(args.output, document)
    print(json.dumps(document['summary'], indent=2))
    return int(bool(document['summary']['failed_cases'] or not document['summary']['headline_valid']))


if __name__ == '__main__':
    raise SystemExit(main())
