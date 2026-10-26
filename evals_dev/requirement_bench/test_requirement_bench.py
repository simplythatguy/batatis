"""Red-team harness regressions. All inputs, references and review identities are synthetic."""
from __future__ import annotations

import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .example_predictor import capture
from .manifest import export_inputs, seal, snapshot_catalog, verify
from .protocol import LAYERS, Invalid, canonical, digest_bytes, file_ref, loads, read_json
from .score import evaluate
from .synthetic import create_fixture, run_demo


def replace_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False) + '\n')


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='requirement-bench-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'fixture'
        self.baseline = run_demo(self.root)
        self.manifest = self.root / 'manifest.json'
        self.pred_path = self.root / 'captured/predictions.jsonl'
        self.preds = [loads(line) for line in self.pred_path.read_text().splitlines()]

    def score(self, *, manifest=None, run_id='synthetic-demo'):
        self.pred_path.write_text(''.join(canonical(p).decode() + '\n' for p in self.preds))
        return evaluate(manifest or self.manifest, self.pred_path, 'holdout', run_id)

    def layer(self, report, name='identified_requirements'):
        return report['diagnostics_all_planned']['layers'][name]

    def change_capture(self, index, change, *, rehash=True):
        ref = self.preds[index]['layers'][LAYERS[0]]
        path = self.pred_path.parent / ref['path']
        evidence = read_json(path)
        change(evidence)
        replace_json(path, evidence)
        if rehash:
            new_ref = file_ref(self.pred_path.parent, ref['path'])
            for name in LAYERS:
                if self.preds[index]['layers'][name] is not None:
                    self.preds[index]['layers'][name] = new_ref

    def reseal(self):
        new = self.root / 'manifest-v2.json'
        seal(self.root / 'plan.json', new)
        return new

    def fresh_capture(self, manifest, run_id='rerun'):
        inputs = self.root / 'fresh-inputs'
        export_inputs(manifest, 'holdout', run_id, inputs)
        config = read_json(inputs / 'predictor-config.json')
        catalog = read_json(inputs / 'source-catalog.json')
        out = self.root / 'fresh-captures'
        out.mkdir()
        packets = [loads(x) for x in (inputs / 'requests.jsonl').read_text().splitlines()]
        self.preds = [capture(p, config, catalog, out, input_root=inputs) for p in packets]
        self.pred_path = out / 'predictions.jsonl'
        return self.score(manifest=manifest, run_id=run_id)

    def test_all_known_differs_from_supported_and_any_hit(self):
        result = self.baseline
        layer = self.layer(result)
        self.assertEqual(layer['known_requirement_recall']['denominator'], 7)
        self.assertEqual(layer['known_requirement_recall']['numerator'], 6)
        self.assertEqual(layer['supported_requirement_recall']['rate'], 1)
        self.assertEqual(layer['all_known_requirements_recalled']['numerator'], 1)
        self.assertEqual(layer['all_known_requirements_recalled']['denominator'], 3)
        self.assertEqual(layer['any_hit_diagnostic']['numerator'], 2)
        self.assertEqual(layer['unsupported_requirements_explicitly_unresolved']['rate'], 1)
        self.assertEqual(layer['all_known_accounted_for_diagnostic']['numerator'], 2)
        self.assertEqual(layer['declared_exhaustive_exact_set_match']['denominator'], 1)
        self.assertIsNone(result['expert_headline']['metrics'])
        self.assertFalse(result['expert_headline']['whole_planned_set_eligible'])

    def test_late_text_survives_input_only_export_and_is_used(self):
        request = loads((self.root / 'predictor-inputs/requests.jsonl').read_text().splitlines()[0])
        text = request['input']['narrative']
        self.assertGreater(text.index('fixture:late'), 12000)
        self.assertEqual(text, read_json(self.root / 'synthetic-late.input.json')['narrative'])
        self.assertIn('late', self.baseline['cases'][0]['layers']['identified_requirements']['matched'])

    def test_primary_hit_does_not_satisfy_supporting_or_admin_requirements(self):
        def only_primary(e):
            e['layers']['identified_requirements']['items'] = [e['layers']['identified_requirements']['items'][1]]
        self.change_capture(0, only_primary)
        layer = self.layer(self.score())
        self.assertEqual(layer['any_hit_diagnostic']['numerator'], 2)
        self.assertEqual(layer['all_known_requirements_recalled']['numerator'], 0)
        self.assertEqual(layer['declared_exhaustive_exact_set_match']['rate'], 0)
        self.assertEqual(layer['recall_by_role']['administrative']['rate'], 0)
        self.assertEqual(layer['recall_by_role']['scope']['rate'], 0)

    def test_four_visible_items_come_from_capture_never_top_three(self):
        self.change_capture(0, lambda e: e['layers']['applicant_visible'].update(
            items=e['layers']['retrieval_candidates']['items'][:4]))
        result = self.score()
        self.assertEqual(result['cases'][0]['layers']['applicant_visible']['observed_items'], 4)
        self.assertEqual(len(result['cases'][0]['layers']['applicant_visible']['matched']), 4)
        self.assertEqual(len(result['cases'][0]['layers']['application_included']['matched']), 4)
        self.assertEqual(len(result['cases'][0]['layers']['retrieval_candidates']['matched']), 5)

    def test_missing_visible_capture_is_a_failure_with_planned_denominator(self):
        self.preds[0]['layers']['applicant_visible'] = None
        result = self.score()
        self.assertEqual(result['cases'][0]['layers']['applicant_visible']['status'], 'not_supplied')
        self.assertEqual(self.layer(result, 'applicant_visible')['known_requirement_recall']['numerator'], 1)
        self.assertEqual(self.layer(result, 'applicant_visible')['known_requirement_recall']['denominator'], 7)
        self.assertEqual(self.layer(result, 'retrieval_candidates')['known_requirement_recall']['numerator'], 6)

    def test_inclusion_is_independent_of_identification(self):
        self.preds[0]['layers']['application_included'] = None
        result = self.score()
        self.assertEqual(self.layer(result, 'identified_requirements')['declared_exhaustive_exact_set_match']['rate'], 1)
        self.assertEqual(self.layer(result, 'application_included')['declared_exhaustive_exact_set_match']['rate'], 0)

    def test_wrong_edition_and_invented_citation_invalidate_layer(self):
        for field, value in [('edition', 'wrong-fixture-edition'), ('printing', 'wrong-printing'), ('provision', 'invented')]:
            with self.subTest(field=field):
                original = copy.deepcopy(self.preds)
                ref = self.preds[0]['layers'][LAYERS[0]]
                path = self.pred_path.parent / ref['path']
                original_evidence = read_json(path)
                self.change_capture(0, lambda e: e['layers']['identified_requirements']['items'][0]['reference'].update({field: value}))
                result = self.score()
                self.assertEqual(result['cases'][0]['layers']['identified_requirements']['status'], 'invalid')
                self.assertEqual(self.layer(result)['known_requirement_recall']['numerator'], 1)
                replace_json(path, original_evidence)
                self.preds = original

    def test_resolved_unsupported_standard_is_invalid(self):
        self.change_capture(1, lambda e: e['layers']['identified_requirements']['items'][-1].update(resolution='resolved', reason=None))
        result = self.score()
        self.assertEqual(result['cases'][1]['layers']['identified_requirements']['status'], 'invalid')
        self.assertEqual(self.layer(result)['known_requirement_recall']['denominator'], 7)

    def test_duplicate_prediction_item_is_failure(self):
        self.change_capture(0, lambda e: e['layers']['identified_requirements']['items'].append(
            copy.deepcopy(e['layers']['identified_requirements']['items'][0])))
        result = self.score()
        self.assertEqual(result['cases'][0]['layers']['identified_requirements']['status'], 'invalid')
        self.assertEqual(self.layer(result)['declared_exhaustive_exact_set_match']['rate'], 0)

    def test_omitted_prediction_counts_in_planned_denominator(self):
        self.preds.pop(0)
        result = self.score()
        self.assertEqual(result['cases'][0]['prediction_status'], 'missing')
        self.assertEqual(result['diagnostics_all_planned']['planned_cases'], 3)
        self.assertEqual(self.layer(result)['known_requirement_recall']['denominator'], 7)
        self.assertEqual(self.layer(result)['all_known_requirements_recalled']['denominator'], 3)
        self.assertIsNone(result['original_capture_accounting']['cost_usd'])

    def test_duplicate_records_are_not_cherry_picked(self):
        self.preds.append(copy.deepcopy(self.preds[0]))
        result = self.score()
        self.assertEqual(result['cases'][0]['prediction_status'], 'duplicate')
        self.assertEqual(self.layer(result)['declared_exhaustive_exact_set_match']['rate'], 0)

    def test_error_record_never_gets_hits_even_with_successful_artifacts(self):
        self.preds[0].update(status='error', error='synthetic failure after dispatch')
        result = self.score()
        self.assertEqual(result['cases'][0]['prediction_status'], 'error')
        self.assertEqual(self.layer(result)['declared_exhaustive_exact_set_match']['rate'], 0)

    def test_malformed_json_keeps_planned_denominator(self):
        self.pred_path.write_text('{bad\n' + canonical(self.preds[1]).decode() + '\n')
        result = evaluate(self.manifest, self.pred_path, 'holdout', 'synthetic-demo')
        self.assertEqual(result['diagnostics_all_planned']['planned_cases'], 3)
        self.assertEqual(self.layer(result)['known_requirement_recall']['denominator'], 7)
        self.assertEqual(result['original_capture_accounting']['unparseable_records'], 1)
        self.assertFalse(result['capture_integrity_valid'])
        self.assertIsNone(result['original_capture_accounting']['provider_requests'])

    def test_duplicate_json_fields_do_not_use_last_value(self):
        self.pred_path.write_text('{"case_id":"synthetic-late","case_id":"synthetic-unknown"}\n')
        result = evaluate(self.manifest, self.pred_path, 'holdout', 'synthetic-demo')
        self.assertEqual(result['original_capture_accounting']['unparseable_records'], 1)
        self.assertEqual(result['diagnostics_all_planned']['prediction_status_counts'], {'missing': 3})

    def test_nonfinite_json_is_malformed(self):
        for token in ('NaN', '1e309', '9' * 5000):
            with self.subTest(token=token[:12]):
                self.pred_path.write_text('{"elapsed_ms":' + token + '}\n')
                result = evaluate(self.manifest, self.pred_path, 'holdout', 'synthetic-demo')
                self.assertEqual(result['original_capture_accounting']['unparseable_records'], 1)

    def test_extreme_integer_usage_is_invalid_not_an_evaluator_crash(self):
        self.preds[0]['requests'] = [self.request(input_tokens=10**500)]
        result = self.score()
        self.assertEqual(result['cases'][0]['prediction_status'], 'invalid')
        self.assertIsNone(result['original_capture_accounting']['input_tokens'])

    def test_unplanned_case_cannot_replace_missing_prediction(self):
        self.preds[0]['case_id'] = 'unplanned'
        result = self.score()
        self.assertEqual(result['cases'][0]['prediction_status'], 'missing')
        self.assertFalse(result['capture_integrity_valid'])
        self.assertEqual(result['diagnostics_all_planned']['planned_cases'], 3)

    def test_empty_gold_is_never_perfect(self):
        plan = read_json(self.root / 'plan.json')
        plan['cases'][0]['split'] = plan['cases'][1]['split'] = 'train'
        replace_json(self.root / 'plan.json', plan)
        result = self.fresh_capture(self.reseal())
        self.assertEqual(result['diagnostics_all_planned']['planned_cases'], 1)
        only_empty = self.layer(result)
        self.assertIsNone(only_empty['known_requirement_recall']['rate'])
        self.assertIsNone(only_empty['declared_exhaustive_exact_set_match']['rate'])
        self.assertEqual(only_empty['all_known_requirements_recalled']['rate'], 0)

    def test_unknown_key_coverage_withholds_exact_accuracy(self):
        path = self.root / 'synthetic-late.answer.json'
        key = read_json(path)
        key['coverage']['status'] = 'unknown'
        replace_json(path, key)
        result = self.fresh_capture(self.reseal())
        self.assertIsNone(self.layer(result)['declared_exhaustive_exact_set_match']['rate'])
        self.assertEqual(self.layer(result)['known_requirement_recall']['numerator'], 6)
        self.assertIsNone(result['expert_headline']['metrics'])

    def test_synthetic_expert_status_is_rejected(self):
        path = self.root / 'synthetic-late.answer.json'
        key = read_json(path)
        key['review']['status'] = 'expert_verified'
        replace_json(path, key)
        with self.assertRaisesRegex(Invalid, 'never expert gold'):
            self.score(manifest=self.reseal())

    def test_provisional_key_excluded_from_expert_headline(self):
        path = self.root / 'synthetic-late.answer.json'
        key = read_json(path)
        key['review']['status'] = 'provisional'
        replace_json(path, key)
        result = self.fresh_capture(self.reseal())
        self.assertEqual(result['expert_headline']['eligible_cases'], 0)
        self.assertIn('synthetic/provisional', result['cohorts'])

    def test_real_key_cannot_use_synthetic_catalog(self):
        path = self.root / 'synthetic-late.answer.json'
        key = read_json(path)
        key['origin'] = 'real'
        replace_json(path, key)
        with self.assertRaisesRegex(Invalid, 'synthetic catalog'):
            self.score(manifest=self.reseal())

    def test_exhaustive_key_requires_all_divisions_reviewed(self):
        path = self.root / 'synthetic-late.answer.json'
        key = read_json(path)
        key['coverage']['dimensions']['C'] = 'unreviewed'
        replace_json(path, key)
        with self.assertRaisesRegex(Invalid, 'unreviewed dimensions'):
            self.score(manifest=self.reseal())

    def test_changed_input_requires_reseal_and_fresh_prediction(self):
        path = self.root / 'synthetic-late.input.json'
        inp = read_json(path)
        inp['narrative'] = inp['narrative'].replace('fixture:late', 'No late requirement now.')
        replace_json(path, inp)
        with self.assertRaisesRegex(Invalid, 'hash changed'):
            self.score()
        manifest = self.reseal()
        stale = self.score(manifest=manifest)
        self.assertEqual(stale['cases'][0]['prediction_status'], 'invalid')
        fresh = self.fresh_capture(manifest)
        self.assertEqual(fresh['cases'][0]['prediction_status'], 'ok')
        self.assertNotIn('late', fresh['cases'][0]['layers']['identified_requirements']['matched'])
        self.assertEqual(self.layer(fresh)['declared_exhaustive_exact_set_match']['rate'], 0)

    def test_extra_catalogued_reference_on_minimum_key_is_unadjudicated(self):
        reference = read_json(self.root / 'catalog.json')['references'][0]
        self.change_capture(1, lambda e: e['layers']['identified_requirements']['items'].append(
            {'reference': reference, 'resolution': 'resolved', 'reason': None}))
        result = self.score()
        stage = result['cases'][1]['layers']['identified_requirements']
        self.assertEqual(stage['status'], 'ok')
        self.assertEqual(stage['extra_items'], 1)
        self.assertEqual(self.layer(result)['known_requirement_recall']['numerator'], 6)

    def test_no_predictions_file_rows_does_not_drop_any_cases(self):
        self.preds = []
        result = self.score()
        self.assertEqual(result['diagnostics_all_planned']['prediction_status_counts'], {'missing': 3})
        self.assertEqual(self.layer(result)['known_requirement_recall']['rate'], 0)
        self.assertEqual(self.layer(result)['declared_exhaustive_exact_set_match']['rate'], 0)

    def test_run_identity_is_bound(self):
        result = self.score(run_id='different-run')
        self.assertEqual(result['diagnostics_all_planned']['prediction_status_counts'], {'invalid': 3})

    def test_tampered_inline_payload_with_old_bindings_is_rejected_by_predictor(self):
        inputs = self.root / 'predictor-inputs'
        packet = loads((inputs / 'requests.jsonl').read_text().splitlines()[0])
        packet['input']['narrative'] += ' TAMPERED PAYLOAD'
        with self.assertRaisesRegex(Invalid, 'inline input payload hash changed'):
            capture(packet, read_json(inputs / 'predictor-config.json'), read_json(inputs / 'source-catalog.json'),
                    self.root / 'captured', input_root=inputs)

    def test_scorer_checks_actual_request_payload_not_only_claimed_hashes(self):
        ref = self.preds[0]['observed_inputs']['request']
        path = self.pred_path.parent / ref['path']
        packet = read_json(path)
        packet['input']['narrative'] += ' TAMPERED PAYLOAD'
        replace_json(path, packet)
        # Rehash the observed artifact, while preserving every old claimed binding.
        self.preds[0]['observed_inputs']['request'] = file_ref(self.pred_path.parent, ref['path'])
        result = self.score()
        self.assertEqual(result['cases'][0]['prediction_status'], 'invalid')
        self.assertIn('inline input payload hash changed', result['cases'][0]['errors'][0])
        self.assertEqual(result['cases'][0]['layers']['identified_requirements']['matched'], [])

    def test_rehashed_foreign_observed_config_and_catalog_are_rejected(self):
        for field in ('config', 'catalog'):
            with self.subTest(field=field):
                ref = self.preds[0]['observed_inputs'][field]
                path = self.pred_path.parent / ref['path']
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                self.preds[0]['observed_inputs'][field] = file_ref(self.pred_path.parent, ref['path'])
                result = self.score()
                self.assertEqual(result['cases'][0]['prediction_status'], 'invalid')
                self.assertIn(f'observed {field} hash changed', result['cases'][0]['errors'][0])
                path.write_bytes(original)
                self.preds[0]['observed_inputs'][field] = ref

    def test_success_without_observed_inputs_is_not_accepted(self):
        self.preds[0]['observed_inputs'] = None
        result = self.score()
        self.assertEqual(result['cases'][0]['prediction_status'], 'invalid')
        self.assertEqual(self.layer(result)['declared_exhaustive_exact_set_match']['rate'], 0)

    def test_observed_attachment_bytes_are_bound_to_the_request(self):
        (self.root / 'supplied.txt').write_text('Synthetic supplied applicant text.')
        path = self.root / 'synthetic-late.input.json'
        inp = read_json(path)
        inp['attachments'] = [{**file_ref(self.root, 'supplied.txt'), 'media_type': 'text/plain'}]
        replace_json(path, inp)
        manifest = self.reseal()
        result = self.fresh_capture(manifest)
        self.assertEqual(result['cases'][0]['prediction_status'], 'ok')
        ref = self.preds[0]['observed_inputs']['attachments'][0]
        (self.pred_path.parent / ref['path']).write_text('Substituted attachment')
        self.preds[0]['observed_inputs']['attachments'][0] = file_ref(self.pred_path.parent, ref['path'])
        result = self.score(manifest=manifest, run_id='rerun')
        self.assertEqual(result['cases'][0]['prediction_status'], 'invalid')
        self.assertIn('observed input attachments differ', result['cases'][0]['errors'][0])

    def test_changed_answer_config_catalog_and_manifest_are_rejected(self):
        for filename in ('synthetic-late.answer.json', 'config.json', 'catalog.json', 'manifest.json'):
            with self.subTest(file=filename):
                path = self.root / filename
                data = path.read_bytes()
                path.write_bytes(data + b' ')
                if filename == 'manifest.json':
                    obj = read_json(path)
                    obj['dataset_id'] = 'tampered'
                    replace_json(path, obj)
                with self.assertRaises(Invalid):
                    self.score()
                path.write_bytes(data)

    def test_changed_evidence_hash_fails_without_losing_other_cases(self):
        self.change_capture(0, lambda e: e.update(kind='captured'), rehash=False)
        result = self.score()
        self.assertTrue(all(s['status'] == 'invalid' for s in result['cases'][0]['layers'].values()))
        self.assertEqual(self.layer(result)['known_requirement_recall']['numerator'], 1)

    def test_rehashed_foreign_evidence_is_still_rejected(self):
        self.change_capture(0, lambda e: e.update(case_id='foreign-case'))
        self.assertEqual(self.score()['cases'][0]['layers']['applicant_visible']['status'], 'invalid')

    def test_captured_layers_require_real_raw_artifacts(self):
        self.change_capture(0, lambda e: e.update(kind='captured'))
        self.assertEqual(self.score()['cases'][0]['layers']['applicant_visible']['status'], 'invalid')

    def test_malformed_capture_paths_count_as_layer_failures(self):
        self.preds[0]['layers']['applicant_visible'] = {'path': 'bad\x00path', 'sha256': 'a' * 64}
        result = self.score()
        self.assertEqual(result['cases'][0]['layers']['applicant_visible']['status'], 'invalid')
        self.assertEqual(self.layer(result, 'applicant_visible')['all_known_requirements_recalled']['denominator'], 3)

    def test_overflowed_capture_cost_totals_stay_unknown(self):
        self.preds[0]['requests'] = [self.request(cost_usd=1e308),
                                    self.request(request_id='synthetic-overflow', cost_usd=1e308)]
        result = self.score()
        self.assertIsNone(result['original_capture_accounting']['cost_usd'])
        self.assertIsNone(result['original_capture_accounting']['reported_cost_usd_subtotal'])
        json.dumps(result, allow_nan=False)

    def request(self, **changes):
        return {'request_id': 'synthetic-request-1', 'provider': 'synthetic-test-only', 'model': 'fixture',
                'status': 'error', 'input_tokens': 11, 'output_tokens': None, 'cost_usd': None,
                'latency_ms': 100, 'error': 'synthetic timeout', **changes}

    def test_failure_usage_and_unknown_cost_are_preserved(self):
        self.preds[0].update(status='error', error='synthetic provider timeout', requests=[self.request()], elapsed_ms=100)
        accounting = self.score()['original_capture_accounting']
        self.assertEqual(accounting['provider_requests'], 1)
        self.assertEqual(accounting['failed_provider_request_records'], 1)
        self.assertIsNone(accounting['cost_usd'])
        self.assertIsNone(accounting['output_tokens'])
        self.assertEqual(accounting['input_tokens'], 11)
        self.assertEqual(accounting['requests'][0]['error'], 'synthetic timeout')

    def test_retries_count_failed_and_successful_requests(self):
        self.preds[0]['requests'] = [self.request(cost_usd=.01, output_tokens=0),
                                    self.request(request_id='synthetic-retry', status='ok', error=None,
                                                 cost_usd=.02, input_tokens=12, output_tokens=3)]
        result = self.score()
        usage = result['original_capture_accounting']
        self.assertEqual(usage['provider_requests'], 2)
        self.assertEqual(usage['failed_provider_request_records'], 1)
        self.assertAlmostEqual(usage['cost_usd'], .03)
        self.assertEqual(usage['input_tokens'], 23)
        self.assertEqual(result['cases'][0]['prediction_status'], 'ok')

    def test_malformed_usage_keeps_other_known_request_entries(self):
        self.preds[0]['requests'] = [self.request(cost_usd=.125, output_tokens=5), {'bad': 'ledger entry'}]
        result = self.score()
        usage = result['original_capture_accounting']
        self.assertEqual(result['cases'][0]['prediction_status'], 'invalid')
        self.assertEqual(usage['known_input_tokens_subtotal'], 11)
        self.assertEqual(usage['reported_cost_usd_subtotal'], .125)
        self.assertIsNone(usage['cost_usd'])

    def test_duplicate_provider_request_ids_do_not_invent_total_cost(self):
        req = self.request(cost_usd=.1)
        self.preds[0]['requests'] = [req]
        self.preds[1]['requests'] = [req]
        result = self.score()
        self.assertFalse(result['capture_integrity_valid'])
        self.assertEqual(result['original_capture_accounting']['duplicate_request_ids'], [req['request_id']])
        self.assertIsNone(result['original_capture_accounting']['cost_usd'])

    def test_failed_latency_is_included_and_missing_latency_stays_unknown(self):
        for pred, latency in zip(self.preds, (1, 50, 1000)):
            pred['elapsed_ms'] = latency
        self.preds[2].update(status='error', error='synthetic slow failure')
        usage = self.score()['original_capture_accounting']
        self.assertEqual(usage['latency_ms']['median'], 50)
        self.assertEqual(usage['latency_ms']['maximum'], 1000)
        self.preds[0]['elapsed_ms'] = None
        self.assertEqual(self.score()['original_capture_accounting']['latency_ms']['unknown_attempts'], 1)

    def test_no_network_is_used_by_export_or_scoring(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            export_inputs(self.manifest, 'holdout', 'offline-check', self.root / 'offline-inputs')
            result = self.score()
        self.assertEqual(result['this_offline_evaluation']['provider_requests'], 0)
        self.assertEqual(result['this_offline_evaluation']['cost_usd'], 0)

    def test_cli_replay_and_missing_record_exit_status(self):
        command = [sys.executable, '-m', 'evals_dev.requirement_bench', 'score', '--manifest', str(self.manifest),
                   '--predictions', str(self.pred_path), '--split', 'holdout', '--run-id', 'synthetic-demo']
        proc = subprocess.run(command + ['--out', str(self.root / 'cli-report.json')], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(loads(proc.stdout)['expert_metrics'])
        self.preds.pop(0)
        self.score()
        proc = subprocess.run(command + ['--out', str(self.root / 'failed-cli-report.json')], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(read_json(self.root / 'failed-cli-report.json')['diagnostics_all_planned']['planned_cases'], 3)


class SplitAndProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='requirement-bench-split-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'fixture'
        create_fixture(self.root)
        self.plan_path = self.root / 'plan.json'
        self.plan = read_json(self.plan_path)

    def seal(self):
        replace_json(self.plan_path, self.plan)
        return seal(self.plan_path, self.root / 'manifest.json')

    def test_group_split_leakage_is_rejected(self):
        self.plan['cases'][0]['split'] = 'train'
        self.plan['cases'][1]['groups'] = self.plan['cases'][0]['groups']
        with self.assertRaisesRegex(Invalid, 'cross-split leakage'):
            self.seal()

    def test_same_narrative_different_case_ids_cannot_cross_splits(self):
        self.plan['cases'][0]['split'] = 'train'
        first = read_json(self.root / 'synthetic-late.input.json')
        second = read_json(self.root / 'synthetic-external.input.json')
        second['narrative'] = '\n' + first['narrative'].upper().replace(' ', '  ') + '\n'
        replace_json(self.root / 'synthetic-external.input.json', second)
        with self.assertRaisesRegex(Invalid, 'cross-split leakage'):
            self.seal()

    def test_shared_attachment_cannot_cross_splits(self):
        self.plan['cases'][0]['split'] = 'train'
        attachment = self.root / 'attachment.txt'
        attachment.write_text('synthetic shared attachment')
        for cid in ('synthetic-late', 'synthetic-external'):
            path = self.root / f'{cid}.input.json'
            inp = read_json(path)
            inp['attachments'] = [{**file_ref(self.root, attachment.name), 'media_type': 'text/plain'}]
            replace_json(path, inp)
        with self.assertRaisesRegex(Invalid, 'cross-split leakage'):
            self.seal()

    def test_transitive_lineage_cannot_cross_splits(self):
        self.plan['cases'][0].update(split='train', groups=['source-a'])
        self.plan['cases'][1].update(split='train', groups=['source-a', 'rewrite-b'])
        self.plan['cases'][2].update(split='holdout', groups=['rewrite-b'])
        with self.assertRaisesRegex(Invalid, 'cross-split leakage'):
            self.seal()

    def test_opaque_answer_bytes_are_not_deserialized_until_scoring(self):
        (self.root / 'synthetic-late.answer.json').write_text('not JSON: opaque answer-side sentinel')
        self.seal()
        export_inputs(self.root / 'manifest.json', 'holdout', 'input-only', self.root / 'exported')
        self.assertNotIn('answer', ' '.join(str(p) for p in (self.root / 'exported').rglob('*')))
        text = (self.root / 'exported/requests.jsonl').read_text()
        self.assertNotIn('answer-side sentinel', text)
        for packet in (loads(line) for line in text.splitlines()):
            self.assertFalse({'reviewer', 'coverage', 'groups', 'answer', 'split'} & set(packet))
            self.assertEqual(set(packet['input']), {'schema_version', 'case_id', 'narrative', 'facts', 'attachments'})
            capture(packet, read_json(self.root / 'exported/predictor-config.json'),
                    read_json(self.root / 'exported/source-catalog.json'), self.root / 'exported',
                    input_root=self.root / 'exported')

    def test_attachment_copy_contains_only_declared_inputs(self):
        a = self.root / 'supplied.txt'
        a.write_text('Synthetic applicant-supplied material')
        path = self.root / 'synthetic-late.input.json'
        inp = read_json(path)
        inp['attachments'] = [{**file_ref(self.root, a.name), 'media_type': 'text/plain'}]
        replace_json(path, inp)
        self.seal()
        export_inputs(self.root / 'manifest.json', 'holdout', 'input-only', self.root / 'exported')
        self.assertEqual((self.root / 'exported/supplied.txt').read_bytes(), a.read_bytes())
        self.assertFalse((self.root / 'exported/plan.json').exists())

    def test_export_preserves_exact_config_and_catalog_bytes(self):
        for filename in ('config.json', 'catalog.json'):
            path = self.root / filename
            path.write_text(json.dumps(read_json(path), separators=(',', ':')))
        self.seal()
        export_inputs(self.root / 'manifest.json', 'holdout', 'bytes-check', self.root / 'exported')
        self.assertEqual((self.root / 'config.json').read_bytes(),
                         (self.root / 'exported/predictor-config.json').read_bytes())
        self.assertEqual((self.root / 'catalog.json').read_bytes(),
                         (self.root / 'exported/source-catalog.json').read_bytes())

    def test_key_copied_under_an_attachment_name_is_rejected_by_hash(self):
        key = self.root / 'synthetic-late.answer.json'
        copied = self.root / 'renamed.txt'
        copied.write_bytes(key.read_bytes())
        path = self.root / 'synthetic-external.input.json'
        inp = read_json(path)
        inp['attachments'] = [{**file_ref(self.root, copied.name), 'media_type': 'text/plain'}]
        replace_json(path, inp)
        with self.assertRaisesRegex(Invalid, 'answer bytes are an input'):
            self.seal()

    def test_dataset_plan_cannot_be_exported_as_an_input_attachment(self):
        path = self.root / 'synthetic-late.input.json'
        inp = read_json(path)
        inp['attachments'] = [{**file_ref(self.root, 'plan.json'), 'media_type': 'application/json'}]
        replace_json(path, inp)
        # The plan bytes remain unchanged, so the attachment is hash-valid.
        with self.assertRaisesRegex(Invalid, 'private dataset plan'):
            seal(self.plan_path, self.root / 'manifest.json')

    def test_input_whitelist_rejects_answer_fields(self):
        path = self.root / 'synthetic-late.input.json'
        inp = read_json(path)
        inp['gold'] = ['forbidden']
        replace_json(path, inp)
        with self.assertRaisesRegex(Invalid, 'expected fields'):
            self.seal()

    def test_answer_like_fact_fields_are_rejected(self):
        path = self.root / 'synthetic-late.input.json'
        inp = read_json(path)
        inp['facts'] = [{'field': 'known_outcome', 'value': 'forbidden'}]
        replace_json(path, inp)
        with self.assertRaisesRegex(Invalid, 'answer-like'):
            self.seal()

    def test_holdout_requires_input_outcome_leakage_review(self):
        self.plan['cases'][0]['leakage_review']['status'] = 'unreviewed'
        with self.assertRaisesRegex(Invalid, 'not cleared'):
            self.seal()

    def test_bundle_path_cannot_escape_including_symlinks(self):
        outside = self.root.parent / 'outside.json'
        outside.write_text('{}')
        (self.root / 'link.json').symlink_to(outside)
        self.plan['cases'][0]['input'] = 'link.json'
        with self.assertRaisesRegex(Invalid, 'escapes bundle'):
            self.seal()

    def test_attachment_drift_and_split_reseal_tampering_are_checked(self):
        self.seal()
        manifest = self.root / 'manifest.json'
        m = read_json(manifest)
        m['cases'][0]['split'] = 'train'
        m['cases'][0]['groups'] = m['cases'][1]['groups']
        from .protocol import fingerprint
        m['seal_sha256'] = fingerprint({k: v for k, v in m.items() if k != 'seal_sha256'})
        replace_json(manifest, m)
        with self.assertRaisesRegex(Invalid, 'cross-split leakage'):
            verify(manifest)

    def test_export_refuses_overwrite(self):
        self.seal()
        export_inputs(self.root / 'manifest.json', 'holdout', 'first', self.root / 'exported')
        with self.assertRaisesRegex(Invalid, 'already exists'):
            export_inputs(self.root / 'manifest.json', 'holdout', 'second', self.root / 'exported')

    def test_protocol_import_does_not_import_scorer_or_keys(self):
        proc = subprocess.run([sys.executable, '-c', 'import sys; import evals_dev.requirement_bench.protocol; '
                               'assert "evals_dev.requirement_bench.score" not in sys.modules; '
                               'assert "evals_dev.requirement_bench.manifest" not in sys.modules'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_catalog_snapshot_uses_real_schema_and_division_identity(self):
        db = self.root / 'synthetic-schema.sqlite'
        with sqlite3.connect(db) as con:
            con.executescript('create table docs(doc,label,kind,citable,sha256); '
                              'create table provisions(doc,division,id,sort_key);')
            con.execute('insert into docs values(?,?,?,?,?)', ('NBC-AE', 'NBC(AE) 2023 p2', 'code', 1, digest_bytes(b'fixture')))
            con.executemany('insert into provisions values(?,?,?,?)', [('NBC-AE', d, 'fixture', d) for d in ('A', 'B', 'C')])
        result = snapshot_catalog(db)
        self.assertEqual(len(result['references']), 3)
        self.assertEqual({r['division'] for r in result['references']}, {'A', 'B', 'C'})
        self.assertEqual(result['provenance']['corpus_files']['database'], digest_bytes(db.read_bytes()))
        self.assertIsNone(result['provenance']['corpus_files']['wal'])


if __name__ == '__main__':
    unittest.main()
