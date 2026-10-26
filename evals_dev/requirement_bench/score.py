"""Answer-side scoring and conservative accounting for captured, offline predictions."""
from __future__ import annotations

import math
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .manifest import (bindings, catalog_index, git_state, harness_hashes, selected, verify)
from .protocol import (LAYERS, VERSION, Invalid, checked_ref, hash_file, is_hash, loads,
                       nonempty, number, read_json, reference, require, shape, validate_request)

ROLES = ('primary', 'supporting', 'administrative', 'scope')
DIMENSIONS = ('A', 'B', 'C', 'other')
REQUEST_FIELDS = {'request_id', 'provider', 'model', 'status', 'input_tokens', 'output_tokens',
                  'cost_usd', 'latency_ms', 'error'}


def key_template(case_id: str) -> dict:
    return {'schema_version': VERSION, 'case_id': case_id, 'origin': 'real',
            'coverage': {'status': 'unknown', 'dimensions': {d: 'unreviewed' for d in DIMENSIONS},
                         'limitations': ['No expert-verified requirement set supplied.']},
            'review': {'status': 'unreviewed', 'reviewer': None, 'qualifications': None,
                       'reviewed_at': None, 'evidence': []}, 'requirements': []}


def _provenance(entries: list, *, verified=False) -> None:
    require(isinstance(entries, list), 'provenance must be a list')
    for entry in entries:
        shape(entry, {'source', 'locator', 'sha256'}, 'source provenance')
        require(nonempty(entry['source']) and nonempty(entry['locator']), 'source/locator missing')
        require(is_hash(entry['sha256']) or (entry['sha256'] is None and not verified), 'source hash missing/invalid')


def load_key(path: Path, case_id: str, catalog: set[tuple], catalog_kind: str) -> dict:
    key = read_json(path)
    shape(key, {'schema_version', 'case_id', 'origin', 'coverage', 'review', 'requirements'}, 'answer key')
    require(type(key['schema_version']) is int and key['schema_version'] == VERSION, 'key version')
    require(key['case_id'] == case_id, 'answer key case id mismatch')
    require(key['origin'] in ('real', 'synthetic'), 'key origin')
    require(key['origin'] == 'synthetic' or catalog_kind != 'synthetic', 'real key cannot use synthetic catalog')
    coverage = shape(key['coverage'], {'status', 'dimensions', 'limitations'}, 'key coverage')
    require(coverage['status'] in ('unknown', 'minimum', 'exhaustive'), 'key coverage status')
    shape(coverage['dimensions'], set(DIMENSIONS), 'key coverage dimensions')
    require(all(s in ('unreviewed', 'reviewed') for s in coverage['dimensions'].values()), 'dimension status')
    require(isinstance(coverage['limitations'], list) and all(nonempty(s) for s in coverage['limitations']), 'key limitations')
    if coverage['status'] == 'exhaustive':
        require(all(s == 'reviewed' for s in coverage['dimensions'].values()), 'exhaustive key has unreviewed dimensions')
    review = shape(key['review'], {'status', 'reviewer', 'qualifications', 'reviewed_at', 'evidence'}, 'key review')
    require(review['status'] in ('unreviewed', 'provisional', 'expert_verified'), 'key review status')
    for field in ('reviewer', 'qualifications', 'reviewed_at'):
        require(review[field] is None or nonempty(review[field]), f'invalid review {field}')
    expert = review['status'] == 'expert_verified'
    require(not (expert and key['origin'] == 'synthetic'), 'synthetic tests are never expert gold')
    _provenance(review['evidence'], verified=expert)
    if expert:
        require(all(nonempty(review[f]) for f in ('reviewer', 'qualifications', 'reviewed_at')) and bool(review['evidence']),
                'expert review requires identity, qualifications, timestamp and evidence')
        try:
            stamp = datetime.fromisoformat(review['reviewed_at'].replace('Z', '+00:00'))
            require(stamp.tzinfo is not None, 'expert review timestamp needs timezone')
        except ValueError as error:
            raise Invalid('invalid expert review timestamp') from error
    require(isinstance(key['requirements'], list), 'requirements must be a list')
    ids, refs = set(), set()
    for req in key['requirements']:
        shape(req, {'id', 'role', 'reference', 'support', 'provenance'}, 'key requirement')
        require(nonempty(req['id']) and req['id'] not in ids, 'empty/duplicate requirement id')
        ids.add(req['id'])
        ref = reference(req['reference'])
        require(ref not in refs, 'duplicate requirement reference; annotate at a distinct source locator')
        refs.add(ref)
        require(req['role'] in ROLES, 'requirement role')
        require(req['support'] in ('catalogued', 'unsupported'), 'requirement support')
        require((ref in catalog) == (req['support'] == 'catalogued'), 'key reference disagrees with sealed source catalog')
        _provenance(req['provenance'], verified=expert)
        require(bool(req['provenance']), 'requirement provenance missing')
    return key


