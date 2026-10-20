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

Every repeat is scored. The printed top-1, recall@5, MRR, ask rate and commit
counts are the mean, with min, max and the per-repeat values.

Two groups are reported and never pooled:

- scored_must_cite is the headline. Gold is must_cite only.
- scored_ask_identify_gold scores ask cases that carry gold.identify_gold.
  It measures retrieval of the primary article. It does not decide that the
  article applies. Its committed errors are a separate count.

A case with neither list is unscored. A commit on it is commits_no_gold, not
an error. Article match uses the leading N.N.N.N. id, so a sentence such as
9.25.5.2.(1) matches the ranked article 9.25.5.2.
"""
from __future__ import annotations

import argparse
import csv
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
METRIC_KEYS = ('top1', 'recall5', 'mrr', 'ask_rate', 'committed_errors_gold', 'commits_no_gold')
ASK_METRIC_KEYS = ('top1', 'recall5', 'mrr', 'committed_errors_ask')
ASK_GROUP = 'scored_ask_identify_gold'
MUST_GROUP = 'scored_must_cite'
ASK_NOTE = ('retrieval of the candidate article on ask cases; '
            'measures finding the article, not deciding it applies')
GOLD_LABEL = 'model-checked, not human-verified'
DEFAULT_OUT = ROOT / 'out' / 'identify-benchmark'


def _article(provision: str) -> str:
    """Article id, the leading ``N.N.N.N.`` form.

    ``9.25.5.2.(1)`` and ``9.25.5.2.`` are the same article. A clause suffix is
    ignored. The stored gold keeps the sentence id; scores compare articles.
    """
    match = ARTICLE.match(provision or '')
    return match.group(1) if match else provision


def _articles(provisions) -> list[str]:
    out: list[str] = []
    for provision in provisions or []:
        art = _article(provision)
        if art and art not in out:
            out.append(art)
    return out


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


def gold_from_entries(entries) -> tuple[list[str], list[dict]]:
    """Copy gold from must_cite, or from a public-case list of provision strings.

    An empty list stays empty. Nothing is invented for a case that has no gold.
    """
    gold: list[str] = []
    roles: list[dict] = []
    for cite in entries or []:
        if isinstance(cite, str):
            provision, role, division = cite, None, None
        else:
            provision = cite.get('provision') or ''
            role = cite.get('role')
            division = cite.get('division')
        art = _article(provision)
        roles.append({'division': division, 'provision': provision, 'role': role, 'article': art})
        if art and art not in gold:
            gold.append(art)
    return gold, roles


def split_identify_gold(entries) -> tuple[list[str], list[dict], list[str]]:
    """Primary benchmark articles, their role rows, and secondary articles.

    Only ``role: benchmark`` is the retrieval target. ``role: secondary`` is
    recorded and is not a recall target. A commit of a secondary article is
    not a committed error.
    """
    primary = [row for row in entries or [] if row.get('role') == 'benchmark']
    secondary = [row for row in entries or [] if row.get('role') == 'secondary']
    gold, roles = gold_from_entries(primary)
    related, _roles = gold_from_entries(secondary)
    return gold, roles, related


def load_cases(source: str, count: int) -> list[dict]:
    rows: list[dict] = []
    if source in ('evals_dev', 'both'):
        for path in sorted((ROOT / 'evals_dev' / 'cases').glob('dev-*.json')):
            data = json.loads(path.read_text())
            gold_block = data.get('gold') or {}
            gold, roles = gold_from_entries(gold_block.get('must_cite') or [])
            ask_gold, ask_roles, ask_secondary = split_identify_gold(gold_block.get('identify_gold') or [])
            if gold and ask_gold:
                _die(f'{data["id"]}: must_cite and identify_gold would pool two gold lists')
            rows.append({'id': data['id'], 'query': data['description'], 'gold': gold,
                         'gold_roles': roles, 'ask_gold': ask_gold, 'ask_gold_roles': ask_roles,
                         'ask_secondary': ask_secondary, 'pool': 'evals_dev'})
    if source in ('public', 'both'):
        public = json.loads((ROOT / 'evals_dev' / 'public_benchmark' / 'cases.json').read_text())
        for case in public:
            gold, roles = gold_from_entries(case.get('gold') or [])
            rows.append({'id': case['id'], 'query': case['query'], 'gold': gold,
                         'gold_roles': roles, 'ask_gold': [], 'ask_gold_roles': [],
                         'ask_secondary': [], 'pool': 'public'})
    if len(rows) < count:
        _die(f'{source} has {len(rows)} cases; this command requires at least {count}.')
    return rows[:count]


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return ordered[rank]


def repeat_metrics(rows: list[dict]) -> dict:
    """Score one repeat. `rows` each have gold, order, intake, and committed.

    Top-1, recall@5 and MRR use only rows whose gold list is non-empty.
    A commit on a no-gold row is `commits_no_gold`, not an error.
    """
    n = len(rows)
    scored = [row for row in rows if row['gold']]
    n_gold = len(scored)
    if scored:
        top1 = recall5 = mrr = 0.0
        for row in scored:
            gold = set(row['gold'])
            order = row['order']
            hits = [index for index, art in enumerate(order) if art in gold]
            top1 += 1 if set(order[:1]) & gold else 0
            recall5 += len(set(order[:5]) & gold) / len(gold)
            mrr += (1 / (hits[0] + 1)) if hits else 0
        top1 /= n_gold
        recall5 /= n_gold
        mrr /= n_gold
    else:
        top1 = recall5 = mrr = None
    errors_gold = 0
    commits_no_gold = 0
    n_ask = 0
    for row in rows:
        if row['gold']:
            gold = set(row['gold'])
            errors_gold += sum(1 for art in row['committed'] if art not in gold)
        elif row.get('ask_gold'):
            n_ask += 1
        else:
            commits_no_gold += len(row['committed'])
    return {
        'top1': top1,
        'recall5': recall5,
        'mrr': mrr,
        'ask_rate': (sum(row['intake'] == 'ask' for row in rows) / n) if n else None,
        'committed_errors_gold': errors_gold,
        'commits_no_gold': commits_no_gold,
        'n_gold': n_gold,
        'n_no_gold': n - n_gold - n_ask,
        'n_ask_gold': n_ask,
        'n': n,
    }


def ask_repeat_metrics(rows: list[dict]) -> dict:
    """Retrieval metrics for ask cases with identify_gold. Not mixed into the headline.

    ``gold`` here is the primary article list. ``secondary`` articles are not
    recall targets, and committing one is not an error.
    """
    n = len(rows)
    if not rows:
        return {'top1': None, 'recall5': None, 'mrr': None, 'committed_errors_ask': 0, 'n': 0}
    top1 = recall5 = mrr = 0.0
    errors = 0
    for row in rows:
        gold = set(row['gold'])
        allowed = gold | set(row.get('secondary') or [])
        order = row['order']
        hits = [index for index, art in enumerate(order) if art in gold]
        top1 += 1 if set(order[:1]) & gold else 0
        recall5 += len(set(order[:5]) & gold) / len(gold)
        mrr += (1 / (hits[0] + 1)) if hits else 0
        errors += sum(1 for art in row['committed'] if art not in allowed)
    return {
        'top1': top1 / n,
        'recall5': recall5 / n,
        'mrr': mrr / n,
        'committed_errors_ask': errors,
        'n': n,
    }


def majority_top1(tops: list[str | None]) -> str | None:
    """Most common top-1. A tie takes the article from the earliest repeat."""
    if not tops:
        return None
    counts: dict[str | None, int] = {}
    for art in tops:
        counts[art] = counts.get(art, 0) + 1
    best = max(counts.values())
    for art in tops:
        if counts[art] == best:
            return art
    return None


def _series(repeats: list[dict], key: str) -> dict:
    values = [row[key] for row in repeats]
    nums = [value for value in values if value is not None]
    if not nums:
        return {'mean': None, 'min': None, 'max': None, 'by_repeat': values}
    return {'mean': statistics.fmean(nums), 'min': min(nums), 'max': max(nums), 'by_repeat': values}


def aggregate(per_case: list[dict]) -> dict:
    """Mean, min, max and per-repeat metrics, plus stability and majority top-1."""
    n_repeats = len(per_case[0]['repeats']) if per_case else 0
    per_repeat = []
    for index in range(n_repeats):
        rows = [{'gold': case['gold'], 'ask_gold': case.get('ask_gold') or [],
                 'order': case['repeats'][index]['order'],
                 'intake': case['repeats'][index]['intake'],
                 'committed': case['repeats'][index]['committed']} for case in per_case]
        metrics = repeat_metrics(rows)
        metrics['repeat'] = index
        per_repeat.append(metrics)
    gold_cases = [case for case in per_case if case['gold']]
    hits = sum(1 for case in gold_cases if case['majority_top1'] in set(case['gold']))
    n = len(per_case)
    stable_n = sum(1 for case in per_case if case['stable'])
    return {
        'per_repeat': per_repeat,
        'series': {key: _series(per_repeat, key) for key in METRIC_KEYS},
        'stability': (stable_n / n) if n else None,
        'n_stable': stable_n,
        'majority_top1_accuracy': (hits / len(gold_cases)) if gold_cases else None,
        'n_gold': per_repeat[0]['n_gold'] if per_repeat else 0,
        'n_no_gold': per_repeat[0]['n_no_gold'] if per_repeat else 0,
        'n_ask_gold': per_repeat[0]['n_ask_gold'] if per_repeat else 0,
        'n': n,
    }


def ask_group_summary(per_case: list[dict]) -> dict:
    """scored_ask_identify_gold. Separate from the must_cite headline."""
    cases = [case for case in per_case if case.get('ask_gold')]
    n_repeats = len(per_case[0]['repeats']) if per_case else 0
    per_repeat = []
    for index in range(n_repeats):
        rows = [{
            'gold': case['ask_gold'],
            'secondary': case.get('ask_secondary') or [],
            'order': case['repeats'][index]['order'],
            'committed': case['repeats'][index]['committed'],
        } for case in cases]
        metrics = ask_repeat_metrics(rows)
        metrics['repeat'] = index
        per_repeat.append(metrics)
    hits = sum(1 for case in cases if case.get('ask_majority_top1') in set(case['ask_gold']))
    stable_n = sum(1 for case in cases if case.get('ask_stable'))
    n = len(cases)
    return {
        'name': ASK_GROUP,
        'note': ASK_NOTE,
        'label': GOLD_LABEL,
        'n': n,
        'per_repeat': per_repeat,
        'series': {key: _series(per_repeat, key) for key in ASK_METRIC_KEYS},
        'stability': (stable_n / n) if n else None,
        'majority_top1_accuracy': (hits / n) if n else None,
    }


def _fmt(value, digits=4) -> str:
    if value is None:
        return 'null'
    if isinstance(value, float):
        return f'{value:.{digits}f}'
    return str(value)


def _returned_ids(per_case: list[dict], requested: str | None) -> str:
    if not requested:
        return 'none'
    found: list[str] = []
    for case in per_case:
        for rep in case.get('repeats') or case.get('reps') or []:
            slot = (rep.get('by_model') or {}).get(requested) or {}
            for model_id in slot.get('returned') or []:
                if model_id not in found:
                    found.append(model_id)
    return ','.join(found) if found else 'none'


def model_id_fields(pins: dict, per_case: list[dict]) -> str:
    """Requested pin and the id the API actually returned, for rerank and verifier."""
    rerank = pins.get('rerank')
    verifier = pins.get('verifier')
    return (f"rerank_model={rerank or 'none'} rerank_returned={_returned_ids(per_case, rerank)} "
            f"verifier_model={verifier or 'none'} verifier_returned={_returned_ids(per_case, verifier)}")


def price_floor_line(variant: str, cad_per_case: float | None, fx: float, fx_date: str) -> str:
    if cad_per_case is None:
        return (f'price_floor variant={variant} cad_per_case=null floor_cad={PRICE_FLOOR_CAD:.2f} '
                f'note=usd_unavailable fx_usd_cad={fx} fx_date={fx_date}')
    delta = cad_per_case - PRICE_FLOOR_CAD
    side = 'above_floor' if delta > 0 else 'below_floor'
    return (f'price_floor variant={variant} cad_per_case={cad_per_case:.4f} floor_cad={PRICE_FLOOR_CAD:.2f} '
            f'delta_cad={delta:.4f} {side}=yes fx_usd_cad={fx} fx_date={fx_date}')


def _read_repeat(result: dict, gold: list[str]) -> dict:
    usage = (result.get('trace') or {}).get('usage') or {}
    order = _articles((result.get('trace') or {}).get('ranked_ids') or
                      [row['provision'] for row in result.get('articles') or []])
    committed = _articles(row['provision'] for row in result.get('articles') or [] if row.get('committed'))
    gold_set = set(gold)
    first = next((index for index, art in enumerate(order) if art in gold_set), None) if gold else None
    return {
        'order': order,
        'top5': order[:5],
        'committed': committed,
        'intake': result.get('intake_action'),
        'input_tokens': int(usage.get('input_tokens') or 0),
        'output_tokens': int(usage.get('output_tokens') or 0),
        'by_model': usage.get('by_model') or {},
        'first_gold_rank': first,
        'mode': result.get('mode'),
    }


def _public_case(case: dict) -> dict:
    return {
        'id': case['id'],
        'gold': case['gold'],
        'gold_roles': case['gold_roles'],
        'ask_gold': case.get('ask_gold') or [],
        'ask_secondary': case.get('ask_secondary') or [],
        'group': ASK_GROUP if case.get('ask_gold') else (MUST_GROUP if case['gold'] else 'unscored'),
        'majority_top1': case['majority_top1'],
        'stable': case['stable'],
        'repeats': [{
            'top5': rep['top5'],
            'committed': rep['committed'],
            'intake': rep['intake'],
            'input_tokens': rep['input_tokens'],
            'output_tokens': rep['output_tokens'],
            'first_gold_rank': rep['first_gold_rank'],
        } for rep in case['repeats']],
    }


def _variant_lines(name: str, pins: dict, per_case: list[dict], summary: dict, *, repeats: int,
                   fallbacks: int, input_per_case: float, output_per_case: float, latencies: list[float],
                   usd: float | None, cad: float | None, fx: float, fx_date: str) -> list[str]:
    series = summary['series']
    chars = pins['verify_chars']
    lines = [
        f"variant={name} screen={pins['screen'] or 'bm25'} {model_id_fields(pins, per_case)} "
        f"verify_chars={chars if chars is not None else 'n/a'} "
        f"n={summary['n']} n_gold={summary['n_gold']} n_ask_gold={summary['n_ask_gold']} "
        f"n_no_gold={summary['n_no_gold']} "
        f"repeats={repeats} fallbacks={fallbacks} "
        f"input_tokens_per_case={input_per_case:.1f} output_tokens_per_case={output_per_case:.1f} "
        f"p50_ms={_fmt(_percentile(latencies, 50), 1)} p95_ms={_fmt(_percentile(latencies, 95), 1)} "
        f"usd_per_case={_fmt(usd, 6)} cad_per_case={_fmt(cad, 6)} "
        f"fx_usd_cad={fx} fx_date={fx_date}"
    ]
    for rep in summary['per_repeat']:
        lines.append(
            f"variant={name} repeat={rep['repeat']} "
            f"top-1={_fmt(rep['top1'])} recall@5={_fmt(rep['recall5'])} MRR={_fmt(rep['mrr'])} "
            f"ask_rate={_fmt(rep['ask_rate'])} "
            f"committed_errors_gold={rep['committed_errors_gold']} "
            f"commits_no_gold={rep['commits_no_gold']} "
            f"n_gold={rep['n_gold']} n_ask_gold={rep['n_ask_gold']} n_no_gold={rep['n_no_gold']}"
        )
    lines.append(
        f"variant={name} summary "
        + ' '.join(
            f"{key}_mean={_fmt(series[key]['mean'])} {key}_min={_fmt(series[key]['min'])} "
            f"{key}_max={_fmt(series[key]['max'])}"
            for key in METRIC_KEYS
        )
        + f" stability={_fmt(summary['stability'])} "
        f"majority_top1={_fmt(summary['majority_top1_accuracy'])} "
        f"n_gold={summary['n_gold']} n_no_gold={summary['n_no_gold']} n={summary['n']}"
    )
    return lines


def _cost(per_case: list[dict], fx: float) -> tuple[float | None, float | None, float, float]:
    from engine.identify.config import estimate_usd

    input_per_case = statistics.fmean(
        statistics.fmean(rep['input_tokens'] for rep in case['repeats']) for case in per_case)
    output_per_case = statistics.fmean(
        statistics.fmean(rep['output_tokens'] for rep in case['repeats']) for case in per_case)
    model_names = sorted({model for case in per_case for rep in case['repeats'] for model in rep['by_model']})
    usd = 0.0
    usd_known = True
    for model in model_names:
        inn = statistics.fmean(statistics.fmean(rep['by_model'].get(model, {}).get('input_tokens', 0)
                                                for rep in case['repeats']) for case in per_case)
        out = statistics.fmean(statistics.fmean(rep['by_model'].get(model, {}).get('output_tokens', 0)
                                                for rep in case['repeats']) for case in per_case)
        part = estimate_usd(model, int(round(inn)), int(round(out)))
        if part is None:
            usd_known = False
            break
        usd += part
    if not model_names:
        usd_known = True
        usd = 0.0
    cad = usd * fx if usd_known else None
    return (usd if usd_known else None), cad, input_per_case, output_per_case


def write_results(payload: dict, out_dir: Path) -> None:
    """Write results.json and summary.csv. Refuse a payload that contains a key."""
    text = json.dumps(payload, indent=2) + '\n'
    if 'sk-' in text or 'OPENAI_API_KEY' in text:
        _die('refusing to write benchmark output that contains a key')
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'results.json').write_text(text)
    fields = ['group', 'variant', 'row', 'repeat', 'top1', 'recall5', 'mrr', 'ask_rate',
              'committed_errors_gold', 'committed_errors_ask', 'commits_no_gold',
              'n_gold', 'n_no_gold', 'n',
              'stability', 'majority_top1', 'input_tokens_per_case', 'output_tokens_per_case',
              'p50_ms', 'p95_ms', 'usd_per_case', 'cad_per_case', 'fx_usd_cad', 'fx_date',
              'rerank_model', 'rerank_returned', 'verifier_model', 'verifier_returned', 'note']
    with (out_dir / 'summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for variant in payload['variants']:
            common = {
                'group': MUST_GROUP,
                'variant': variant['name'],
                'n_gold': variant['n_gold'],
                'n_no_gold': variant['n_no_gold'],
                'n': variant['n'],
                'note': 'headline',
                'committed_errors_ask': '',
                'fx_usd_cad': payload['fx_usd_cad'],
                'fx_date': payload['fx_date'],
                'rerank_model': (variant['requested_models'] or {}).get('rerank') or '',
                'rerank_returned': ','.join(variant['returned_models'].get('rerank') or []) or 'none',
                'verifier_model': (variant['requested_models'] or {}).get('verifier') or '',
                'verifier_returned': ','.join(variant['returned_models'].get('verifier') or []) or 'none',
                'input_tokens_per_case': variant['input_tokens_per_case'],
                'output_tokens_per_case': variant['output_tokens_per_case'],
                'p50_ms': variant['p50_ms'],
                'p95_ms': variant['p95_ms'],
                'usd_per_case': variant['usd_per_case'],
                'cad_per_case': variant['cad_per_case'],
            }
            for rep in variant['per_repeat']:
                writer.writerow({**common, 'row': 'repeat', 'repeat': rep['repeat'],
                                 'top1': rep['top1'], 'recall5': rep['recall5'], 'mrr': rep['mrr'],
                                 'ask_rate': rep['ask_rate'],
                                 'committed_errors_gold': rep['committed_errors_gold'],
                                 'commits_no_gold': rep['commits_no_gold'],
                                 'stability': '', 'majority_top1': ''})
            series = variant['series']
            for label, pick in (('mean', 'mean'), ('min', 'min'), ('max', 'max')):
                writer.writerow({
                    **common, 'row': label, 'repeat': '',
                    'top1': series['top1'][pick], 'recall5': series['recall5'][pick],
                    'mrr': series['mrr'][pick], 'ask_rate': series['ask_rate'][pick],
                    'committed_errors_gold': series['committed_errors_gold'][pick],
                    'commits_no_gold': series['commits_no_gold'][pick],
                    'stability': variant['stability'] if label == 'mean' else '',
                    'majority_top1': variant['majority_top1_accuracy'] if label == 'mean' else '',
                })
            ask = variant.get('groups', {}).get(ASK_GROUP) or {}
            ask_series = ask.get('series') or {}
            ask_common = {
                'group': ASK_GROUP,
                'variant': variant['name'],
                'n_gold': '',
                'n_no_gold': '',
                'n': ask.get('n') or 0,
                'note': ask.get('note') or ASK_NOTE,
                'committed_errors_gold': '',
                'commits_no_gold': '',
                'ask_rate': '',
                'fx_usd_cad': payload['fx_usd_cad'],
                'fx_date': payload['fx_date'],
                'rerank_model': common['rerank_model'],
                'rerank_returned': common['rerank_returned'],
                'verifier_model': common['verifier_model'],
                'verifier_returned': common['verifier_returned'],
                'input_tokens_per_case': '',
                'output_tokens_per_case': '',
                'p50_ms': '',
                'p95_ms': '',
                'usd_per_case': '',
                'cad_per_case': '',
            }
            for rep in ask.get('per_repeat') or []:
                writer.writerow({**ask_common, 'row': 'repeat', 'repeat': rep['repeat'],
                                 'top1': rep['top1'], 'recall5': rep['recall5'], 'mrr': rep['mrr'],
                                 'committed_errors_ask': rep['committed_errors_ask'],
                                 'stability': '', 'majority_top1': ''})
            for label, pick in (('mean', 'mean'), ('min', 'min'), ('max', 'max')):
                writer.writerow({
                    **ask_common, 'row': label, 'repeat': '',
                    'top1': (ask_series.get('top1') or {}).get(pick),
                    'recall5': (ask_series.get('recall5') or {}).get(pick),
                    'mrr': (ask_series.get('mrr') or {}).get(pick),
                    'committed_errors_ask': (ask_series.get('committed_errors_ask') or {}).get(pick),
                    'stability': ask.get('stability') if label == 'mean' else '',
                    'majority_top1': ask.get('majority_top1_accuracy') if label == 'mean' else '',
                })


def run_variants(cases: list[dict], repeats: int, fx: float, fx_date: str, *,
                 runner=None, out_dir: Path | None = None) -> int:
    from engine.identify.config import RERANK_MODEL, VERIFY_MODEL_OPENAI
    if runner is None:
        from engine.identify.pipeline import run as runner

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
    print('accuracy=mean_of_every_repeat headline=scored_must_cite '
          'ask_group=scored_ask_identify_gold_not_pooled '
          'article_match=sentence_id_equals_article_id')
    exit_code = 0
    written_variants = []
    for name, kwargs, pins in variants:
        per_case = []
        latencies = []
        fallbacks = 0
        for case in cases:
            reps = []
            for _repeat in range(repeats):
                started = time.perf_counter()
                result = runner(case['query'], ranker=kwargs.get('ranker'), verify=kwargs.get('verify', True),
                                verify_chars=kwargs.get('verify_chars') if 'verify_chars' in kwargs else None)
                latencies.append((time.perf_counter() - started) * 1000)
                rep = _read_repeat(result, case['gold'])
                if rep['mode'] == 'bm25_fallback' and name != 'a_bm25':
                    fallbacks += 1
                reps.append(rep)
            tops = [rep['order'][0] if rep['order'] else None for rep in reps]
            ask_gold = list(case.get('ask_gold') or [])
            per_case.append({
                'id': case['id'], 'gold': list(case['gold']),
                'gold_roles': list(case.get('gold_roles') or []),
                'ask_gold': ask_gold,
                'ask_secondary': list(case.get('ask_secondary') or []),
                'ask_majority_top1': majority_top1(tops) if ask_gold else None,
                'ask_stable': len(set(tops)) <= 1 if ask_gold else None,
                'majority_top1': majority_top1(tops),
                'stable': len(set(tops)) <= 1,
                'repeats': reps,
            })
        summary = aggregate(per_case)
        ask_summary = ask_group_summary(per_case)
        usd, cad, input_per_case, output_per_case = _cost(per_case, fx)
        for line in _variant_lines(name, pins, per_case, summary, repeats=repeats, fallbacks=fallbacks,
                                   input_per_case=input_per_case, output_per_case=output_per_case,
                                   latencies=latencies, usd=usd, cad=cad, fx=fx, fx_date=fx_date):
            print(line)
        print(price_floor_line(name, cad, fx, fx_date))
        for rep in ask_summary['per_repeat']:
            print(f"group={ASK_GROUP} variant={name} repeat={rep['repeat']} "
                  f"top-1={_fmt(rep['top1'])} recall@5={_fmt(rep['recall5'])} MRR={_fmt(rep['mrr'])} "
                  f"committed_errors_ask={rep['committed_errors_ask']} n={rep['n']} "
                  f"label={GOLD_LABEL!r}")
        ask_series = ask_summary['series']
        print(f"group={ASK_GROUP} variant={name} summary n={ask_summary['n']} "
              + ' '.join(
                  f"{key}_mean={_fmt(ask_series[key]['mean'])} {key}_min={_fmt(ask_series[key]['min'])} "
                  f"{key}_max={_fmt(ask_series[key]['max'])}"
                  for key in ASK_METRIC_KEYS
              )
              + f" stability={_fmt(ask_summary['stability'])} "
              f"majority_top1={_fmt(ask_summary['majority_top1_accuracy'])} "
              f"note={ASK_NOTE!r}")
        if name != 'a_bm25' and fallbacks == len(per_case) * repeats:
            exit_code = 1
            print(f'variant={name} provider calls all fell back to BM25; check the OpenAI account, not this log, for the key.',
                  file=sys.stderr)
        written_variants.append({
            'name': name,
            'requested_models': {'screen': pins['screen'], 'rerank': pins['rerank'], 'verifier': pins['verifier'],
                                 'verify_chars': pins['verify_chars']},
            'returned_models': {
                'rerank': [] if not pins.get('rerank') else _returned_ids(per_case, pins['rerank']).split(','),
                'verifier': [] if not pins.get('verifier') else _returned_ids(per_case, pins['verifier']).split(','),
            },
            'per_repeat': [{key: rep[key] for key in
                            ('repeat', 'top1', 'recall5', 'mrr', 'ask_rate', 'committed_errors_gold',
                             'commits_no_gold', 'n_gold', 'n_no_gold', 'n')}
                           for rep in summary['per_repeat']],
            'series': summary['series'],
            'stability': summary['stability'],
            'majority_top1_accuracy': summary['majority_top1_accuracy'],
            'n_gold': summary['n_gold'],
            'n_no_gold': summary['n_no_gold'],
            'n': summary['n'],
            'groups': {
                MUST_GROUP: {
                    'name': MUST_GROUP,
                    'n': summary['n_gold'],
                    'note': 'headline accuracy on must_cite; not pooled with scored_ask_identify_gold',
                    'per_repeat': summary['per_repeat'],
                    'series': summary['series'],
                    'stability': summary['stability'],
                    'majority_top1_accuracy': summary['majority_top1_accuracy'],
                },
                ASK_GROUP: ask_summary,
            },
            'fallbacks': fallbacks,
            'input_tokens_per_case': input_per_case,
            'output_tokens_per_case': output_per_case,
            'p50_ms': _percentile(latencies, 50),
            'p95_ms': _percentile(latencies, 95),
            'usd_per_case': usd,
            'cad_per_case': cad,
            'cases': [_public_case(case) for case in per_case],
        })
        for variant in written_variants:
            for slot in variant['returned_models'].values():
                if slot == ['none']:
                    slot.clear()
    payload = {
        'provider': 'openai',
        'fx_usd_cad': fx,
        'fx_date': fx_date,
        'repeats': repeats,
        'n_cases': len(cases),
        'gold_provenance': (
            'Headline scored_must_cite copies must_cite only. '
            'scored_ask_identify_gold copies gold.identify_gold role benchmark and is not pooled. '
            'identify_gold_candidates are unscored. '
            'Article match: the leading N.N.N.N. id, so 9.25.5.2.(1) matches ranked 9.25.5.2. '
            'Ask identify_gold is model-checked, not human-verified.'
        ),
        'variants': written_variants,
    }
    write_results(payload, out_dir or DEFAULT_OUT)
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
    parser.add_argument('--out', type=Path, default=None,
                        help='Directory for results.json and summary.csv. Default: out/identify-benchmark (gitignored).')
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
    return run_variants(cases, args.repeats, args.fx_usd_cad, args.fx_date, out_dir=args.out)


if __name__ == '__main__':
    sys.exit(main())
