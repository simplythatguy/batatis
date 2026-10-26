"""Run the real local identifier from an exported input-only bundle.

This predictor imports the wire protocol, never the scorer, manifest, or keys.
Application/export and browser layers require their own observed captures.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from evals_dev.requirement_bench.protocol import (Invalid, canonical, checked_ref, file_ref, fingerprint,
                                                read_json, require, write_json)


def frozen_config():
    """Exact production source hashes, including uncommitted Python changes."""
    from engine.identify.config import load_config
    from evals_dev.requirement_bench.protocol import hash_file
    repo = Path(__file__).resolve().parents[1]
    paths = sorted([*repo.joinpath('engine').rglob('*.py'), *repo.joinpath('codedb').rglob('*.py'),
                    repo / 'engine/identify/pipeline.json', Path(__file__).resolve(),
                    Path(__file__).parent / 'requirement_bench/protocol.py'])
    source_hash = fingerprint({str(p.relative_to(repo)): hash_file(p) for p in paths})
    return {'predictor': {'name': 'batatis-local-requirement-ledger',
            'git_commit': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
            'dirty': bool(subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'])),
            'source_sha256': source_hash}, 'settings': {'identify_config': load_config().as_dict()}}


def _reference(item):
    return {'document': 'NBC-AE', 'edition': '2023', 'printing': '2nd',
            'division': item.division, 'provision': item.provision_id}


def capture(request, bundle: Path, out: Path, codes, config):
    from engine.identify.case_input import active_facts, compose
    from engine.identify.pipeline import run
    from engine.models import Case, Fact, Source
    from engine.store import CaseStore

    started = time.perf_counter()
    inp = request['input']
    from evals_dev.requirement_bench.protocol import digest_bytes, validate_request
    validate_request(request)
    binding = {k: v for k, v in request.items() if k != 'input'}
    # Export hashes bind exact JSON file bytes, which need not use canonical formatting.
    from evals_dev.requirement_bench.protocol import hash_file
    require(hash_file(bundle / 'predictor-config.json') == request['config_sha256'], 'config hash mismatch')
    require(hash_file(bundle / 'source-catalog.json') == request['catalog_sha256'], 'catalog hash mismatch')
    catalog = read_json(bundle / 'source-catalog.json')
    require(catalog['kind'] == 'source_snapshot', 'real capture requires a source snapshot catalog')
    corpus_files = catalog['provenance']['corpus_files']
    def source_matches():
        return corpus_files == {'database': hash_file(Path(codes.db_path)),
                                'wal': hash_file(Path(str(codes.db_path) + '-wal'))
                                if Path(str(codes.db_path) + '-wal').exists() else None}
    require(source_matches(), 'corpus differs from the frozen catalog')
    facts = [Fact(field='project.description', value=inp['narrative'], kind='pointed', status='confirmed',
                  source=Source(type='user_text', ref='evaluation narrative'))]
    facts += [Fact(field=f['field'], value=f['value'], kind='pointed', status='confirmed',
                   source=Source(type='user_text', ref='evaluation supplied fact')) for f in inp['facts']]
    request_name = f'{request["input_sha256"]}.request.json'
    write_json(out / request_name, request)
    observed = {'request': file_ref(out, request_name), 'config': file_ref(out, 'predictor-config.json'),
                'catalog': file_ref(out, 'source-catalog.json'), 'attachments': []}
    with tempfile.TemporaryDirectory(prefix='batatis-requirement-capture-') as temp:
        store = CaseStore(Path(temp) / 'cases.sqlite')
        case = store.put(Case(facts=facts))
        for index, attachment in enumerate(inp['attachments']):
            path = checked_ref(bundle, {'path': attachment['path'], 'sha256': attachment['sha256']})
            data = path.read_bytes()
            require(digest_bytes(data) == attachment['sha256'], 'attachment changed while reading')
            name = f'{request["input_sha256"]}.attachment-{index}.bin'
            with (out / name).open('xb') as stream:
                stream.write(data)
            observed['attachments'].append(file_ref(out, name))
            store.put_file(case.id, path.name, data, attachment['media_type'])
        context = compose(case, store)
        result = run(context.text, codes=codes, config=config, facts=active_facts(case)).result
    require(source_matches(), 'corpus changed during identification')
    require(sum(s.requests for s in result.trace.stages) == 0, 'capture unexpectedly dispatched a provider')
    result.input_sha256, result.input_coverage_gaps = context.sha256, list(context.gaps)
    raw_name = f'{request["input_sha256"]}.engine.json'
    write_json(out / raw_name, result.model_dump(mode='json'))
    require(result.requirement_status != 'source_unavailable', 'identifier source verification unavailable')
    raw = file_ref(out, raw_name)
    verified = [r for r in result.requirements if r.source_status == 'verified' and r.provision_id]
    candidates = [{'reference': _reference(r), 'resolution': 'resolved', 'reason': None} for r in verified]
    identified = [{'reference': _reference(r), 'resolution': 'resolved', 'reason': None} for r in verified
                  if r.applicability == 'confirmed' and not r.needs_review and r.disposition != 'exclude']
    evidence = {**binding, 'kind': 'captured', 'layers': {
        'retrieval_candidates': {'items': candidates, 'raw_artifacts': [raw]},
        'identified_requirements': {'items': identified, 'raw_artifacts': [raw]},
    }}
    evidence_name = f'{request["input_sha256"]}.layers.json'
    write_json(out / evidence_name, evidence)
    ref = file_ref(out, evidence_name)
    return {**binding, 'status': 'ok', 'error': None,
            'elapsed_ms': round((time.perf_counter() - started) * 1000, 3), 'requests': [],
            'observed_inputs': observed,
            'layers': {'retrieval_candidates': ref, 'identified_requirements': ref,
                       'application_included': None, 'applicant_visible': None}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from engine.codes import Codes
        from engine.identify.config import load_config
        from evals_dev.requirement_bench.protocol import loads
        config = load_config()
        require(config.screen == 'requirements', 'only the local requirements profile is allowed')
        frozen = read_json(args.bundle / 'predictor-config.json')
        require(frozen['settings'].get('identify_config') == config.as_dict(), 'predictor config is not the frozen profile')
        require(frozen == frozen_config(), 'predictor source or revision differs from frozen config')
        require(not args.out.exists(), 'capture output already exists; use a fresh directory')
        args.out.mkdir(parents=True)
        for name in ('predictor-config.json', 'source-catalog.json'):
            shutil.copyfile(args.bundle / name, args.out / name)
        codes = Codes(args.db)
        records = []
        for line in (args.bundle / 'requests.jsonl').read_text().splitlines():
            request = loads(line)
            started = time.perf_counter()
            try:
                require(frozen == frozen_config(), 'predictor source or profile changed during capture')
                record = capture(request, args.bundle, args.out, codes, config)
                require(frozen == frozen_config(), 'predictor source or profile changed during capture')
            except Exception as error:
                binding = {k: v for k, v in request.items() if k != 'input'}
                record = {**binding, 'status': 'error', 'error': f'{type(error).__name__}: {error}',
                          'elapsed_ms': round((time.perf_counter() - started) * 1000, 3), 'requests': [],
                          'observed_inputs': None,
                          'layers': {name: None for name in ('retrieval_candidates', 'identified_requirements',
                                                           'application_included', 'applicant_visible')}}
            records.append(record)
        with (args.out / 'predictions.jsonl').open('x') as stream:
            for record in records:
                stream.write(canonical(record).decode() + '\n')
        print(json.dumps({'planned': len(records), 'errors': sum(r['status'] != 'ok' for r in records),
                          'provider_requests': 0, 'application_and_visibility': 'not_captured'}))
        return int(any(r['status'] != 'ok' for r in records))
    except (Invalid, OSError, KeyError, ValueError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