def _requests(value) -> list[dict]:
    require(isinstance(value, list), 'provider requests must be a list, including failed dispatches')
    ids = set()
    for req in value:
        shape(req, REQUEST_FIELDS, 'provider request')
        require(nonempty(req['request_id']) and req['request_id'] not in ids, 'duplicate/empty request id')
        ids.add(req['request_id'])
        require(nonempty(req['provider']) and (req['model'] is None or nonempty(req['model'])), 'provider/model missing')
        require(req['status'] in ('ok', 'error'), 'request status')
        require(req['error'] is None or nonempty(req['error']), 'request error')
        require((req['status'] == 'error') == nonempty(req['error']), 'request status/error disagree')
        require(all(number(req[k], integer=True) for k in ('input_tokens', 'output_tokens')), 'request tokens invalid')
        require(all(number(req[k]) for k in ('cost_usd', 'latency_ms')), 'request cost/latency invalid')
    return value


def _capture_records(path: Path) -> tuple[list[dict], list[dict]]:
    records, errors = [], []
    for line_no, line in enumerate(path.read_bytes().splitlines(), 1):
        try:
            obj = loads(line.decode('utf-8'))
            require(isinstance(obj, dict), 'prediction must be an object')
            records.append({'line': line_no, 'record': obj})
        except (Invalid, UnicodeError) as error:
            errors.append({'line': line_no, 'error': str(error)})
    return records, errors


def _observed_inputs(value: dict, root: Path, expected: dict) -> dict:
    """Check retained predictor-side artifacts, rather than only claimed hashes."""
    shape(value, {'request', 'config', 'catalog', 'attachments'}, 'observed inputs')
    packet = read_json(checked_ref(root, value['request']))
    validate_request(packet)
    require(all(packet[k] == v for k, v in expected.items()), 'observed request has stale or foreign bindings')
    for field in ('config', 'catalog'):
        checked_ref(root, value[field])
        require(value[field]['sha256'] == expected[field + '_sha256'], f'observed {field} hash changed')
    require(isinstance(value['attachments'], list), 'observed attachments must be a list')
    for ref in value['attachments']:
        checked_ref(root, ref)
    require(Counter(ref['sha256'] for ref in value['attachments']) ==
            Counter(a['sha256'] for a in packet['input']['attachments']), 'observed input attachments differ')
    return value


def _layer(ref: dict, name: str, root: Path, expected: dict, key: dict, catalog: set[tuple], answer_hashes: set[str]) -> dict:
    path = checked_ref(root, ref)
    require(ref['sha256'] not in answer_hashes, 'answer key reused as evidence')
    evidence = read_json(path)
    shape(evidence, set(expected) | {'kind', 'layers'}, 'evidence capture')
    require(type(evidence['schema_version']) is int, 'evidence version')
    require(all(evidence[k] == v for k, v in expected.items()), 'evidence has stale or foreign bindings')
    require(evidence['kind'] in ('synthetic', 'captured'), 'evidence kind')
    require(key['origin'] == 'synthetic' or evidence['kind'] == 'captured', 'synthetic evidence for real case')
    require(isinstance(evidence['layers'], dict) and set(evidence['layers']) <= set(LAYERS), 'evidence layers')
    stage = shape(evidence['layers'].get(name), {'items', 'raw_artifacts'}, f'{name} capture')
    require(isinstance(stage['raw_artifacts'], list), 'raw artifacts must be a list')
    if evidence['kind'] == 'captured':
        require(bool(stage['raw_artifacts']), 'real capture needs raw evidence for this layer')
    for raw in stage['raw_artifacts']:
        checked_ref(root, raw)
        require(raw['sha256'] not in answer_hashes, 'answer key reused as raw evidence')
    require(isinstance(stage['items'], list), 'captured items must be a list')
    resolved, unresolved, seen = set(), set(), set()
    for item in stage['items']:
        shape(item, {'reference', 'resolution', 'reason'}, 'predicted requirement')
        identity = reference(item['reference'])
        require(identity not in seen, 'duplicate predicted reference')
        seen.add(identity)
        require(item['resolution'] in ('resolved', 'unresolved'), 'prediction resolution')
        require(item['reason'] is None or nonempty(item['reason']), 'prediction reason')
        if item['resolution'] == 'resolved':
            require(identity in catalog, 'resolved citation absent from catalog (wrong edition or invented citation)')
            resolved.add(identity)
        else:
            require(nonempty(item['reason']), 'unresolved requirement needs a reason')
            unresolved.add(identity)
    supported = {reference(r['reference']): r['id'] for r in key['requirements'] if r['support'] == 'catalogued'}
    unsupported = {reference(r['reference']): r['id'] for r in key['requirements'] if r['support'] == 'unsupported'}
    return {'status': 'ok', 'errors': [], 'observed_items': len(seen),
            'evidence': ref, 'raw_artifacts': stage['raw_artifacts'],
            'matched': sorted(supported[r] for r in resolved & supported.keys()),
            'unresolved_detected': sorted(unsupported[r] for r in unresolved & unsupported.keys()),
            'extra_items': len(seen - (supported.keys() | unsupported.keys())),
            'resolved_items': len(resolved), 'unresolved_items': len(unresolved)}


