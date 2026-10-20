"""Keyed OpenAI identification benchmark.

One command. It refuses to start when OPENAI_API_KEY is missing, never prints that
key, and runs the official-source fetch plus codedb build before scoring.

    BATATIS_LLM_PROVIDER=openai .venv/bin/python -m engine.identify.benchmark \
      --repeats 3 --cases 20 --source evals_dev \
      --fx-usd-cad 1.4097 --fx-date 2026-10-19

`--fx-usd-cad` and `--fx-date` are required. Pass the rate you want used (Bank of Canada
series FXUSDCAD is CAD per 1 USD). The process prints those parameters; it does not
keep a silent conversion rate of its own.

Variants:
  a_bm25                    BM25 only
  b_openai_rerank           BM25 top 60 + OpenAI rerank
  c_openai_rerank_verify    (b) + OpenAI verifier on full article text
  d_verify_700              (c) with 700-character verifier cards

Leave-one-family-out does not change these ranks: identification does not read the
precedent index.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRICE_FLOOR_CAD = 125.0
ARTICLE = re.compile(r'(\d+\.\d+\.\d+\.\d+\.)')
SECRET_ENV = re.compile(r'(KEY|TOKEN|SECRET|PASSWORD)', re.I)


def _article(provision: str) -> str:
    match = ARTICLE.match(provision or '')
    return match.group(1) if match else provision


def _die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def _require_key() -> None:
    provider = os.environ.get('BATATIS_LLM_PROVIDER', 'openai').strip().lower()
    if provider != 'openai':
        _die('This benchmark is the OpenAI run. Set BATATIS_LLM_PROVIDER=openai.')
    os.environ['BATATIS_LLM_PROVIDER'] = 'openai'
    if not (os.environ.get('OPENAI_API_KEY') or '').strip():
        _die('OPENAI_API_KEY is not set. Refusing to run the keyed benchmark.')


def _clean_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not SECRET_ENV.search(key)}


def ensure_codedb() -> None:
    env = _clean_env()
    fetch = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'fetch_sources.py')], cwd=ROOT, env=env)
    if fetch.returncode != 0:
        _die(f'scripts/fetch_sources.py failed (exit {fetch.returncode})', fetch.returncode or 1)
    build = subprocess.run([sys.executable, '-m', 'codedb', 'build'], cwd=ROOT, env=env)
    if build.returncode != 0:
        _die(f'python -m codedb build failed (exit {build.returncode})', build.returncode or 1)


def load_cases(source: str, count: int) -> list[dict]:
    rows: list[dict] = []
    if source in ('evals_dev', 'both'):
        for path in sorted((ROOT / 'evals_dev' / 'cases').glob('dev-*.json')):
            data = json.loads(path.read_text())
            gold = []
            for cite in data.get('gold', {}).get('must_cite') or []:
                art = _article(cite.get('provision', ''))
                if art and art not in gold:
                    gold.append(art)
            rows.append({'id': data['id'], 'query': data['description'], 'gold': gold,
                         'pool': 'evals_dev'})
    if source in ('public', 'both'):
        public = json.loads((ROOT / 'evals_dev' / 'public_benchmark' / 'cases.json').read_text())
        for case in public:
            gold = []
            for item in case.get('gold') or []:
                art = _article(item)
                if art and art not in gold:
                    gold.append(art)
            rows.append({'id': case['id'], 'query': case['query'], 'gold': gold, 'pool': 'public'})
    if len(rows) < count:
        _die(f'{source} has {len(rows)} cases; this command requires at least {count}.')
    return rows[:count]


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return ordered[rank]


def _retrieval(cases: list[dict], ranked: dict[str, list[str]]) -> dict:
    scored = [case for case in cases if case['gold']]
    if not scored:
        return {'top1': None, 'recall5': None, 'mrr': None, 'n_scored': 0}
    top1 = recall5 = mrr = 0.0
    for case in scored:
        gold = set(case['gold'])
        order = ranked.get(case['id']) or []
        hits = [index for index, art in enumerate(order) if art in gold]
        top1 += 1 if set(order[:1]) & gold else 0
        recall5 += len(set(order[:5]) & gold) / len(gold)
        mrr += (1 / (hits[0] + 1)) if hits else 0
    n = len(scored)
    return {'top1': top1 / n, 'recall5': recall5 / n, 'mrr': mrr / n, 'n_scored': n}


def _fmt(value, digits=4) -> str:
    if value is None:
        return 'null'
    if isinstance(value, float):
        return f'{value:.{digits}f}'
    return str(value)


def price_floor_line(variant: str, cad_per_case: float | None, fx: float, fx_date: str) -> str:
    if cad_per_case is None:
        return (f'price_floor variant={variant} cad_per_case=null floor_cad={PRICE_FLOOR_CAD:.2f} '
                f'note=usd_unavailable fx_usd_cad={fx} fx_date={fx_date}')
    delta = cad_per_case - PRICE_FLOOR_CAD
    side = 'above_floor' if delta > 0 else 'below_floor'
    return (f'price_floor variant={variant} cad_per_case={cad_per_case:.4f} floor_cad={PRICE_FLOOR_CAD:.2f} '
            f'delta_cad={delta:.4f} {side}=yes fx_usd_cad={fx} fx_date={fx_date}')


def run_variants(cases: list[dict], repeats: int, fx: float, fx_date: str) -> int:
    from engine.identify.config import RERANK_MODEL, VERIFY_MODEL_OPENAI, estimate_usd
    from engine.identify.pipeline import run

    variants = [
        ('a_bm25', {'ranker': 'bm25'}, {'screen': None, 'rerank': None, 'verifier': None, 'verify_chars': None}),
        ('b_openai_rerank', {'verify': False},
         {'screen': None, 'rerank': RERANK_MODEL, 'verifier': None, 'verify_chars': None}),
        ('c_openai_rerank_verify', {'verify_chars': None},
         {'screen': None, 'rerank': RERANK_MODEL, 'verifier': VERIFY_MODEL_OPENAI, 'verify_chars': 'full'}),
        ('d_verify_700', {'verify_chars': 700},
         {'screen': None, 'rerank': RERANK_MODEL, 'verifier': VERIFY_MODEL_OPENAI, 'verify_chars': 700}),
    ]
    print(f'identify-benchmark provider=openai cases={len(cases)} repeats={repeats} '
          f'fx_usd_cad={fx} fx_date={fx_date} price_floor_cad={PRICE_FLOOR_CAD:.2f}')
    print('lofo=unchanged identification does not read the precedent index')
    exit_code = 0
    for name, kwargs, pins in variants:
        per_case = []
        latencies = []
        fallbacks = 0
        for case in cases:
            reps = []
            order = []
            intake = 'ask'
            committed = []
            for repeat in range(repeats):
                started = time.perf_counter()
                result = run(case['query'], ranker=kwargs.get('ranker'), verify=kwargs.get('verify', True),
                             verify_chars=kwargs.get('verify_chars') if 'verify_chars' in kwargs else None)
                elapsed_ms = (time.perf_counter() - started) * 1000
                latencies.append(elapsed_ms)
                usage = (result.get('trace') or {}).get('usage') or {}
                if result.get('mode') == 'bm25_fallback' and name != 'a_bm25':
                    fallbacks += 1
                reps.append({'input_tokens': int(usage.get('input_tokens') or 0),
                             'output_tokens': int(usage.get('output_tokens') or 0),
                             'by_model': usage.get('by_model') or {}})
                if repeat == 0:
                    order = list((result.get('trace') or {}).get('ranked_ids') or
                                 [row['provision'] for row in result.get('articles') or []])
                    intake = result.get('intake_action')
                    committed = [row['provision'] for row in result.get('articles') or [] if row.get('committed')]
            per_case.append({'id': case['id'], 'gold': case['gold'], 'order': order, 'intake': intake,
                             'committed': committed, 'reps': reps})
        n = len(per_case)
        input_per_case = statistics.fmean(
            statistics.fmean(rep['input_tokens'] for rep in case['reps']) for case in per_case)
        output_per_case = statistics.fmean(
            statistics.fmean(rep['output_tokens'] for rep in case['reps']) for case in per_case)
        model_names = sorted({model for case in per_case for rep in case['reps'] for model in rep['by_model']})
        usd = 0.0
        usd_known = True
        for model in model_names:
            inn = statistics.fmean(statistics.fmean(rep['by_model'].get(model, {}).get('input_tokens', 0)
                                                    for rep in case['reps']) for case in per_case)
            out = statistics.fmean(statistics.fmean(rep['by_model'].get(model, {}).get('output_tokens', 0)
                                                    for rep in case['reps']) for case in per_case)
            part = estimate_usd(model, int(round(inn)), int(round(out)))
            if part is None:
                usd_known = False
                break
            usd += part
        if not model_names:
            usd_known = True
            usd = 0.0
        cad = usd * fx if usd_known else None
        metrics = _retrieval(per_case, {case['id']: case['order'] for case in per_case})
        ask_rate = sum(case['intake'] == 'ask' for case in per_case) / n
        errors = 0
        for case in per_case:
            gold = set(case['gold'])
            errors += sum(1 for art in case['committed'] if art not in gold)
        chars = pins['verify_chars']
        print(
            f"variant={name} screen={pins['screen'] or 'bm25'} rerank_model={pins['rerank'] or 'none'} "
            f"verifier_model={pins['verifier'] or 'none'} verify_chars={chars if chars is not None else 'n/a'} "
            f"n={n} n_scored={metrics['n_scored']} repeats={repeats} fallbacks={fallbacks} "
            f"top-1={_fmt(metrics['top1'])} recall@5={_fmt(metrics['recall5'])} MRR={_fmt(metrics['mrr'])} "
            f"ask_rate={ask_rate:.4f} committed_errors={errors} "
            f"input_tokens_per_case={input_per_case:.1f} output_tokens_per_case={output_per_case:.1f} "
            f"p50_ms={_fmt(_percentile(latencies, 50), 1)} p95_ms={_fmt(_percentile(latencies, 95), 1)} "
            f"usd_per_case={_fmt(usd if usd_known else None, 6)} cad_per_case={_fmt(cad, 6)} "
            f"fx_usd_cad={fx} fx_date={fx_date}"
        )
        print(price_floor_line(name, cad, fx, fx_date))
        if name != 'a_bm25' and fallbacks == n * repeats:
            exit_code = 1
            print(f'variant={name} provider calls all fell back to BM25; check the OpenAI account, not this log, for the key.',
                  file=sys.stderr)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--repeats', type=int, required=True)
    parser.add_argument('--cases', type=int, default=20)
    parser.add_argument('--source', choices=('evals_dev', 'public', 'both'), default='evals_dev')
    parser.add_argument('--fx-usd-cad', type=float, required=True,
                        help='CAD per 1 USD. Printed in the output. Required so the rate is not silent.')
    parser.add_argument('--fx-date', required=True, help='Date of --fx-usd-cad, YYYY-MM-DD. Printed in the output.')
    parser.add_argument('--skip-build', action='store_true', help='Skip fetch and codedb build. Not for the director command.')
    args = parser.parse_args(argv)
    if args.repeats < 1:
        _die('--repeats must be at least 1')
    if args.cases < 20:
        _die('--cases must be at least 20')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', args.fx_date):
        _die('--fx-date must be YYYY-MM-DD')
    if args.fx_usd_cad <= 0:
        _die('--fx-usd-cad must be a positive CAD-per-USD rate')
    _require_key()
    if not args.skip_build:
        ensure_codedb()
    cases = load_cases(args.source, args.cases)
    return run_variants(cases, args.repeats, args.fx_usd_cad, args.fx_date)


if __name__ == '__main__':
    sys.exit(main())
