"""Keyed completeness benchmark for variants A, B, and C.

From the repository root, with OPENAI_API_KEY already in the environment:

    BATATIS_LLM_PROVIDER=openai python3 -m evals_dev.completeness_eval --live --repeats 3

The process never prints the key. If the key is missing, it exits with an error
before any provider call. Variant C is the LLM pass. A and B do not call a model.

The case set is the planted fixtures, the 60 evals_dev cases, and the Unc
samples (uncalibrated public precedent queries). Gold labels are used only
after a variant returns, and only for the planted set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANTED_APPS = ROOT / 'evals_dev' / 'planted' / 'apps'
PLANTED_GOLD = ROOT / 'evals_dev' / 'planted' / 'gold'
DEV_CASES = ROOT / 'evals_dev' / 'cases'
UNC_CASES = ROOT / 'evals_dev' / 'public_benchmark' / 'cases.json'

# Bank of Canada Valet FXUSDCAD, Canadian dollars per US dollar.
# Observed 2026-10-20: the latest published observation was 2026-10-19.
USD_TO_CAD = 1.4097
USD_TO_CAD_DATE = '2026-10-19'
USD_TO_CAD_SOURCE = 'Bank of Canada Valet series FXUSDCAD (daily average, CAD per USD)'
PRICE_FLOOR_CAD = 125.0
MIN_CASES = 20

VARIANTS = ('A', 'B', 'C')


@dataclass
class BenchCase:
    id: str
    source: str
    document: object
    gold: dict | None = None


@dataclass
class Observation:
    variant: str
    case_id: str
    source: str
    repeat: int
    input_tokens: int
    output_tokens: int
    latency_s: float
    usd: float
    invented_values: int
    result: object
    gold: dict | None = None


@dataclass
class VariantRollup:
    variant: str
    model_id: str
    called_model: bool
    observations: list[Observation] = field(default_factory=list)
    skipped: str | None = None


def redact(text: str) -> str:
    """Remove API keys from a message. The raw key is never returned."""
    secret = os.environ.get('OPENAI_API_KEY') or ''
    if secret:
        text = text.replace(secret, '[redacted]')
    other = os.environ.get('ANTHROPIC_API_KEY') or ''
    if other:
        text = text.replace(other, '[redacted]')
    import re
    text = re.sub(r'\bsk-[A-Za-z0-9_\-]{8,}\b', '[redacted]', text)
    text = re.sub(r'(?i)(api[_-]?key\s*[=:]\s*)\S+', r'\1[redacted]', text)
    return text


def require_openai_key() -> str:
    provider = (os.environ.get('BATATIS_LLM_PROVIDER') or '').strip().lower()
    if provider != 'openai':
        raise SystemExit(
            'BATATIS_LLM_PROVIDER must be openai for this benchmark. '
            'The key is not printed.')
    key = os.environ.get('OPENAI_API_KEY') or ''
    if not key.strip():
        raise SystemExit(
            'OPENAI_API_KEY is not set. Export it in the environment and rerun. '
            'The key is not printed.')
    return key


def _ensure_planted() -> None:
    texts = list(PLANTED_APPS.glob('*.txt')) if PLANTED_APPS.exists() else []
    from evals_dev.planted.generate import PLANTS
    if len(texts) >= len(PLANTS) and any(PLANTED_GOLD.glob('*.json')):
        return
    from evals_dev.planted.generate import main as generate_main
    generate_main()


def _narrative(case_id: str, text: str, source: str):
    from engine.ingest import Ingested
    data = text.encode('utf-8')
    return Ingested(
        ref=f'{source}:{case_id}', data=data, text=text, kind='narrative',
        submission_id=case_id,
        section_text={'A': '', 'B': text, 'C': '', 'D': '', 'process': '', 'attachment': ''})


def load_cases() -> list[BenchCase]:
    from engine.ingest import ingest_bytes

    _ensure_planted()
    cases: list[BenchCase] = []
    for path in sorted(PLANTED_APPS.glob('*.txt')):
        gold_path = PLANTED_GOLD / f'{path.stem}.json'
        gold = json.loads(gold_path.read_text()) if gold_path.exists() else None
        data = path.read_bytes()
        document = ingest_bytes(data, path.name)[0]
        document.submission_id = path.stem
        cases.append(BenchCase(path.stem, 'planted', document, gold))

    for path in sorted(DEV_CASES.glob('dev-*.json')):
        payload = json.loads(path.read_text())
        # The checker receives the applicant narrative only. Gold stays out.
        text = str(payload.get('description') or '').strip()
        if not text:
            continue
        cases.append(BenchCase(payload.get('id') or path.stem, 'evals_dev',
                               _narrative(payload.get('id') or path.stem, text, 'evals_dev')))

    if UNC_CASES.exists():
        for payload in json.loads(UNC_CASES.read_text()):
            text = str(payload.get('query') or '').strip()
            if not text:
                continue
            cases.append(BenchCase(str(payload['id']), 'unc',
                                   _narrative(str(payload['id']), text, 'unc')))
    if len(cases) < MIN_CASES:
        raise SystemExit(f'benchmark needs at least {MIN_CASES} cases; loaded {len(cases)}')
    return cases


def open_codes():
    try:
        from engine.codes import Codes
        return Codes()
    except FileNotFoundError:
        return None


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _score_planted(observations: list[Observation], codes_available: bool) -> dict:
    """Score the first repeat of planted cases. Gold is not an input to the variant."""
    first = [item for item in observations if item.repeat == 0 and item.source == 'planted' and item.result is not None]
    correct = total = 0
    per_class: dict[str, list[int]] = {}
    false_positives = []
    prompt_gaps = prompt_ready = 0
    for obs in first:
        gold = obs.gold
        if not gold:
            continue
        by_field = {element.field: element for element in obs.result.elements}
        for expected in gold.get('elements') or []:
            if expected.get('requires_codedb') and not codes_available:
                continue
            total += 1
            got = by_field.get(expected['field'])
            ok = (got is not None and got.verdict == expected['expected_verdict']
                  and (got.problem or None) == (expected.get('problem') or None))
            if ok:
                correct += 1
            defect = expected.get('defect_class')
            if defect:
                bucket = per_class.setdefault(defect, [0, 0])
                bucket[1] += 1
                if ok:
                    bucket[0] += 1
        if gold.get('control'):
            for element in obs.result.elements:
                if element.verdict != 'present' and not element.lookup_skipped:
                    false_positives.append(f'{obs.case_id}:{element.field}:{element.problem or element.verdict}')
        for element in obs.result.elements:
            if element.verdict in ('missing', 'unclear'):
                prompt_gaps += 1
                if element.prompt and element.prompt.get('question') and element.prompt.get('field'):
                    prompt_ready += 1
    return {
        'correct': correct,
        'total': total,
        'success': (correct / total) if total else 0.0,
        'per_class': per_class,
        'false_positives': false_positives,
        'prompt_coverage': (prompt_ready / prompt_gaps) if prompt_gaps else 1.0,
    }


def run_benchmark(cases: list[BenchCase], *, repeats: int, live: bool, client=None) -> list[VariantRollup]:
    from engine.completeness_variants import run_variant
    from engine.llm_judgement import OPENAI_MODEL, estimate_usd

    codes = open_codes()
    codes_available = codes is not None
    rollups = {
        'A': VariantRollup('A', 'none (deterministic rules; no provider call)', False),
        'B': VariantRollup('B', 'none (deterministic rules and heuristics; no provider call)', False),
        'C': VariantRollup('C', OPENAI_MODEL if live else f'{OPENAI_MODEL} (pinned, not called)', bool(live),
                           skipped=None if live else 'not called; rerun with --live and OPENAI_API_KEY'),
    }
    gold_by_id = {case.id: case.gold for case in cases if case.source == 'planted'}
    for repeat in range(repeats):
        for case in cases:
            for variant in VARIANTS:
                if variant == 'C' and not live:
                    continue
                started = time.perf_counter()
                try:
                    result = run_variant(variant, case.document, codes, client if variant == 'C' else None)
                except Exception as exc:
                    raise SystemExit(redact(f'variant {variant} failed on {case.source}:{case.id}: {exc}')) from None
                elapsed = time.perf_counter() - started
                usage = result.usage
                input_tokens = int(usage.input_tokens) if usage else 0
                output_tokens = int(usage.output_tokens) if usage else 0
                model = usage.model if usage else ''
                usd = estimate_usd(model, input_tokens, output_tokens) if usage else 0.0
                obs = Observation(
                    variant, case.id, case.source, repeat, input_tokens, output_tokens,
                    elapsed, usd, result.invented_values, result,
                    gold_by_id.get(case.id) if case.source == 'planted' else None)
                rollups[variant].observations.append(obs)
                print(f'progress variant={variant} case={case.source}:{case.id} repeat={repeat + 1}/{repeats}',
                      file=sys.stderr)
    for rollup in rollups.values():
        rollup.codes_available = codes_available  # type: ignore[attr-defined]
    # Silence unused import if a live run never reaches Anthropic. The pin is reported below.
    return [rollups[name] for name in VARIANTS]


def _mean_tokens(observations: list[Observation], case_id: str) -> tuple[float, float]:
    rows = [item for item in observations if item.case_id == case_id]
    if not rows:
        return 0.0, 0.0
    return (sum(item.input_tokens for item in rows) / len(rows),
            sum(item.output_tokens for item in rows) / len(rows))


def format_report(rollups: list[VariantRollup], cases: list[BenchCase], repeats: int) -> str:
    from engine.llm_judgement import ANTHROPIC_MODEL, OPENAI_MODEL
    counts = {source: sum(1 for case in cases if case.source == source) for source in ('planted', 'evals_dev', 'unc')}
    lines = [
        'completeness benchmark',
        f'parameter usd_to_cad={USD_TO_CAD}',
        f'parameter usd_to_cad_date={USD_TO_CAD_DATE}',
        f'parameter usd_to_cad_source={USD_TO_CAD_SOURCE}',
        f'parameter price_floor_cad={PRICE_FLOOR_CAD:.0f}',
        f'parameter repeats={repeats}',
        f'parameter pinned_openai_model={OPENAI_MODEL}',
        f'parameter pinned_anthropic_model={ANTHROPIC_MODEL}',
        f'cases={len(cases)} planted={counts["planted"]} evals_dev={counts["evals_dev"]} unc={counts["unc"]}',
        'unc_samples=evals_dev/public_benchmark/cases.json (uncalibrated public precedent queries; gold is not sent to the checker)',
        'success_metrics=planted fixtures only, first repeat; dev cases and Unc samples are in the cost, latency, and invented-value totals',
        '',
    ]
    gate_failed = False
    for rollup in rollups:
        lines.append(f'variant {rollup.variant}')
        lines.append(f'  model_id={rollup.model_id}')
        lines.append(f'  pinned_openai_model={OPENAI_MODEL}')
        lines.append(f'  pinned_anthropic_model={ANTHROPIC_MODEL}')
        if rollup.skipped:
            lines.append(f'  status=skipped ({rollup.skipped})')
            lines.append('  input_tokens_per_case=not measured')
            lines.append('  output_tokens_per_case=not measured')
            lines.append('  p50_latency_s=not measured')
            lines.append('  p95_latency_s=not measured')
            lines.append('  usd_per_case=not measured')
            lines.append('  cad_per_case=not measured')
            lines.append(f'  price_floor=not measured; compare a live C run with the C${PRICE_FLOOR_CAD:.0f} price floor')
            lines.append('  per_class_detection=not scored')
            lines.append('  clean_control_false_positives=not scored')
            lines.append('  overall_success=not scored')
            lines.append('  invented_values=not scored')
            lines.append('  invented_value_gate=not scored')
            lines.append('')
            continue
        case_ids = []
        for obs in rollup.observations:
            if obs.case_id not in case_ids:
                case_ids.append(obs.case_id)
        lines.append('  tokens_per_case:')
        for case_id in case_ids:
            incoming, outgoing = _mean_tokens(rollup.observations, case_id)
            lines.append(f'    {case_id} input_tokens={incoming:.1f} output_tokens={outgoing:.1f}')
        latencies = [obs.latency_s for obs in rollup.observations]
        passes = max(repeats, 1)
        usd_per_case = sum(obs.usd for obs in rollup.observations) / (len(case_ids) * passes) if case_ids else 0.0
        cad_per_case = usd_per_case * USD_TO_CAD
        relation = 'under' if cad_per_case < PRICE_FLOOR_CAD else 'at or above'
        delta = abs(PRICE_FLOOR_CAD - cad_per_case)
        invented = sum(obs.invented_values for obs in rollup.observations)
        if invented:
            gate_failed = True
        score = _score_planted(rollup.observations, bool(getattr(rollup, 'codes_available', False)))
        lines.append(f'  p50_latency_s={_percentile(latencies, 0.50):.6f}')
        lines.append(f'  p95_latency_s={_percentile(latencies, 0.95):.6f}')
        lines.append(f'  usd_per_case={usd_per_case:.6f}')
        lines.append(f'  cad_per_case={cad_per_case:.6f}')
        lines.append(
            f'  price_floor=CAD {cad_per_case:.6f} per case is {relation} the C${PRICE_FLOOR_CAD:.0f} '
            f'price floor by CAD {delta:.6f}')
        lines.append('  per_class_detection:')
        if not score['per_class']:
            lines.append('    (no planted classes in this run)')
        for name in sorted(score['per_class']):
            caught, planted = score['per_class'][name]
            rate = caught / planted if planted else 0.0
            lines.append(f'    {name} caught={caught} planted={planted} rate={rate:.3f}')
        lines.append(f'  clean_control_false_positives={len(score["false_positives"])}')
        for item in score['false_positives']:
            lines.append(f'    {item}')
        lines.append(
            f'  overall_success={score["success"]:.3f} ({score["correct"]}/{score["total"]})')
        lines.append(f'  prompt_coverage={score["prompt_coverage"]:.3f}')
        lines.append(f'  invented_values={invented}')
        lines.append(f'  invented_value_gate={"fail" if invented else "pass"}')
        lines.append('')
    lines.append(f'invented_value_gate_all={"fail" if gate_failed else "pass"}')
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Completeness benchmark for variants A, B, and C.')
    parser.add_argument('--live', action='store_true',
                        help='Call variant C with OPENAI_API_KEY. The key is not printed.')
    parser.add_argument('--repeats', type=int, default=1)
    args = parser.parse_args(argv)
    if args.repeats < 1:
        print('repeats must be at least 1', file=sys.stderr)
        return 2
    client = None
    if args.live:
        try:
            require_openai_key()
        except SystemExit as exc:
            print(redact(str(exc)), file=sys.stderr)
            return 2
        from engine.llm_judgement import OpenAIClient
        client = OpenAIClient()
    try:
        cases = load_cases()
        rollups = run_benchmark(cases, repeats=args.repeats, live=args.live, client=client)
    except SystemExit as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2
    except Exception as exc:
        print(redact(f'benchmark failed: {type(exc).__name__}: {exc}'), file=sys.stderr)
        return 1
    report = format_report(rollups, cases, args.repeats)
    sys.stdout.write(report)
    if 'invented_value_gate_all=fail' in report:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