def _failed_layer(status: str, message: str | None = None) -> dict:
    return {'status': status, 'errors': [message] if message else [], 'observed_items': None,
            'evidence': None, 'raw_artifacts': [],
            'matched': [], 'unresolved_detected': [], 'extra_items': 0, 'resolved_items': 0, 'unresolved_items': 0}


def _ratio(n: int, d: int) -> dict:
    return {'numerator': n, 'denominator': d, 'rate': n / d if d else None}


def _complete(key: dict) -> bool:
    return (key['coverage']['status'] == 'exhaustive' and bool(key['requirements'])
            and all(r['support'] == 'catalogued' for r in key['requirements']))


def _aggregate(rows: list[dict], keys: dict[str, dict]) -> dict:
    out = {'planned_cases': len(rows), 'prediction_status_counts': dict(Counter(r['prediction_status'] for r in rows)),
           'key_coverage_counts': dict(Counter(keys[r['case_id']]['coverage']['status'] for r in rows)), 'layers': {}}
    for name in LAYERS:
        known = matched = supported = unresolved = unresolved_hits = any_hit = all_hit = accounted = exact = 0
        observed = eligible = precision_n = precision_d = 0
        dimensions = {d: [0, 0] for d in DIMENSIONS}
        roles = {role: [0, 0] for role in ROLES}
        statuses = Counter()
        for row in rows:
            key = keys[row['case_id']]
            requirements = key['requirements']
            layer = row['layers'][name]
            hits, pending = set(layer['matched']), set(layer['unresolved_detected'])
            statuses[layer['status']] += 1
            observed += layer['status'] == 'ok'
            known += len(requirements)
            matched += len(hits)
            supported += sum(r['support'] == 'catalogued' for r in requirements)
            unresolved += sum(r['support'] == 'unsupported' for r in requirements)
            unresolved_hits += len(pending)
            any_hit += bool(hits)
            all_hit += bool(requirements) and len(hits) == len(requirements)
            accounted += bool(requirements) and len(hits | pending) == len(requirements)
            if _complete(key):
                eligible += 1
                exact += (layer['status'] == 'ok' and len(hits) == len(requirements)
                          and layer['observed_items'] == len(requirements))
                precision_n += len(hits)
                precision_d += layer['observed_items'] or 0
            for req in requirements:
                d = req['reference']['division'] or 'other'
                dimensions[d][0] += req['id'] in hits
                dimensions[d][1] += 1
                roles[req['role']][0] += req['id'] in hits
                roles[req['role']][1] += 1
        out['layers'][name] = {
            'observed_valid_captures': observed, 'status_counts': dict(statuses),
            'known_requirement_recall': _ratio(matched, known),
            'supported_requirement_recall': _ratio(matched, supported),
            'any_hit_diagnostic': _ratio(any_hit, len(rows)),
            'all_known_requirements_recalled': _ratio(all_hit, len(rows)),
            'all_known_accounted_for_diagnostic': _ratio(accounted, len(rows)),
            'unsupported_requirements_explicitly_unresolved': _ratio(unresolved_hits, unresolved),
            'declared_exhaustive_exact_set_match': _ratio(exact, eligible),
            'precision_on_declared_exhaustive_keys': _ratio(precision_n, precision_d),
            'recall_by_division': {d: _ratio(*counts) for d, counts in dimensions.items()},
            'recall_by_role': {role: _ratio(*counts) for role, counts in roles.items()},
        }
    return out


