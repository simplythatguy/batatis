"""Aggregation over every repeat. The runner is fake; this test does not call a model."""
import json
from pathlib import Path

import pytest

from engine.identify.benchmark import gold_from_entries, run_variants, write_results


def _result(order, committed, intake):
    return {
        'mode': 'openai',
        'intake_action': intake,
        'articles': [{'provision': art, 'committed': art in committed} for art in order],
        'trace': {
            'ranked_ids': order,
            'usage': {
                'input_tokens': 10,
                'output_tokens': 2,
                'by_model': {
                    'gpt-4.1-mini-2025-04-14': {
                        'input_tokens': 8, 'output_tokens': 1,
                        'returned': ['gpt-4.1-mini-2025-04-14'],
                    },
                    'gpt-4.1-2025-04-14': {
                        'input_tokens': 2, 'output_tokens': 1,
                        'returned': ['gpt-4.1-2025-04-14'],
                    },
                },
            },
        },
    }


def _runner():
    calls = {}

    def run(query, **_kwargs):
        rep = calls.get(query, 0) % 3
        calls[query] = calls.get(query, 0) + 1
        if query == 'gold':
            if rep == 0:
                return _result(['9.10.15.5.', '9.99.99.99.'], ['9.10.15.5.', '9.99.99.99.'], 'proceed_conditionally')
            if rep == 1:
                return _result(['9.10.15.5.'], ['9.10.15.5.'], 'proceed_conditionally')
            return _result(['9.8.8.8.', '9.7.7.7.', '9.10.15.5.'], [], 'ask')
        return _result(['9.1.1.1.'], ['9.1.1.1.'] if rep == 0 else [], 'ask')

    run.calls = calls
    return run


CASES = [
    {'id': 'gold-case', 'query': 'gold', 'gold': ['9.10.15.5.'],
     'gold_roles': [{'division': 'B', 'provision': '9.10.15.5.(8)', 'role': 'benchmark',
                     'article': '9.10.15.5.'}]},
    {'id': 'no-gold-case', 'query': 'nogold', 'gold': [], 'gold_roles': []},
]


def test_empty_must_cite_is_not_given_invented_gold():
    gold, roles = gold_from_entries([])
    assert gold == [] and roles == []
    gold, roles = gold_from_entries([
        {'division': 'B', 'provision': '9.10.15.5.(8)', 'role': 'benchmark'},
        {'division': 'B', 'provision': '9.10.15.1.', 'role': 'scope'},
    ])
    assert gold == ['9.10.15.5.', '9.10.15.1.']
    assert [row['role'] for row in roles] == ['benchmark', 'scope']


def test_every_repeat_is_scored_and_no_gold_commits_are_separate(tmp_path):
    runner = _runner()
    code = run_variants(CASES, 3, 1.4097, '2026-10-19', runner=runner, out_dir=tmp_path)
    assert code == 0
    # 2 cases x 3 repeats x 4 variants. Each variant sees the same three-repeat script.
    assert runner.calls == {'gold': 12, 'nogold': 12}

    payload = json.loads((tmp_path / 'results.json').read_text())
    assert payload['fx_usd_cad'] == 1.4097 and payload['fx_date'] == '2026-10-19'
    assert 'sk-' not in (tmp_path / 'results.json').read_text()
    assert 'OPENAI_API_KEY' not in (tmp_path / 'summary.csv').read_text()
    variant = next(row for row in payload['variants'] if row['name'] == 'c_openai_rerank_verify')
    assert variant['n_gold'] == 1 and variant['n_no_gold'] == 1 and variant['n'] == 2
    repeats = variant['per_repeat']
    assert [row['top1'] for row in repeats] == [1.0, 1.0, 0.0]
    assert [row['recall5'] for row in repeats] == [1.0, 1.0, 1.0]
    assert repeats[2]['mrr'] == pytest.approx(1 / 3)
    assert [row['ask_rate'] for row in repeats] == [0.5, 0.5, 1.0]
    assert [row['committed_errors_gold'] for row in repeats] == [1, 0, 0]
    assert [row['commits_no_gold'] for row in repeats] == [1, 0, 0]
    assert variant['series']['top1']['mean'] == pytest.approx(2 / 3)
    assert variant['series']['top1']['min'] == 0.0 and variant['series']['top1']['max'] == 1.0
    assert variant['series']['top1']['mean'] != repeats[0]['top1']
    assert variant['series']['mrr']['mean'] == pytest.approx((1 + 1 + 1 / 3) / 3)
    assert variant['series']['ask_rate']['mean'] == pytest.approx(2 / 3)
    assert variant['series']['committed_errors_gold']['mean'] == pytest.approx(1 / 3)
    assert variant['series']['commits_no_gold']['mean'] == pytest.approx(1 / 3)
    assert variant['stability'] == pytest.approx(0.5)
    assert variant['majority_top1_accuracy'] == pytest.approx(1.0)

    gold = next(row for row in variant['cases'] if row['id'] == 'gold-case')
    assert gold['gold'] == ['9.10.15.5.']
    assert gold['gold_roles'][0]['role'] == 'benchmark'
    assert gold['majority_top1'] == '9.10.15.5.'
    assert gold['stable'] is False
    assert [rep['top5'][0] for rep in gold['repeats']] == ['9.10.15.5.', '9.10.15.5.', '9.8.8.8.']
    assert gold['repeats'][0]['committed'] == ['9.10.15.5.', '9.99.99.99.']
    assert [rep['intake'] for rep in gold['repeats']] == ['proceed_conditionally', 'proceed_conditionally', 'ask']
    nogold = next(row for row in variant['cases'] if row['id'] == 'no-gold-case')
    assert nogold['gold'] == [] and nogold['stable'] is True
    assert nogold['repeats'][0]['committed'] == ['9.1.1.1.']
    assert variant['returned_models']['rerank'] == ['gpt-4.1-mini-2025-04-14']
    assert variant['returned_models']['verifier'] == ['gpt-4.1-2025-04-14']

    csv_text = (tmp_path / 'summary.csv').read_text()
    assert 'committed_errors_gold' in csv_text and 'commits_no_gold' in csv_text
    assert '1.4097' in csv_text and '2026-10-19' in csv_text


def test_write_results_refuses_a_key(tmp_path):
    with pytest.raises(SystemExit):
        write_results({'note': 'sk-secret'}, tmp_path)
    assert not (tmp_path / 'results.json').exists()


def test_default_output_dir_is_gitignored():
    text = Path('out/identify-benchmark/')
    ignore = (Path(__file__).resolve().parents[2] / '.gitignore').read_text()
    assert f'{text}' in ignore or 'out/identify-benchmark/' in ignore
