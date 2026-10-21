"""The committed result rows are consistent with the code that reads them, and the committed memo is what those rows produce."""
import gzip
import json
from collections import Counter

import pytest

from evals_dev.identify_bench import analysis, memo
from evals_dev.identify_bench.arms import arm_hashes, standard_arms
from evals_dev.identify_bench.rows import RESULTS, RowStore, row_key

REPO = RESULTS.parents[2]
MEMO = REPO / 'docs' / 'accuracy' / 'code-id-decision.md'
G1 = REPO / 'docs' / 'accuracy' / 'g1-report.md'


def packed_rows():
    for path in sorted(RESULTS.glob('*.jsonl.gz')):
        with gzip.open(path, 'rt', encoding='utf-8') as fh:
            for line in fh:
                if line.strip():
                    yield path.name.split('.jsonl')[0], json.loads(line)


def test_every_committed_row_has_the_key_its_fields_give():
    n = 0
    for arm, r in packed_rows():
        assert r['arm'] == arm
        assert r['key'] == row_key(r['config_hash'], r['case_id'], r['repeat'], r['profile']), (arm, r['case_id'])
        assert r['order'] or r['errors'], f'{arm} {r["case_id"]} has neither a ranking nor an error'
        n += 1
    assert n > 0


def test_live_rows_carry_the_hash_of_the_arm_the_registry_builds_today():
    hashes = arm_hashes(standard_arms())
    stale = Counter()
    for arm, r in packed_rows():
        if r['source'] == 'live' and arm in hashes and r['config_hash'] != hashes[arm]:
            stale[arm] += 1
    assert not stale, f'rows written by an arm config that no longer exists (re-run or migrate them): {dict(stale)}'


def test_no_row_names_a_key_or_a_secret():
    blob = ''.join(json.dumps(r) for _a, r in packed_rows())
    assert 'sk-' not in blob and 'Bearer' not in blob and 'OPENAI_API_KEY=' not in blob


def test_the_committed_memo_and_g1_report_are_the_current_output_of_the_committed_rows():
    if not MEMO.is_file():
        pytest.skip('docs/accuracy/code-id-decision.md has not been generated yet')
    try:
        from engine.identify.corpus import articles
        from evals_dev.identify_bench.live import db_path
        db = db_path()
        arts = articles(db)
    except Exception:                                               # noqa: BLE001 - no code database in this environment
        pytest.skip('code database not built; the quote recheck in the memo needs it')
    import hashlib
    recorded = {r['codedb_sha256'] for _a, r in packed_rows() if r['source'] == 'live' and r['codedb_sha256']}
    if hashlib.sha256(db.read_bytes()).hexdigest() not in recorded:
        pytest.skip('this code database is not the build the rows were measured on')
    an = analysis.analyse(RowStore(RESULTS), arts=arts)
    from evals_dev.identify_bench.datasets import FOLDS_FILE
    folds_sha = json.loads(FOLDS_FILE.read_text())['sha256']
    ledgers = {}
    from evals_dev.identify_bench.ledger import Ledger
    from evals_dev.identify_bench.live import LEDGER_DIR, OPENAI_STOP_USD
    for provider, stop in (('openai', OPENAI_STOP_USD), ('jev', None)):
        p = LEDGER_DIR / f'{provider}.jsonl'
        ledgers[provider] = Ledger(p, provider, stop).summary() if p.exists() else None
    assert memo.render_decision(an, ledger_openai=ledgers['openai'], ledger_jev=ledgers['jev'], folds_sha=folds_sha) == MEMO.read_text()
    assert memo.render_g1_report(an, ledger_openai=ledgers['openai'], ledger_jev=ledgers['jev']) == G1.read_text()


def test_every_upstream_reference_resolves_to_a_committed_row():
    keys: dict[str, set[str]] = {}
    refs = []
    for arm, r in packed_rows():
        keys.setdefault(arm, set()).add(r['key'])
        refs += [(arm, up, k) for up, k in r['upstream'].items()]
    missing = Counter((arm, up) for arm, up, k in refs if k not in keys.get(up, set()))
    assert not missing, f'rows point at upstream rows that are not in the committed files: {dict(missing)}'