def _accounting(records: list[dict], malformed: list[dict], missing: int) -> dict:
    requests, latencies, errors = [], [], []
    unknown_attempts = len(malformed) + missing
    for entry in records:
        r = entry['record']
        if number(r.get('elapsed_ms')) and r.get('elapsed_ms') is not None:
            latencies.append(r['elapsed_ms'])
        else:
            errors.append({'line': entry['line'], 'error': 'unknown or invalid attempt latency'})
        if not isinstance(r.get('requests'), list):
            unknown_attempts += 1
            errors.append({'line': entry['line'], 'error': 'unknown request ledger'})
            continue
        for req in r['requests']:
            try:
                requests.extend(_requests([req]))
            except Invalid as error:
                unknown_attempts += 1
                errors.append({'line': entry['line'], 'error': str(error)})
    counts = Counter(r['request_id'] for r in requests)
    duplicates = sorted(k for k, n in counts.items() if n > 1)
    complete = not unknown_attempts and not duplicates
    def subtotal(values):
        total = sum(values)
        return total if number(total) else None
    def total(field):
        values = [r[field] for r in requests]
        return subtotal(values) if complete and all(v is not None for v in values) else None
    sorted_latency = sorted(latencies)
    return {'scope': 'All captured attempt records, including failed, duplicate and unplanned predictions; self-reported usage.',
            'attempt_records': len(records), 'unparseable_records': len(malformed), 'missing_planned_predictions': missing,
            'unknown_usage_attempts': unknown_attempts, 'request_records': len(requests),
            'provider_requests': len(requests) if complete else None,
            'failed_provider_request_records': sum(r['status'] == 'error' for r in requests),
            'duplicate_request_ids': duplicates, 'cost_usd': total('cost_usd'),
            'reported_cost_usd_subtotal': subtotal(r['cost_usd'] for r in requests if r['cost_usd'] is not None),
            'unknown_cost_request_records': sum(r['cost_usd'] is None for r in requests),
            'input_tokens': total('input_tokens'), 'output_tokens': total('output_tokens'),
            'known_input_tokens_subtotal': subtotal(r['input_tokens'] for r in requests if r['input_tokens'] is not None),
            'known_output_tokens_subtotal': subtotal(r['output_tokens'] for r in requests if r['output_tokens'] is not None),
            'requests': requests, 'errors': errors,
            'latency_ms': {'scope': 'Captured end-to-end attempt latency, failures included; no performance comparison.',
                           'samples': len(latencies), 'unknown_attempts': len(records) - len(latencies) + len(malformed) + missing,
                           'median': (statistics.median_low(latencies) / 2 + statistics.median_high(latencies) / 2) if latencies else None,
                           'p95_nearest_rank': sorted_latency[math.ceil(.95 * len(latencies)) - 1] if latencies else None,
                           'minimum': min(latencies) if latencies else None, 'maximum': max(latencies) if latencies else None}}


