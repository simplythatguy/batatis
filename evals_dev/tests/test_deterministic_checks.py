"""Deterministic checks. No human key and no model grade."""
import json
import sqlite3
from pathlib import Path

import pytest

from evals_dev import deterministic_checks
from evals_dev.deterministic_checks import (
    AB_FIELDS, CODEDB_MISSING, build_report, load_schemas, provision_exact, render,
    score_citations, score_planted,
)
from evals_dev.output_adapters import citations, discover
from evals_dev.stats import wilson_interval

DEV = Path(__file__).resolve().parents[1]
ROOT_SCHEMAS = DEV / 'schemas'
MANIFESTS = DEV / 'planted' / 'ab_minimal'


def _pair(function='F03', objective='OP3.1', bracket='[F03-OP3.1]', note=''):
    """Build one synthetic objective/function attribution pair."""
    return {'function': function, 'objective': objective, 'bracket': bracket, 'application_note': note}


def _db(pairs=None, status='direct', root=None):
    """Build a synthetic normalized database view for Section C comparisons."""
    return {
        'pairs': pairs if pairs is not None else [_pair()],
        'intents': [],
        'status': {'status': status, 'root_provision': root},
        'comparison': None,
    }


def test_wilson_bounds_a_known_ratio():
    """Verify wilson bounds a known ratio."""
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(1, 2)
    assert 0.0 <= low < 0.5 < high <= 1.0


def test_section_c_exactness_accepts_only_a_full_match():
    """Verify section c exactness accepts only a full match."""
    engine = {'pairs': [_pair()], 'intents': [], 'comparison': None}
    gold = {'pairs': ['[F03-OP3.1]'], 'conditional': [], 'status': 'direct', 'root_provision': None}
    assert provision_exact(engine, _db(), gold)
    assert not provision_exact(engine, _db(pairs=[_pair(objective='OS1.2', bracket='[F03-OS1.2]')]), gold)
    assert not provision_exact(engine, _db(), dict(gold, pairs=['[F02-OP1.2]']))
    assert not provision_exact(None, _db(), None)


def test_citation_resolution_splits_system_and_gold(tmp_path):
    """Verify citation resolution splits system and gold."""
    db = tmp_path / 'codedb.sqlite'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE provisions (doc TEXT, division TEXT, id TEXT)')
    con.execute("INSERT INTO provisions VALUES ('NBC-AE', 'B', '9.10.15.5.(8)')")
    con.commit()
    con.close()
    system = [
        {'provision': '9.10.15.5.(8)', 'division': 'B'},
        {'provision': '9.99.99.99.(1)', 'division': 'B'},
    ]
    scored = score_citations(system, db, empty_reason='no system output')
    assert scored['label'] == '1 of 2'
    assert scored['wilson_95'] == wilson_interval(1, 2)
    missing = score_citations(system, None, empty_reason='no system output')
    assert missing['n'] == 0 and missing['skipped'] == CODEDB_MISSING
    empty = score_citations([], db, empty_reason='no system output')
    assert empty['skipped'] == 'no system output'


def test_adapters_read_each_output_kind():
    """Verify adapters read each output kind."""
    identify = citations('identify', [{'articles': [{'provision': '9.10.15.5.(8)', 'division': 'B'}]}])
    section_c = citations('section_c', [{'section_c': [{'provision_id': '9.10.15.5.(8)', 'division': 'B'}]}])
    section_d = citations('section_d', [{'issues': [{'citation': 'Div B Sentence 9.10.15.5.(8)'}]}])
    assert [c['source'] for c in identify + section_c + section_d] == ['identify', 'section_c', 'section_d']
    assert {c['provision'] for c in identify + section_c + section_d} == {'9.10.15.5.(8)'}


def test_planted_detection_is_known_by_construction():
    """Verify planted detection is known by construction."""
    manifests = [json.loads(p.read_text()) for p in sorted(MANIFESTS.glob('*.json'))]
    assert sum(len(m['removed_fields']) for m in manifests) == 10
    assert any(m['role'] == 'clean-control' and m['removed_fields'] == [] for m in manifests)

    def checker(facts):
        """Detect administrative fields absent from the supplied applicant facts."""
        return {field for field in AB_FIELDS if field not in facts}

    detection, false_positives = score_planted(manifests, checker)
    assert detection['label'] == '10 of 10'
    assert false_positives['label'] == '0 of 8'
    blind, noisy = score_planted(manifests, lambda facts: set(AB_FIELDS))
    assert blind['label'] == '10 of 10'
    assert noisy['label'] == '8 of 8'
    missed, _ = score_planted(manifests, lambda facts: set())
    assert missed['x'] == 0 and missed['n'] == 10


