"""Synthetic marker reader demonstrating the input-only seam; no real code inference.

This module imports only the predictor protocol. It does not receive a manifest,
key path, split, group, coverage label, or reviewer metadata.
"""
from __future__ import annotations

import time
import shutil
from pathlib import Path

from .protocol import (LAYERS, checked_ref, file_ref, fingerprint, read_json, require,
                       validate_request, write_json)


def capture(request: dict, config: dict, catalog: dict, out: Path, *, input_root: Path) -> dict:
    start = time.perf_counter()
    validate_request(request)
    observed = {}
    for name, filename, payload in (('config', 'predictor-config.json', config),
                                    ('catalog', 'source-catalog.json', catalog)):
        src_ref = {'path': filename, 'sha256': request[name + '_sha256']}
        src = checked_ref(input_root, src_ref)
        require(fingerprint(read_json(src)) == fingerprint(payload), f'loaded {name} differs from observed artifact')
        target = f'observed-{name}-{src_ref["sha256"]}.json'
        if not (out / target).exists():
            with src.open('rb') as source, (out / target).open('xb') as dest:
                shutil.copyfileobj(source, dest)
        observed[name] = file_ref(out, target)
        require(observed[name]['sha256'] == src_ref['sha256'], f'observed {name} copy changed')
    observed['attachments'] = []
    for attachment in request['input']['attachments']:
        src = checked_ref(input_root, {'path': attachment['path'], 'sha256': attachment['sha256']})
        target = f'observed-attachment-{attachment["sha256"]}'
        if not (out / target).exists():
            with src.open('rb') as source, (out / target).open('xb') as dest:
                shutil.copyfileobj(source, dest)
        ref = file_ref(out, target)
        require(ref['sha256'] == attachment['sha256'], 'observed attachment copy changed')
        observed['attachments'].append(ref)
    request_file = f'observed-request-{request["input_sha256"]}.json'
    write_json(out / request_file, request)
    observed['request'] = file_ref(out, request_file)
    require(config['settings'].get('synthetic') is True, 'example predictor only accepts synthetic fixtures')
    require(catalog['kind'] == 'synthetic', 'example predictor cannot run on a real code catalog')
    text = request['input']['narrative']
    items = [{'reference': ref, 'resolution': 'resolved', 'reason': None}
             for ref in catalog['references'] if f"fixture:{ref['provision']}" in text]
    if 'fixture:external' in text:
        items.append({'reference': {'document': 'SYNTHETIC-EXTERNAL-STANDARD', 'edition': None,
                                   'printing': None, 'division': None, 'provision': 'fixture-external-review'},
                      'resolution': 'unresolved', 'reason': 'Synthetic standard is outside this fixture catalog.'})
    binding = {k: v for k, v in request.items() if k != 'input'}
    # These are simulated captures. Real adapters must supply observed per-layer raw evidence.
    included = items[:max(0, len(items) - 1)]
    sets = (items, items, included, included[:config['settings']['visible_count']])
    evidence = {**binding, 'kind': 'synthetic',
                'layers': {name: {'items': entries, 'raw_artifacts': []} for name, entries in zip(LAYERS, sets)}}
    filename = f'capture-{request["input_sha256"]}.json'
    write_json(out / filename, evidence)
    ref = file_ref(out, filename)
    return {**binding, 'status': 'ok', 'error': None,
            'elapsed_ms': round((time.perf_counter() - start) * 1000, 3), 'requests': [],
            'observed_inputs': observed,
            'layers': {name: ref for name in LAYERS}}