def evaluate(manifest_path: Path, predictions_path: Path, split: str, run_id: str) -> dict:
    start = time.perf_counter()
    require(nonempty(run_id), 'run id missing')
    m = verify(manifest_path)
    cases = selected(m, split)
    catalog_doc = read_json(checked_ref(manifest_path.parent, m['catalog']))
    catalog = catalog_index(catalog_doc)
    keys = {c['case_id']: load_key(checked_ref(manifest_path.parent, c['answer']), c['case_id'], catalog, catalog_doc['kind'])
            for c in cases}
    records, malformed = _capture_records(predictions_path)
    by_id = defaultdict(list)
    unplanned = []
    for entry in records:
        cid = entry['record'].get('case_id')
        if isinstance(cid, str) and cid in keys:
            by_id[cid].append(entry['record'])
        else:
            unplanned.append({'line': entry['line'], 'error': 'unknown or unselected case id'})
    root = predictions_path.parent
    rows = []
    answer_hashes = {c['answer']['sha256'] for c in m['cases']}
    for case in cases:
        cid = case['case_id']
        row = {'case_id': cid, 'prediction_status': 'ok', 'errors': [], 'observed_inputs': None, 'layers': {}}
        found = by_id[cid]
        pred = found[0] if len(found) == 1 else None
        if not found:
            row['prediction_status'] = 'missing'
        elif len(found) > 1:
            row['prediction_status'] = 'duplicate'
        else:
            expected = bindings(m, case, run_id)
            try:
                shape(pred, set(expected) | {'status', 'error', 'elapsed_ms', 'requests', 'layers', 'observed_inputs'}, 'prediction')
                require(type(pred['schema_version']) is int, 'prediction version')
                require(all(pred[k] == v for k, v in expected.items()), 'prediction has stale or foreign bindings')
                require(pred['status'] in ('ok', 'error'), 'prediction status')
                require(pred['error'] is None or nonempty(pred['error']), 'prediction error')
                require((pred['status'] == 'error') == nonempty(pred['error']), 'prediction status/error disagree')
                require(number(pred['elapsed_ms']), 'prediction latency invalid')
                _requests(pred['requests'])
                shape(pred['layers'], set(LAYERS), 'prediction layers')
                if pred['status'] == 'error':
                    row['prediction_status'] = 'error'
                    row['errors'].append(pred['error'])
                else:
                    row['observed_inputs'] = _observed_inputs(pred['observed_inputs'], root, expected)
            except (Invalid, OSError) as error:
                row['prediction_status'] = 'invalid'
                row['errors'].append(str(error))
        for name in LAYERS:
            if row['prediction_status'] != 'ok':
                row['layers'][name] = _failed_layer(row['prediction_status'])
            elif pred['layers'][name] is None:
                row['layers'][name] = _failed_layer('not_supplied')
            else:
                try:
                    row['layers'][name] = _layer(pred['layers'][name], name, root, bindings(m, case, run_id),
                                                keys[cid], catalog, answer_hashes)
                except (Invalid, OSError) as error:
                    row['layers'][name] = _failed_layer('invalid', str(error))
                    row['layers'][name]['evidence'] = pred['layers'][name]
            row['layers'][name]['missing_known'] = sorted(
                req['id'] for req in keys[cid]['requirements'] if req['id'] not in row['layers'][name]['matched'])
        rows.append(row)
    cases_by_id = {c['case_id']: c for c in cases}
    expert_rows = [r for r in rows if keys[r['case_id']]['origin'] == 'real'
                   and keys[r['case_id']]['review']['status'] == 'expert_verified' and _complete(keys[r['case_id']])
                   and cases_by_id[r['case_id']]['leakage_review']['status'] == 'cleared']
    cohorts = defaultdict(list)
    for row in rows:
        key = keys[row['case_id']]
        cohorts[key['origin'] + '/' + key['review']['status']].append(row)
    accounting = _accounting(records, malformed, sum(not by_id[c['case_id']] for c in cases))
    integrity = not malformed and not unplanned and not accounting['duplicate_request_ids']
    return {'schema_version': VERSION,
            'scope': 'Requirement-reference coverage on supplied keys and layer captures; no safety, equivalence or compliance determination.',
            'run_id': run_id, 'split': split, 'capture_integrity_valid': integrity,
            'capture_errors': malformed + unplanned,
            'provenance': {'manifest_sha256': m['seal_sha256'], 'manifest_file_sha256': hash_file(manifest_path),
                           'predictions_sha256': hash_file(predictions_path), 'dataset_id': m['dataset_id'],
                           'catalog': m['catalog'], 'catalog_provenance': catalog_doc['provenance'], 'config': m['config'],
                           'predictor': read_json(checked_ref(manifest_path.parent, m['config']))['predictor'],
                           'seal_git': m['git'], 'scoring_git': git_state(Path(__file__).parent),
                           'seal_harness': m['harness'], 'scoring_harness': harness_hashes(),
                           'cases': [{k: c[k] for k in ('case_id', 'split', 'groups', 'content_sha256', 'input_payload_sha256',
                                                       'input', 'answer', 'leakage_review')}
                                     for c in cases],
                           'keys': {cid: {'origin': k['origin'], 'coverage': k['coverage'], 'review': k['review']}
                                    for cid, k in keys.items()}},
            'diagnostics_all_planned': _aggregate(rows, keys),
            'cohorts': {name: _aggregate(members, keys) for name, members in cohorts.items()},
            'expert_headline': {'eligible_cases': len(expert_rows), 'total_planned_cases': len(rows),
                                'metrics': _aggregate(expert_rows, keys) if expert_rows and integrity else None,
                                'whole_planned_set_eligible': bool(expert_rows) and len(expert_rows) == len(rows) and integrity,
                                'reason': 'Only real, nonempty, expert-verified exhaustive keys with all dimensions reviewed, '
                                          'catalogued requirements and cleared input leakage review qualify. '
                                          'Synthetic/provisional/minimum/unknown/unsupported cases do not. '
                                          'Expert status is supplied review evidence, not independently authenticated.'},
            'original_capture_accounting': accounting,
            'this_offline_evaluation': {'provider_requests': 0, 'cost_usd': 0,
                                        'scoring_elapsed_ms': round((time.perf_counter() - start) * 1000, 3)},
            'cases': rows}
