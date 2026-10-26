"""Freeze, resume and score a Codex Luna experiment using the real engine.

DATA_PROMPTS_ROOT points to restored originals; BATATIS_CODEDB to the private code
database. This CLI never dispatches a model: T3 owns dispatch and task identities.
The existing grouped split, reference construction and strict judge validator are
reused unchanged from work/data-prompts-eval-20261025@01913a80.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

from .codex_transport import CodexTransport, PendingCall, pending, write_json
from .data_prompts import checks, corpus, gold, judge, render, score

REPO = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def sources() -> dict:
    files = [p for base in ('engine', 'codedb', 'evals_dev/data_prompts', 'web/src')
             for p in sorted((REPO / base).rglob('*'))
             if p.suffix in ('.py', '.json', '.ts', '.tsx', '.css')]
    files += [REPO / 'evals_dev/codex_transport.py', REPO / 'evals_dev/luna_accuracy.py']
    return {str(p.relative_to(REPO)): digest(p) for p in files}


def local_development():
    return [c for c in corpus.select('dev') if c.city in ('Calgary', 'Edmonton')]


def freeze(root: Path, selection: str) -> None:
    if (root / 'manifest.json').exists():
        raise ValueError('experiment already frozen; choose a new run directory')
    if any((root / 'results').glob('*.json')):
        raise ValueError('run directory contains pre-existing results; choose an empty run directory')
    cases = local_development() if selection == 'local-dev' else corpus.select(selection)
    if not cases:
        raise ValueError('empty selection')
    if len({c.id for c in cases}) != len(cases):
        raise ValueError('duplicate cases cannot be counted as independent work')
    components = corpus._components(corpus.load())
    data = {'version': 'codex-luna-experiment-v4', 'selection': selection,
            'case_ids': [c.id for c in cases], 'split': corpus.split(), 'sources': sources(),
            'index_sha256': digest(corpus.METADATA_ROOT / 'index.json'),
            'source_components': {c.id: components[c.id] for c in cases},
            'input_hashes': {c.id: {'prompt': hashlib.sha256(c.prompt.encode()).hexdigest(),
                                  'attachments': [a.sha256 for a in c.attachments]} for c in cases},
            'reference_hashes': {c.id: {name: digest(corpus.METADATA_ROOT / c.folder / name)
                                      for name in ('source.json', 'evaluation.json')} for c in cases},
            'codedb': digest(Path(os.environ['BATATIS_CODEDB'])),
            'model': 'codex:gpt-6-luna', 'effort': 'max', 'service_tier': 'priority',
            'cost': None, 'usage': None, 'transport': 'T3 delegate_task; no OpenAI API',
            'claim_scope': 'local Codex agent diagnostic; not hosted-product accuracy',
            'hosted_context_verified': False,
            'identify': 'bm25_v3 top60, Luna full-text verify60; no automatic commitment',
            'limits': ['Model-graded source coverage, not professional validation.',
                       'T3 injects workspace/orchestration instructions; inference context differs from the hosted app.',
                       'Private restored attachments; 4MB hosted upload cap bypassed.',
                       'Local transport experiment; hosted transport is unchanged.']}
    write_json(root / 'manifest.json', data)


def selected(root: Path):
    manifest = json.loads((root / 'manifest.json').read_text())
    if digest(corpus.METADATA_ROOT / 'index.json') != manifest['index_sha256']:
        raise ValueError('frozen case index changed')
    actual_sources = sources()
    changed = sorted(name for name in actual_sources.keys() | manifest['sources'].keys()
                     if actual_sources.get(name) != manifest['sources'].get(name))
    if changed:
        raise ValueError(f'frozen source changed; create a new experiment: {changed[:3]}')
    if digest(Path(os.environ['BATATIS_CODEDB'])) != manifest['codedb']:
        raise ValueError('frozen code database changed')
    by_id = {c.id: c for c in corpus.load()}
    if corpus.split() != manifest['split']:
        raise ValueError('grouped split changed')
    for cid in manifest['case_ids']:
        c = by_id[cid]
        actual = {'prompt': hashlib.sha256(c.prompt.encode()).hexdigest(),
                  'attachments': [a.sha256 for a in c.attachments]}
        if actual != manifest['input_hashes'][cid] or any(
                digest(corpus.METADATA_ROOT / c.folder / name) != expected
                for name, expected in manifest['reference_hashes'][cid].items()):
            raise ValueError('frozen case inputs or references changed')
    return [by_id[cid] for cid in manifest['case_ids']]


def seal(root: Path, case_id: str, result: dict, calls: list) -> dict:
    frozen = json.loads((root / 'manifest.json').read_text())
    return {**result, 'provenance': {'manifest_sha256': fingerprint(frozen),
                                   'case_input_sha256': fingerprint(frozen['input_hashes'][case_id]),
                                   'content_sha256': fingerprint({'content': result, 'calls': calls}), 'calls': calls}}


def bound_result(root: Path, case_id: str) -> dict:
    result = json.loads((root / 'results' / f'{case_id}.json').read_text())
    frozen = json.loads((root / 'manifest.json').read_text())
    if not isinstance(result, dict) or not isinstance(result.get('provenance'), dict):
        raise ValueError('result is not bound to this frozen experiment')
    proof = result['provenance']
    if not isinstance(proof.get('calls'), list) or any(not isinstance(c, dict) for c in proof['calls']):
        raise ValueError('invalid model call receipts')
    content = {k: v for k, v in result.items() if k != 'provenance'}
    if result.get('case_id') != case_id or proof.get('manifest_sha256') != fingerprint(frozen) \
            or proof.get('case_input_sha256') != fingerprint(frozen['input_hashes'][case_id]) \
            or proof.get('content_sha256') != fingerprint({'content': content, 'calls': proof.get('calls')}):
        raise ValueError('result is not bound to this frozen experiment')
    for call in proof.get('calls') or []:
        if not re.fullmatch(r'[0-9a-f]{64}', call.get('request_sha256') or ''):
            raise ValueError('invalid model request identity')
        path = root / 'calls' / call['request_sha256'] / 'response.json'
        if digest(path) != call['response_sha256'] \
                or digest(path.with_name('request.json')) != call['request_file_sha256'] \
                or json.loads(path.read_text()).get('task_id') != call['task_id']:
            raise ValueError('model response changed after the result was saved')
    return result


def run_case(case, root: Path) -> dict:
    from engine.codes import Codes
    from engine.completeness import check_completeness
    from engine.identify.config import IdentifyConfig
    from engine.identify.pipeline import description_hash, run
    from engine.identify.providers import Transports
    from engine.intake import service
    from engine.intake.extract import scrubbed
    from engine.intake.plan import description
    from engine.models import Case
    from engine.redact import known_values, scrub

    codes, app = Codes(), Case()
    files = [(f'file{i + 1}', a.filename, case.read(a)) for i, a in enumerate(case.attachments)]
    calls = []
    intake = CodexTransport(root, case.id, 'intake', calls)
    review = CodexTransport(root, case.id, 'review', calls)
    extraction = service.run(case.prompt, files, codes=codes, outbound=scrubbed,
                             transport=intake, status='live', review_transport=review, review_status='live')
    service.apply(app, case.prompt, extraction)
    result = {'case_id': case.id, 'errors': [], 'expected_stages':
              {'intake_model': True, 'document_review': bool(files), 'identify': True, 'verify': True}}
    redirected = bool(app.intake and app.intake.plan and app.intake.plan.scope.status == 'redirect')
    result['identify_skipped'] = redirected
    if not redirected:
        text = description(app)
        tp = Transports(kind='live', openai=CodexTransport(root, case.id, 'identify', calls).identify)
        config = IdentifyConfig(screen='bm25_v3', rerank='none', verifier='openai',
                                rerank_n=60, verify_n=60, top_k=10)
        output = run(scrub(text, known_values(app, [])), codes=codes, config=config,
                     transports=tp, facts=app.facts, description_sha256=description_hash(text))
        app.identify = output.result
    service.refresh(app)
    result['case'] = app.model_dump(mode='json')
    result['gaps'] = [g.model_dump(mode='json') for g in check_completeness(app, codes)]
    result['failure_reasons'] = checks.completion(result)
    return seal(root, case.id, result, calls)


def resume(root: Path, case_id: str | None = None) -> dict:
    counts = Counter()
    cases = selected(root)
    if case_id is not None and case_id not in {c.id for c in cases}:
        raise ValueError('case is outside this frozen experiment')
    for case in cases:
        if case_id is not None and case.id != case_id:
            continue
        path = root / 'results' / f'{case.id}.json'
        if path.exists():
            existing = bound_result(root, case.id)
            counts['failed' if checks.completion(existing) else 'complete'] += 1
            continue
        try:
            result = run_case(case, root)
        except PendingCall:
            counts['pending'] += 1
        except Exception as error:
            write_json(path, seal(root, case.id, {'case_id': case.id, 'errors': [type(error).__name__]}, []))
            counts['failed'] += 1
        else:
            write_json(path, result)
            counts['failed' if checks.completion(result) else 'complete'] += 1
    return dict(counts)


def grade(root: Path) -> dict:
    from engine.codes import Codes
    codes, rows = Codes(), []
    for case in selected(root):
        path = root / 'results' / f'{case.id}.json'
        invalid_result = False
        try:
            result = bound_result(root, case.id) if path.exists() else {}
        except (ValueError, KeyError, OSError):
            result, invalid_result = {}, True
        reference = gold.gold(case, codes)
        reasons = checks.completion(result)
        if invalid_result:
            reasons = ['result_provenance_mismatch']
        verdicts = []
        judge_calls = []
        invalid = {'unverified', 'missing_verdict', 'duplicate_verdict', 'invalid_verdict', 'invalid_payload',
                   'invalid_ids', 'old-validator', 'cache_request_mismatch'}
        if not reasons:
            bridge = CodexTransport(root, case.id, 'judge', judge_calls)
            try:
                verdicts = judge.grade(case.prompt, render.report(result), list(reference.items),
                                       model='gpt-6-luna', effort='max', transport=bridge,
                                       cache_root=root / 'judge-cache')
            except PendingCall:
                reasons = ['pending_judge']
            except Exception as error:
                reasons = [f'judge:{type(error).__name__}']
            if any(v.note in invalid for v in verdicts):
                reasons = ['judge_invalid_verdict']
        found = {v.id: v for v in verdicts}
        items = [{'id': i.id, 'kind': i.kind, 'passed': bool(found.get(i.id) and found[i.id].passed),
                  'scored': bool(i.id in found and found[i.id].note not in invalid),
                  'note': found[i.id].note if i.id in found else '; '.join(reasons),
                  'evidence': found[i.id].evidence if i.id in found else ''} for i in reference.items]
        items += [{'id': f'A:{a}', 'kind': 'A', 'passed': ok and not reasons, 'scored': not reasons}
                  for a, ok in checks.articles(reference.articles, result)]
        rows.append({'case_id': case.id, 'tier': case.tier, 'city': case.city, 'checks': items,
                     'failure_reasons': reasons, 'guardrails': checks.guardrails(case, result, codes),
                     'review_status': (((result.get('case') or {}).get('intake') or {}).get('review') or {}).get('status'),
                     'unread_input': [f['text'] for f in (((result.get('case') or {}).get('intake') or {})
                                                          .get('review') or {}).get('flags') or []
                                      if f.get('kind') == 'not_read'],
                     'judge_calls': judge_calls,
                     'validator_version': judge.VERSION, 'provenance': 'frozen-codex-experiment'})
    write_json(root / 'scores.json', rows)
    summary = score.summarize(rows)
    summary['cases_expected'] = len(selected(root))
    summary['cases_judged'] = sum(not r['failure_reasons'] for r in rows)
    summary['whole_cases_correct'] = sum(all(c['passed'] for c in r['checks'])
                                         and all(v[0] for v in r['guardrails'].values()) for r in rows)
    summary['by_city'] = {city: {'cases': len(local), 'checks': sum(len(r['checks']) for r in local),
                               'passed': sum(c['passed'] for r in local for c in r['checks'])}
                          for city in sorted({r['city'] for r in rows})
                          if (local := [r for r in rows if r['city'] == city])}
    manifest = json.loads((root / 'manifest.json').read_text())
    complete_local = manifest.get('selection') == 'local-dev' and \
        {r['case_id'] for r in rows} == {c.id for c in local_development()} and \
        {r['city'] for r in rows} == {'Calgary', 'Edmonton'}
    summary['complete_local_development_selection'] = complete_local
    all_checks = [c for row in rows for c in row['checks']]
    summary['check_coverage_target_met'] = complete_local and not summary['cases_failed'] and \
        not summary['cases_with_unread_input'] and \
        sum(c['passed'] for c in all_checks) * 100 >= 95 * len(all_checks) and \
        all(v['passed'] == v['n'] for v in summary['guardrails'].values()) and \
        all(v['checks'] and v['passed'] * 100 >= 95 * v['checks'] for v in summary['by_city'].values())
    # A workspace agent is a different inference context from the hosted application.
    # Its diagnostic score cannot certify the user's production accuracy target.
    summary['production_accuracy_established'] = False
    summary['target_met'] = False
    summary['cost'] = None
    summary['grading'] = 'Codex Luna max; model-graded, not expert validated'
    write_json(root / 'summary.json', summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('freeze', 'resume', 'pending', 'grade'))
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--selection', default='dev')
    p.add_argument('--case', help='Resume only this case; use disjoint cases for parallel workers.')
    args = p.parse_args()
    if args.case and args.command != 'resume':
        p.error('--case is only supported for resume')
    # Keep all engine network providers disabled even if the parent has private keys.
    os.environ['BATATIS_LIVE'] = '0'
    os.environ['BATATIS_LIVE_ELEPHANT'] = '0'
    os.environ.pop('BATATIS_PROVIDER', None)
    if args.command == 'freeze':
        freeze(args.root, args.selection)
        print('experiment frozen')
    elif args.command == 'pending':
        print(json.dumps(pending(args.root), ensure_ascii=False))
    else:
        print(json.dumps(resume(args.root, args.case) if args.command == 'resume' else grade(args.root), indent=2))


if __name__ == '__main__':
    main()
