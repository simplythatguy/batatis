"""Haiku low/medium on the frozen Luna workflow, with its unchanged Luna judge."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path

from . import luna_accuracy
from .codex_transport import PendingCall, pending, write_json
from .task_transport import LUNA_JUDGE, TaskTransport, haiku

REPO = Path(__file__).resolve().parents[1]
ADAPTER_FILES = ('evals_dev/task_transport.py', 'evals_dev/model_comparison.py')


def workflow(effort: str):
    # A private module instance keeps the frozen workflow functions unchanged and
    # confines transport injection to this experiment process/module.
    name = f'evals_dev._haiku_workflow_{effort}'
    spec = importlib.util.spec_from_file_location(name, REPO / 'evals_dev/luna_accuracy.py')
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    candidate = haiku(effort)
    core.CodexTransport = lambda root, case_id, stage, calls=None: TaskTransport(
        root, case_id, stage, LUNA_JUDGE if stage == 'judge' else candidate, calls)
    return core


def freeze(root: Path, effort: str):
    if os.environ.get('DPE_JUDGE_NONCE', ''):
        raise ValueError('comparison requires the Luna baseline empty judge nonce')
    if any((root / 'calls').glob('*/request.json')):
        raise ValueError('choose a fresh comparison directory')
    core = workflow(effort)
    core.freeze(root, 'local-dev')
    path = root / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest.update({'version': 'task-model-comparison-v1', 'model': 'claudeAgent:claude-haiku-5-5',
                     'effort': effort, 'service_tier': None, 'candidate': haiku(effort), 'judge': LUNA_JUDGE,
                     'judge_nonce': '',
                     'adapter_sources': {name: core.digest(REPO / name) for name in ADAPTER_FILES},
                     'transport': 'T3 delegate_task; no OpenAI or Anthropic API client',
                     'engine_model_metadata': 'Legacy engine constants are unchanged; dispatch receipts identify actual models.',
                     'comparison': 'Same local-dev inputs, engine workflow, references and Luna-max judge as local-dev-v5.'})
    write_json(path, manifest)


def validate(root: Path, effort: str):
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest.get('candidate') != haiku(effort) or manifest.get('judge') != LUNA_JUDGE:
        raise ValueError('frozen candidate or judge configuration changed')
    if manifest.get('judge_nonce') != '' or os.environ.get('DPE_JUDGE_NONCE', ''):
        raise ValueError('comparison requires the Luna baseline empty judge nonce')
    if set(manifest.get('adapter_sources', {})) != set(ADAPTER_FILES):
        raise ValueError('frozen comparison adapter inventory is incomplete')
    for name, expected in manifest['adapter_sources'].items():
        if luna_accuracy.digest(REPO / name) != expected:
            raise ValueError('frozen comparison adapter changed')
    core = workflow(effort)
    core.selected(root)
    return core


class PreparationFailure(BaseException):
    pass


def prepare(root: Path, effort: str, case_id: str | None = None):
    """Stage independent source calls, without persisting a simulated response/result."""
    from engine.codes import Codes
    from engine.intake import service
    from engine.intake.extract import scrubbed

    core, rows = validate(root, effort), []
    cases = core.selected(root)
    if case_id is not None and case_id not in {c.id for c in cases}:
        raise ValueError('case is outside this frozen comparison')
    for case in cases:
        if case_id is not None and case.id != case_id:
            continue
        sequence = []

        def collector(stage):
            bridge = core.CodexTransport(root, case.id, stage)

            def call(*args, **kwargs):
                try:
                    payload, usage = bridge(*args, **kwargs)
                except PendingCall as waiting:
                    sequence.append(waiting.path.parent.name)
                    return {'facts': []}, {}
                except Exception as error:
                    raise PreparationFailure(f'{case.id}/{stage}: {type(error).__name__}') from None
                # Record the canonical request identity even on a validated cache hit.
                request = {'system': args[0], 'user': args[1], 'schema': args[2], **bridge.target}
                sequence.append(core.fingerprint(request))
                return payload, usage
            return call

        files = [(f'file{i + 1}', a.filename, case.read(a)) for i, a in enumerate(case.attachments)]
        service.run(case.prompt, files, codes=Codes(), outbound=scrubbed, transport=collector('intake'),
                    status='live', review_transport=collector('review'), review_status='live')
        rows.append({'case_id': case.id, 'source_requests': len(sequence)})
    name = f'preparation-{case_id}.json' if case_id else 'preparation.json'
    write_json(root / name, {'cases': rows, 'simulated_responses_saved': 0,
                                         'case_results_written': 0})
    return {'cases_prepared': len(rows), 'logical_source_requests': sum(r['source_requests'] for r in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'prepare', 'resume', 'grade', 'pending'))
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--effort', required=True, choices=('low', 'medium'))
    parser.add_argument('--case')
    args = parser.parse_args()
    for name in ('BATATIS_LIVE', 'BATATIS_LIVE_JEV', 'BATATIS_LIVE_ELEPHANT'):
        os.environ[name] = '0'
    os.environ.pop('BATATIS_PROVIDER', None)
    if args.command == 'freeze':
        freeze(args.root, args.effort)
        print('comparison frozen')
        return
    core = validate(args.root, args.effort)
    if args.command == 'prepare':
        result = prepare(args.root, args.effort, args.case)
    elif args.command == 'resume':
        result = core.resume(args.root, args.case)
    elif args.command == 'grade':
        result = core.grade(args.root)
        result.update({'candidate': haiku(args.effort), 'judge': LUNA_JUDGE})
        write_json(args.root / 'summary.json', result)
    else:
        result = [{k: r[k] for k in ('request_sha256', 'case_id', 'stage', 'provider', 'model', 'options', 'path')}
                  for r in pending(args.root)]
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