def test_report_without_codedb_does_not_mix_in_a_model_grade(tmp_path):
    """Verify report without codedb does not mix in a model grade."""
    case = {'id': 'dev-001', 'gold': {'must_cite': [{'division': 'B', 'provision': '9.10.15.5.(8)'}],
                                     'section_c': [], 'intake_action': 'ask'}}
    report = build_report(
        root=tmp_path, db_path=None, cases=[case],
        manifests=[json.loads(p.read_text()) for p in sorted(MANIFESTS.glob('*.json'))],
        schemas=load_schemas(ROOT_SCHEMAS),
        documents={'identify': [{'articles': [], 'intake_action': 'ask'}]},
    )
    assert report['grader'] == 'deterministic'
    assert report['evals'] == 'model-checked'
    assert report['human_key'] == 'unfilled'
    assert 'model_grader_agreement' not in report
    assert 'accuracy' not in report
    checks = report['checks']
    assert checks['section_c_exactness']['skipped'] == CODEDB_MISSING
    assert checks['citation_resolution']['fixture_gold']['skipped'] == CODEDB_MISSING
    assert checks['planted_missing_fields']['detection']['skipped'] == CODEDB_MISSING
    assert checks['schema_validity']['by_kind']['identify']['label'] == '1 of 1'
    assert checks['schema_validity']['by_kind']['case']['skipped'] == CODEDB_MISSING
    text = render(report)
    assert text.startswith('deterministic checks')
    assert 'model-checked' in text and 'unfilled' in text
    assert 'human-verified' not in text


def test_invalid_engine_output_fails_schema_validity():
    """Verify invalid engine output fails schema validity."""
    bad = {'articles': [{'provision': '9.99.99.99.(1)'}], 'intake_action': 'ask'}
    report = build_report(
        root=MANIFESTS, db_path=None, cases=[], manifests=[],
        schemas=load_schemas(ROOT_SCHEMAS),
        documents={'identify': [bad]},
    )
    identify = report['checks']['schema_validity']['by_kind']['identify']
    assert identify['label'] == '0 of 1'
    assert identify['wilson_95'] == wilson_interval(0, 1)


@pytest.mark.parametrize('findings', [[], [{
    'id': 'missing-owner', 'section': 'A', 'field': 'owner_name',
    'message': 'Supply the owner name.', 'severity': 'blocking',
}]])
def test_completeness_file_is_one_schema_document(tmp_path, findings):
    """The file adapter preserves valid empty and populated findings arrays."""
    folder = tmp_path / 'outputs' / 'completeness'
    folder.mkdir(parents=True)
    (folder / 'findings.json').write_text(json.dumps(findings))
    identify = tmp_path / 'outputs' / 'identify'
    identify.mkdir()
    docs = [{'articles': [], 'intake_action': 'ask'}, {'articles': [], 'intake_action': 'redirect'}]
    (identify / 'batch.json').write_text(json.dumps(docs))
    found = discover(tmp_path)
    assert found['completeness'] == [findings]
    assert found['identify'] == docs
    report = build_report(root=tmp_path, db_path=None, cases=[], manifests=[],
                          schemas=load_schemas(ROOT_SCHEMAS))
    row = report['checks']['schema_validity']['by_kind']['completeness']
    assert row['label'] == '1 of 1' and row['skipped'] is None


def test_find_codedb_uses_only_environment_and_repository_paths(tmp_path, monkeypatch):
    """Discovery prefers an explicit database and reports a missing repository copy."""
    dev = tmp_path / 'evals_dev'
    dev.mkdir()
    monkeypatch.setattr(deterministic_checks, 'DEV', dev)
    monkeypatch.delenv('BATATIS_CODEDB', raising=False)
    checked = []
    is_file = Path.is_file

    def track_is_file(path):
        """Record every probed path without changing filesystem behavior."""
        checked.append(path)
        return is_file(path)

    monkeypatch.setattr(Path, 'is_file', track_is_file)
    repo_db = tmp_path / 'codedb' / 'build' / 'codedb.sqlite'
    assert deterministic_checks.find_codedb() is None
    assert checked == [repo_db]
    repo_db.parent.mkdir(parents=True)
    repo_db.touch()
    assert deterministic_checks.find_codedb() == repo_db
    external = tmp_path / 'external.sqlite'
    external.touch()
    monkeypatch.setenv('BATATIS_CODEDB', str(external))
    assert deterministic_checks.find_codedb() == external
    external.unlink()
    assert deterministic_checks.find_codedb() == repo_db
