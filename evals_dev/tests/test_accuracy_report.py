"""The accuracy report builder (scripts/accuracy_report.py, WP-16): no figure without a source, no claim without a test,
no provider name, and the code identification section follows the stored rows."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('accuracy_report', ROOT / 'scripts' / 'accuracy_report.py')
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

REPORT = json.loads((ROOT / 'docs' / 'accuracy' / 'report.json').read_text(encoding='utf-8'))


def test_the_committed_report_validates_and_was_built_from_a_clean_tree():
    ar.validate(REPORT)
    assert REPORT['built_from']['dirty'] is False, 'regenerate after committing the code it measures'
    assert ar.HEX.match(REPORT['built_from']['commit'])
    v = REPORT['verified']
    assert v and v['passed'] == v['total'], 'the committed report is built with its guaranteed tests run and passing'


def test_a_non_finite_number_fails_the_build():
    broken = copy.deepcopy(REPORT)
    broken['measured'][0]['figures'][0]['x'] = float('nan')
    with pytest.raises(ar.ReportError, match='non-finite'):
        ar.validate(broken)


def test_without_the_database_recheck_no_fabrication_count_is_shown():
    probe = _probe()
    probe['integrity_rechecked'] = False
    s = _section(probe)
    assert not [f for f in s['figures'] if f['id'] == 'codeid.fabricated']
    g1 = next(t for t in s['detail'] if t['title'] == 'Gate G1 checks')['rows']
    assert any(r[0] == 'Fabricated citations shown' and r[1] == 'not rechecked' for r in g1)


def test_a_figure_without_a_source_fails_the_build():
    for breakage in (lambda f: f.pop('source'), lambda f: f['source'].update(commit=''),
                     lambda f: f['source'].update(kind='file', paths=[]), lambda f: f['source'].update(kind='pr', pr=None),
                     lambda f: f.update(n=0), lambda f: f.update(dataset='')):
        broken = copy.deepcopy(REPORT)
        breakage(broken['measured'][0]['figures'][0])
        with pytest.raises(ar.ReportError):
            ar.validate(broken)


def test_a_claim_without_a_test_or_with_a_missing_test_fails_the_build():
    broken = copy.deepcopy(REPORT)
    broken['guaranteed'][0]['tests'] = []
    with pytest.raises(ar.ReportError, match='names no test'):
        ar.validate(broken)
    claims = [{'id': 'x', 'tests': ['engine/tests/test_export.py::test_that_does_not_exist']},
              {'id': 'y', 'tests': ['web/src/rules/rules.test.ts::no such test']}, {'id': 'z', 'tests': []}]
    problems = ar.check_tests(claims)
    assert len(problems) == 3


def test_every_guaranteed_claim_names_tests_that_exist():
    assert ar.check_tests(ar.GUARANTEED) == []
    assert len(ar.GUARANTEED) >= 8
    committed = {c['id']: [t['id'] for t in c['tests']] for c in REPORT['guaranteed']}
    assert committed == {c['id']: c['tests'] for c in ar.GUARANTEED}, 'the committed report is stale: rebuild it'


def test_a_provider_name_fails_the_build():
    broken = copy.deepcopy(REPORT)
    broken['measured'][0]['figures'][0]['label'] = 'Scored by gpt-6-luna'
    with pytest.raises(ar.ReportError, match='provider name'):
        ar.validate(broken)


def _probe(repeats_screen: int = 2, winner: str | None = None, g15: str = 'NOT RUN') -> dict:
    def ev(x, n=79, repeats=1, usd=0.0):
        return {'cases': n, 'repeats': repeats, 'missing_rows': 0,
                'success': {'x': x, 'n': n, 'rate': x / n, 'wilson_95': list(ar.wilson(x, n))},
                'by_group': {'part9': {'x': x / 2, 'n': 45, 'rate': 0.5, 'wilson_95': [0.3, 0.6]}},
                'by_repeat': [x / n], 'ranking': {'hit@1': {'mean': 0.6}, 'hit@5': {'mean': 0.8}, 'mrr': {'mean': 0.7}},
                'top1_agreement': 0.85, 'usd_per_case_run': usd, 'errors': {'rows': n * repeats, 'rows_with_errors': 0, 'rows_retried': 0},
                'fabricated_citations_shown': 0, 'quote_match_before_filtering': 0.97}
    sel = {'R0-bm25': ev(28), 'R5-jev-screen-rerank60': ev(60.5, repeats=repeats_screen, usd=0.018),
           'V15f-R5': ev(63.6, repeats=5, usd=0.019)}
    return {
        'cases': {'total': 139, 'selection_gold': 79, 'selection_by_group': {'part9': 45, 'other': 25, 'mixed': 9},
                  'development_gold': 38, 'public53': 53, 'by_dataset': {}},
        'selection': sel, 'development': {'V15f-R5': ev(30.4, n=38, repeats=5)},
        'public53': {'R0-bm25': ev(18, n=53), 'R5-jev-screen-rerank60': ev(33.5, n=53, repeats=repeats_screen)},
        'kinds': {'R0-bm25': 'rank', 'R5-jev-screen-rerank60': 'rerank', 'V15f-R5': 'verify', 'R4-jev-screen': 'screen'},
        'chains': {'V15f-R5': ['R4-jev-screen', 'R5-jev-screen-rerank60', 'V15f-R5']},
        'latency': {}, 'stage_latency': {},
        'g1': [{'id': 'G1.1', 'status': 'PASS'}, {'id': 'G1.5', 'status': g15}],
        'rerank_mrr_public53': [0.71, 0.715], 'top1_by_part': {'V15f-R5': {}},
        'decision': {'best': 'V15f-R5', 'winner': winner, 'provisional': None if winner else 'V15f-R5', 'agreement_min': 0.9,
                     'rows': [{'arm': 'V15f-R5', 'tied': True, 'p_worse': 1.0, 'notes': [],
                               'robust': {'agreement_ok': bool(winner), 'top1_agreement': 0.846}}]},
        'rows': {'live': 3503, 'first': '2026-10-21T18:00:00Z', 'last': '2026-10-21T23:00:00Z'},
        'row_files': [{'arm': 'V15f-R5', 'rows': 395, 'sha256': 'abcdef0123456789'}],
        'integrity_rechecked': True,
    }


def _section(probe: dict) -> dict:
    return {'id': 'code-id', 'title': 't', 'plain': 'p', **ar.code_id_from_probe(probe, '6a4279525d22f39501cb2456431121446007c3c9', 'branch b')}


def test_code_identification_from_stored_rows_is_provisional_and_names_no_provider():
    s = _section(_probe())
    assert s['status'] == 'provisional'
    product = next(f for f in s['figures'] if f['id'] == 'codeid.product')
    assert product['value'] == '63.6 of 79' and 'provisional' in product['tags'] and product['interval']
    assert any(c.startswith('Provisional: 2 complete relevance draws') for c in s['caveats'])
    assert '84.6%' in ' '.join(s['caveats'])
    report = {**REPORT, 'measured': [s]}
    ar.validate(report)
    assert not ar.PROVIDER_NAMES.search(json.dumps(s))


def test_the_same_code_reports_a_finished_benchmark_as_measured():
    s = _section(_probe(repeats_screen=5, winner='V15f-R5', g15='PASS'))
    assert s['status'] == 'measured'
    assert not any('provisional' in f['tags'] for f in s['figures'])
    assert s['caveats'][0].startswith('The decision rule chose')


def test_without_benchmark_rows_the_section_says_not_run_and_shows_no_number(monkeypatch):
    monkeypatch.setattr(ar, 'bench_tree', lambda ref: (None, None, None, None))
    s = ar.code_id_section(None)
    assert s['status'] == 'not_run' and s['figures'] == []
    ar.validate({**REPORT, 'measured': [s]})


def test_an_unverified_draft_never_overwrites_the_published_report(monkeypatch, tmp_path):
    published = (ar.OUT_JSON.read_text(), ar.OUT_MD.read_text())
    monkeypatch.setattr(ar, 'build', lambda **kw: {'draft': True})
    monkeypatch.setattr(ar, 'dump', lambda r: '{"draft": true}')
    monkeypatch.setattr(ar, 'render_md', lambda r: '# draft')
    monkeypatch.setattr(ar, '_draft_paths', lambda: (tmp_path / 'report.json', tmp_path / 'report.md'))
    assert ar.main(['--no-verify']) == 0
    assert (ar.OUT_JSON.read_text(), ar.OUT_MD.read_text()) == published
    assert (tmp_path / 'report.json').read_text() == '{"draft": true}'


def test_draft_paths_are_a_fresh_private_folder_each_run():
    import stat
    (j1, _), (j2, _) = ar._draft_paths(), ar._draft_paths()
    assert j1.parent != j2.parent
    assert stat.S_IMODE(j1.parent.stat().st_mode) == 0o700
    assert not j1.parent.is_symlink()


def test_a_failed_markdown_render_leaves_the_published_json_untouched(monkeypatch):
    published = ar.OUT_JSON.read_text()
    monkeypatch.setattr(ar, 'build', lambda **kw: {'draft': True})
    monkeypatch.setattr(ar, 'dump', lambda r: '{"new": true}')
    def boom(r):
        raise RuntimeError('render failed')
    monkeypatch.setattr(ar, 'render_md', boom)
    with pytest.raises(RuntimeError):
        ar.main([])
    assert ar.OUT_JSON.read_text() == published


def test_a_failed_second_replacement_rolls_back_the_first(tmp_path, monkeypatch):
    a, b = tmp_path / 'report.json', tmp_path / 'report.md'
    a.write_text('old json')
    b.write_text('old md')
    real = ar.os.replace
    calls = []

    def flaky(src, dst):
        calls.append(dst)
        if str(dst) == str(b):
            raise OSError('disk full')
        return real(src, dst)

    monkeypatch.setattr(ar.os, 'replace', flaky)
    with pytest.raises(OSError):
        ar._publish({a: 'new json', b: 'new md'})
    monkeypatch.setattr(ar.os, 'replace', real)
    assert (a.read_text(), b.read_text()) == ('old json', 'old md')
    assert sorted(p.name for p in tmp_path.iterdir()) == ['report.json', 'report.md']   # no temp files left


def test_publish_uses_unique_temp_files(tmp_path):
    a = tmp_path / 'report.json'
    ar._publish({a: 'one'})
    ar._publish({a: 'two'})
    assert a.read_text() == 'two' and [p.name for p in tmp_path.iterdir()] == ['report.json']
