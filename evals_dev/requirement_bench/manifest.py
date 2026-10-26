"""Seal datasets, enforce split isolation, and export predictor-only bundles.

Sealing hashes answer files as opaque bytes. Only scoring loads their contents.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

from .protocol import (VERSION, canonical, checked_ref, child, digest_bytes, file_ref,
                       fingerprint, hash_file, is_hash, nonempty, read_json, reference,
                       require, shape, validate_input, validate_request, write_json)

SPLITS = ('train', 'dev', 'holdout')
CASE_FIELDS = {'case_id', 'split', 'groups', 'input', 'answer', 'leakage_review'}


def git_state(root: Path) -> dict:
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)
    try:
        status = git('status', '--porcelain')
        return {'head': git('rev-parse', 'HEAD').decode().strip(), 'dirty': bool(status),
                'status_sha256': digest_bytes(status)}
    except (OSError, subprocess.CalledProcessError):
        return {'head': None, 'dirty': None, 'status_sha256': None}


def harness_hashes() -> dict:
    return {p.name: hash_file(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def catalog_index(catalog: dict) -> set[tuple]:
    shape(catalog, {'schema_version', 'kind', 'provenance', 'references'}, 'catalog')
    require(catalog['schema_version'] == VERSION and type(catalog['schema_version']) is int, 'catalog version')
    require(catalog['kind'] in ('synthetic', 'source_snapshot'), 'catalog kind')
    require(isinstance(catalog['provenance'], dict) and bool(catalog['provenance']), 'catalog provenance missing')
    require(isinstance(catalog['references'], list) and bool(catalog['references']), 'catalog references missing')
    refs = [reference(r) for r in catalog['references']]
    require(len(set(refs)) == len(refs), 'duplicate catalog reference')
    require(all(r['edition'] is not None and r['printing'] is not None for r in catalog['references']),
            'catalog must identify edition and printing')
    return set(refs)


def validate_config(config: dict) -> None:
    shape(config, {'predictor', 'settings'}, 'config')
    p = shape(config['predictor'], {'name', 'git_commit', 'dirty', 'source_sha256'}, 'predictor provenance')
    require(nonempty(p['name']), 'predictor name missing')
    require(p['git_commit'] is None or (isinstance(p['git_commit'], str) and
            len(p['git_commit']) == 40 and all(c in '0123456789abcdef' for c in p['git_commit'])), 'predictor git commit')
    require(p['dirty'] is None or type(p['dirty']) is bool, 'predictor dirty status')
    require(p['source_sha256'] is None or is_hash(p['source_sha256']), 'predictor source hash')
    require(isinstance(config['settings'], dict), 'predictor settings must be an object')


def _normalized(value: str) -> str:
    return ' '.join(value.casefold().split())


def _inspect_cases(cases: list, root: Path, *, sealed: bool) -> list[dict]:
    require(isinstance(cases, list) and bool(cases), 'no planned cases')
    ids, tokens, answer_files, input_files = set(), {}, set(), set()
    out = []
    for case in cases:
        shape(case, CASE_FIELDS | ({'content_sha256', 'input_payload_sha256'} if sealed else set()), 'case')
        cid = case['case_id']
        require(nonempty(cid) and cid not in ids, 'empty or duplicate case id')
        ids.add(cid)
        require(case['split'] in SPLITS, f'{cid}: invalid split')
        groups = case['groups']
        require(isinstance(groups, list) and bool(groups) and all(nonempty(g) for g in groups), f'{cid}: groups missing')
        require(len(set(groups)) == len(groups), f'{cid}: duplicate group')
        review = shape(case['leakage_review'], {'status', 'reviewer', 'evidence'}, 'leakage review')
        require(review['status'] in ('unreviewed', 'cleared', 'contains_outcome'), 'leakage review status')
        require(review['reviewer'] is None or nonempty(review['reviewer']), 'leakage reviewer')
        require(isinstance(review['evidence'], list) and all(nonempty(e) for e in review['evidence']), 'leakage evidence')
        if review['status'] == 'cleared':
            require(nonempty(review['reviewer']) and bool(review['evidence']), 'cleared input needs review evidence')
        if case['split'] == 'holdout':
            require(review['status'] == 'cleared', f'{cid}: holdout input leakage review is not cleared')
        refs = {name: (case[name] if sealed else file_ref(root, case[name])) for name in ('input', 'answer')}
        for ref in refs.values():
            checked_ref(root, ref)
        inp = read_json(checked_ref(root, refs['input']))
        validate_input(inp, cid)
        attachments = []
        for a in inp['attachments']:
            ref = {'path': a['path'], 'sha256': a['sha256']}
            checked_ref(root, ref)
            attachments.append(a['sha256'])
            input_files.add((child(root, a['path']), a['sha256']))
        input_files.add((child(root, refs['input']['path']), refs['input']['sha256']))
        answer_files.add((child(root, refs['answer']['path']), refs['answer']['sha256']))
        content_hash = fingerprint({'narrative': _normalized(inp['narrative']),
                                    'facts': sorted((_normalized(f['field']), _normalized(f['value'])) for f in inp['facts']),
                                    'attachments': sorted(attachments)})
        if sealed:
            require(case['content_sha256'] == content_hash, f'{cid}: content fingerprint changed')
            require(case['input_payload_sha256'] == fingerprint(inp), f'{cid}: input payload fingerprint changed')
        identities = [('group', g) for g in groups] + [('content', content_hash),
                      ('narrative', fingerprint(_normalized(inp['narrative'])))] + [('attachment', h) for h in attachments]
        for identity in identities:
            prior = tokens.setdefault(identity, (case['split'], cid))
            require(prior[0] == case['split'], f'{cid}: cross-split leakage ({identity[0]}) with {prior[1]}')
        out.append({**case, **refs, 'content_sha256': content_hash, 'input_payload_sha256': fingerprint(inp)})
    require(not ({p for p, _ in input_files} & {p for p, _ in answer_files}), 'answer file is an input')
    require(not ({h for _, h in input_files} & {h for _, h in answer_files}), 'answer bytes are an input')
    return out


def seal(plan_path: Path, out: Path) -> dict:
    require(plan_path.parent.resolve() == out.parent.resolve(), 'plan and manifest must share a bundle root')
    plan = read_json(plan_path)
    shape(plan, {'schema_version', 'dataset_id', 'catalog', 'config', 'cases'}, 'plan')
    require(plan['schema_version'] == VERSION and type(plan['schema_version']) is int, 'plan version')
    require(nonempty(plan['dataset_id']), 'dataset id missing')
    root = plan_path.parent
    catalog, config = file_ref(root, plan['catalog']), file_ref(root, plan['config'])
    catalog_index(read_json(checked_ref(root, catalog)))
    validate_config(read_json(checked_ref(root, config)))
    cases = _inspect_cases(plan['cases'], root, sealed=False)
    plan_hash = hash_file(plan_path)
    for case in cases:
        inp = read_json(checked_ref(root, case['input']))
        require(case['input']['sha256'] != plan_hash and
                all(a['sha256'] != plan_hash for a in inp['attachments']), 'private dataset plan reused as predictor input')
    key_hashes = {c['answer']['sha256'] for c in cases}
    require(not key_hashes & {catalog['sha256'], config['sha256']}, 'answer reused as catalog/config')
    payload = {'schema_version': VERSION, 'dataset_id': plan['dataset_id'], 'catalog': catalog,
               'config': config, 'cases': cases, 'git': git_state(root), 'harness': harness_hashes()}
    result = {**payload, 'seal_sha256': fingerprint(payload)}
    write_json(out, result)
    return result


def verify(manifest_path: Path) -> dict:
    m = read_json(manifest_path)
    shape(m, {'schema_version', 'dataset_id', 'catalog', 'config', 'cases', 'git', 'harness', 'seal_sha256'}, 'manifest')
    require(m['schema_version'] == VERSION and type(m['schema_version']) is int, 'manifest version')
    require(fingerprint({k: v for k, v in m.items() if k != 'seal_sha256'}) == m['seal_sha256'], 'manifest seal changed')
    root = manifest_path.parent
    catalog_index(read_json(checked_ref(root, m['catalog'])))
    validate_config(read_json(checked_ref(root, m['config'])))
    _inspect_cases(m['cases'], root, sealed=True)
    require(not {c['answer']['sha256'] for c in m['cases']} & {m['catalog']['sha256'], m['config']['sha256']},
            'answer reused as catalog/config')
    return m


def selected(m: dict, split: str) -> list[dict]:
    require(split in SPLITS, 'invalid split')
    cases = [c for c in m['cases'] if c['split'] == split]
    require(bool(cases), 'selected split has no planned cases')
    return cases


def bindings(m: dict, case: dict, run_id: str) -> dict:
    return {'schema_version': VERSION, 'run_id': run_id, 'case_id': case['case_id'],
            'manifest_sha256': m['seal_sha256'], 'input_sha256': case['input']['sha256'],
            'input_payload_sha256': case['input_payload_sha256'],
            'config_sha256': m['config']['sha256'], 'catalog_sha256': m['catalog']['sha256']}


def export_inputs(manifest_path: Path, split: str, run_id: str, out: Path) -> dict:
    require(nonempty(run_id), 'run id missing')
    m = verify(manifest_path)
    cases = selected(m, split)
    root = manifest_path.parent
    packets, attachments = [], {}
    for case in cases:
        inp = read_json(checked_ref(root, case['input']))
        packet = {**bindings(m, case, run_id), 'input': inp}
        validate_request(packet)
        packets.append(packet)
        for a in inp['attachments']:
            attachments[a['path']] = a['sha256']
    reserved = {'requests.jsonl', 'predictor-config.json', 'source-catalog.json'}
    require(not reserved & set(attachments), 'attachment uses reserved export name')
    require(not out.exists(), 'export directory already exists; use a new run directory')
    out.mkdir(parents=True)
    for name, sha in attachments.items():
        src = checked_ref(root, {'path': name, 'sha256': sha})
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        require(target.resolve().is_relative_to(out.resolve()), 'export attachment path escapes bundle')
        with src.open('rb') as source, target.open('xb') as dest:
            shutil.copyfileobj(source, dest)
    for name, ref in (('predictor-config.json', m['config']), ('source-catalog.json', m['catalog'])):
        with checked_ref(root, ref).open('rb') as source, (out / name).open('xb') as dest:
            shutil.copyfileobj(source, dest)
    with (out / 'requests.jsonl').open('x', encoding='utf-8') as stream:
        for p in packets:
            stream.write(canonical(p).decode() + '\n')
    return {'planned_cases': len(cases), 'requests_sha256': hash_file(out / 'requests.jsonl'),
            'run_id': run_id, 'provider_calls': 0}


def snapshot_catalog(db: Path) -> dict:
    """Export identities only from the real codedb schema, with WAL-aware provenance."""
    require(db.is_file(), 'codedb database missing')
    def hashes():
        return {label: hash_file(p) if p.exists() else None
                for label, p in (('database', db), ('wal', Path(str(db) + '-wal')))}
    before = hashes()
    with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        con.execute('begin')
        doc = con.execute("select label, sha256 from docs where doc='NBC-AE' and kind='code' and citable=1").fetchone()
        require(doc is not None and doc[0] == 'NBC(AE) 2023 p2' and is_hash(doc[1]), 'unsupported codedb edition or schema')
        refs = [{'document': 'NBC-AE', 'edition': '2023', 'printing': '2nd', 'division': division, 'provision': provision}
                for division, provision in con.execute("select division,id from provisions where doc='NBC-AE' "
                                                       "and division in ('A','B','C') order by division,sort_key")]
        require({r['division'] for r in refs} == {'A', 'B', 'C'}, 'codedb missing divisions')
    require(before == hashes(), 'codedb changed during snapshot; retry on a stable copy')
    result = {'schema_version': VERSION, 'kind': 'source_snapshot',
              'provenance': {'label': doc[0], 'source_text_sha256': doc[1], 'corpus_files': before,
                             'git': git_state(db.parent)}, 'references': refs}
    catalog_index(result)
    return result
