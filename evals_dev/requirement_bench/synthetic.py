"""Generate clearly synthetic fixtures, export them, and score offline captures.

Fixture authoring and prediction are separate steps. No historical or real keys
are imported. These fixtures establish harness behavior, never expert accuracy.
"""
from __future__ import annotations

from pathlib import Path

from .example_predictor import capture
from .manifest import export_inputs, git_state, seal
from .protocol import (canonical, digest_bytes, hash_file, loads, read_json,
                       require, write_json)
from .score import DIMENSIONS, evaluate, key_template


def create_fixture(out: Path) -> None:
    require(not out.exists(), 'synthetic fixture directory exists')
    out.mkdir(parents=True)
    refs = [{'document': 'SYNTHETIC-TEST-CODE', 'edition': 'fixture-v1', 'printing': 'test-only',
             'division': d, 'provision': p}
            for d, p in [('A', 'scope'), ('B', 'primary'), ('B', 'supporting'), ('B', 'late'), ('C', 'admin')]]
    write_json(out / 'catalog.json', {'schema_version': 1, 'kind': 'synthetic',
                                     'provenance': {'notice': 'Invented test symbols, never real provisions.'}, 'references': refs})
    git = git_state(Path(__file__).parent)
    write_json(out / 'config.json', {'predictor': {'name': 'synthetic marker reader (test only)',
                                                 'git_commit': git['head'],
                                                 'dirty': git['dirty'], 'source_sha256': hash_file(Path(__file__).with_name('example_predictor.py'))},
                                     'settings': {'synthetic': True, 'visible_count': 2}})
    texts = {
        'synthetic-late': ('Synthetic example: fixture:scope fixture:primary fixture:supporting fixture:admin. '
                           + 'Background without a deciding requirement. ' * 300 + '\nFinal deciding text: fixture:late'),
        'synthetic-external': 'Synthetic other-standard example: fixture:primary fixture:external.',
        'synthetic-unknown': 'Synthetic unlabeled example. Requirement coverage has not been reviewed.',
    }
    cases = []
    for cid, text in texts.items():
        write_json(out / f'{cid}.input.json', {'schema_version': 1, 'case_id': cid, 'narrative': text, 'facts': [], 'attachments': []})
        key = key_template(cid)
        key['origin'] = 'synthetic'
        key['coverage']['limitations'] = ['Synthetic harness regression only; no real requirement or expert judgment.']
        wanted = refs if cid == 'synthetic-late' else refs[1:2] if cid == 'synthetic-external' else []
        key['requirements'] = [{'id': r['provision'], 'role': ('administrative' if r['division'] == 'C' else
                                  'scope' if r['division'] == 'A' else 'supporting' if r['provision'] == 'supporting' else 'primary'),
                                'reference': r, 'support': 'catalogued',
                                'provenance': [{'source': 'synthetic fixture definition', 'locator': r['provision'],
                                                'sha256': digest_bytes(b'synthetic fixture, not expert gold')}]}
                               for r in wanted]
        if cid == 'synthetic-late':
            key['coverage'].update(status='exhaustive', dimensions={d: 'reviewed' for d in DIMENSIONS})
        if cid == 'synthetic-external':
            key['coverage']['status'] = 'minimum'
            key['requirements'].append({'id': 'external', 'role': 'supporting', 'support': 'unsupported',
                                        'reference': {'document': 'SYNTHETIC-EXTERNAL-STANDARD', 'edition': None,
                                                      'printing': None, 'division': None, 'provision': 'fixture-external-review'},
                                        'provenance': [{'source': 'synthetic fixture definition', 'locator': 'external',
                                                        'sha256': digest_bytes(b'synthetic external fixture')}]})
        write_json(out / f'{cid}.answer.json', key)
        cases.append({'case_id': cid, 'split': 'holdout', 'groups': [cid], 'input': f'{cid}.input.json',
                      'answer': f'{cid}.answer.json', 'leakage_review': {'status': 'cleared', 'reviewer': 'synthetic author',
                       'evidence': ['Synthetic inputs authored separately from the answer files; harness tests only.']}})
    write_json(out / 'plan.json', {'schema_version': 1, 'dataset_id': 'synthetic-requirement-regressions-v1',
                                  'catalog': 'catalog.json', 'config': 'config.json', 'cases': cases})


def run_demo(out: Path) -> dict:
    create_fixture(out)
    seal(out / 'plan.json', out / 'manifest.json')
    export_inputs(out / 'manifest.json', 'holdout', 'synthetic-demo', out / 'predictor-inputs')
    predictor = out / 'predictor-inputs'
    config = read_json(predictor / 'predictor-config.json')
    catalog = read_json(predictor / 'source-catalog.json')
    captures = out / 'captured'
    captures.mkdir()
    requests = [loads(line) for line in (predictor / 'requests.jsonl').read_text().splitlines()]
    with (captures / 'predictions.jsonl').open('x', encoding='utf-8') as stream:
        for request in requests:
            stream.write(canonical(capture(request, config, catalog, captures, input_root=predictor)).decode() + '\n')
    result = evaluate(out / 'manifest.json', captures / 'predictions.jsonl', 'holdout', 'synthetic-demo')
    write_json(out / 'report.json', result)
    return result
