"""The claims registry: every claim has an owner, every named test exists, nothing is called backed without evidence."""
import ast
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / 'evals_dev' / 'accuracy' / 'claims.yaml'
IDS = [f'C{i}' for i in range(1, 6)] + [f'M{i}' for i in range(1, 8)] + [f'G{i}' for i in range(1, 6)]
STATUSES = {'backed', 'partial', 'planned'}


@pytest.fixture(scope='module')
def claims():
    data = json.loads(REGISTRY.read_text())
    assert data['schema'] == 'batatis-claims/1'
    return data['claims']


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_every_claim_of_the_plan_is_listed_once(claims):
    assert list(claims) == IDS


def test_each_claim_is_complete(claims):
    for cid, c in claims.items():
        assert c['kind'] in ('guaranteed', 'measured', 'gate') and c['title'].strip()
        assert c['kind'] == {'C': 'guaranteed', 'M': 'measured', 'G': 'gate'}[cid[0]], cid
        assert c['status'] in STATUSES and c['owner'].strip(), cid
        assert isinstance(c['tests'], list) and isinstance(c['runs'], list), cid
        assert c['gap'].strip(), f'{cid} must say what is missing'


def test_every_named_test_exists(claims):
    for cid, c in claims.items():
        for ref in c['tests']:
            path, _, name = ref.partition('::')
            assert name, f'{cid}: {ref} needs path::test_name'
            file = REPO / path
            assert file.is_file(), f'{cid}: {path} does not exist'
            assert name in function_names(file), f'{cid}: {name} is not defined in {path}'


def test_every_guaranteed_claim_has_a_test(claims):
    for cid, c in claims.items():
        if c['kind'] == 'guaranteed':
            assert c['tests'], f'{cid} has no test; a guaranteed claim without one is not guaranteed'


def test_nothing_is_backed_or_partial_without_evidence(claims):
    for cid, c in claims.items():
        evidence = bool(c['tests']) or any(r.get('artifact') or r.get('pending') for r in c['runs'])
        if c['status'] in ('backed', 'partial'):
            assert evidence, f'{cid} is {c["status"]} with no test and no run'
        if c['status'] == 'planned':
            assert not c['tests'] or cid == 'G4', f'{cid} is planned but has tests; call it partial'


def test_a_finished_run_names_an_artifact_that_exists(claims):
    for cid, c in claims.items():
        for r in c['runs']:
            assert r['command'].strip()
            if not r.get('pending') and r.get('artifact'):
                assert (REPO / r['artifact']).is_file() or r['artifact'].startswith('docs/accuracy/'), f'{cid}: {r["artifact"]}'


def test_the_held_out_run_is_recorded_as_pending_not_done(claims):
    pending = [r for r in claims['M7']['runs'] if r.get('pending')]
    assert pending and 'once' in pending[0]['note']


def test_nothing_in_the_registry_names_the_screening_vendor():
    """The registry feeds the accuracy page. Nothing a user can see may name the vendor; internal eval files may."""
    assert 'jev' not in REGISTRY.read_text().lower()
