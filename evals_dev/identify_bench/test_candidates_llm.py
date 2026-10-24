"""Offline tests for the LLM candidate generators: no network, live.openai_json is monkeypatched."""
from __future__ import annotations

import pytest

from evals_dev.identify_bench import candidates_llm as m
from evals_dev.identify_bench import live


def test_cli_report_never_rebuilds_or_dispatches(monkeypatch, tmp_path):
    monkeypatch.setattr(m, 'RESULTS', tmp_path)
    monkeypatch.setattr(m, 'report', lambda: pytest.fail('report must not rebuild with model calls'))
    assert m.main(['report', '--live']) == 2


def test_cli_is_cache_only_without_explicit_live_flag(monkeypatch):
    seen = []
    monkeypatch.setattr(m.bench_cases, 'all_cases', lambda: [])
    monkeypatch.setattr(m, 'my_spend', lambda: 0)
    def run(*args, **kwargs):
        seen.append(kwargs['live_calls'])
        return {}
    monkeypatch.setattr(m, 'run_arm', run)
    assert m.main(['toc']) == 0
    assert seen == [False]


def test_cli_live_flag_reaches_one_uncached_synthetic_transport(monkeypatch, tmp_path):
    from engine.identify import providers
    from evals_dev.identify_bench.cache import Store
    from evals_dev.identify_bench.cases import Case
    for attr, name in (('_elephant_store', 'elephant'), ('_openai_store', 'openai'), ('_spend', 'spend')):
        monkeypatch.setattr(live, attr, Store(name, tmp_path))
    monkeypatch.setattr(live, 'ENV_FILE', tmp_path / 'absent.env')
    monkeypatch.setattr(live, '_live_enabled', False)
    monkeypatch.setattr(m.bench_cases, 'all_cases', lambda: [
        Case('cli-live', 'dev', 'A house with a soffit near the property line.', ('9.10.15.5.',))])
    called = []
    def raw(*args, **kwargs):
        called.append(args[0])
        return {'articles': [{'id': '9.10.15.5.', 'role': 'departs_from', 'reason': 'Exterior wall'}]}, \
               {'input_tokens': 10, 'output_tokens': 5, 'returned_model': kwargs['model']}
    monkeypatch.setattr(providers, 'raw_openai_json', raw)
    assert m.main(['toc', '--live', '--fold', 'all', '--limit', '1']) == 0
    assert called == ['toc_screen']
    assert live._live_enabled is False


def test_toc_has_every_division_b_article_once():
    text = m.toc_text()
    articles = [line.split(' ', 1)[0] for line in text.splitlines() if line[:1].isdigit()]
    assert len(articles) == 2080 == len(set(articles)) == len(m.article_ids())


def test_toc_hierarchy_puts_articles_under_their_subsection_and_section():
    lines = m.toc_text().splitlines()
    i = lines.index('9.10.15.5. Construction of Exposing Building Face of Houses')
    sub = next(l for l in reversed(lines[:i]) if l.startswith('#### '))
    sec = next(l for l in reversed(lines[:i]) if l.startswith('### '))
    part = next(l for l in reversed(lines[:i]) if l.startswith('## '))
    assert sub == '#### 9.10.15. Spatial Separation Between Houses'
    assert sec == '### 9.10. Fire Protection'
    assert part == '## Part 9 Housing and Small Buildings'
    # a section heading precedes its first subsection (sort_key lists subsections first)
    assert lines.index('### 9.10. Fire Protection') < lines.index('#### 9.10.1. Definitions and Application')


def test_toc_parts_filter():
    text = m.toc_text(parts={9})
    assert text.startswith('## Part 9') and '## Part 3' not in text


def test_validate_ids_drops_and_counts_unknown_and_repairs_trailing_dot():
    valid, invalid = m.validate_ids(['9.10.15.5.', '9.10.15.5', '9.10.15.5.', '9.99.99.99.', 'Table 9.10.14.4.', '', None])
    assert valid == ['9.10.15.5.']
    assert invalid == ['9.99.99.99.', 'Table 9.10.14.4.', '', None]


def test_luna_toc_parses_schema_and_reports_invalid(monkeypatch):
    seen = {}

    def fake(name, schema, system, user, **kw):
        seen.update(name=name, schema=schema, system=system, user=user, **kw)
        return {'articles': [
            {'id': '9.10.15.5.', 'role': 'departs_from', 'reason': 'soffit protection'},
            {'id': '9.10.15.4.', 'role': 'must_meet', 'reason': 'openings'},
            {'id': '9.10.15.42.', 'role': 'related', 'reason': 'made up'},
            {'id': '9.10.15.4.', 'role': 'related', 'reason': 'duplicate'},
        ]}, {'input_tokens': 10, 'output_tokens': 5, 'usd': 0.0}

    monkeypatch.setattr(live, 'openai_json', fake)
    r = m.luna_toc('house soffit near property line', effort='medium', picks=40)
    assert r['ranked'] == ['9.10.15.5.', '9.10.15.4.']
    assert r['invalid'] == ['9.10.15.42.'] and r['returned'] == 4
    assert r['roles'] == {'9.10.15.5.': 'departs_from', '9.10.15.4.': 'must_meet'}
    assert seen['model'] == 'gpt-6-luna' and seen['effort'] == 'medium' and seen['tag'].startswith('w2-')
    assert seen['schema']['properties']['articles']['items']['properties']['role']['enum'] == list(m.ROLES)
    assert 'RECALL-FIRST' in seen['system'] and 'never judge' in seen['system'].lower()
    assert '9.10.15.5. Construction of Exposing Building Face of Houses' in seen['system']


def test_luna_hyde_fuses_facet_retrievals(monkeypatch):
    monkeypatch.setattr(live, 'openai_json', lambda *a, **k: ({'facets': [
        {'facet': 'spatial separation', 'search_terms': 'limiting distance soffit exposing building face',
         'passage': 'Soffits within 1.2 m of the property line shall be protected.'},
        {'facet': 'guards', 'search_terms': 'guard height balcony', 'passage': 'Guards shall be not less than 1 070 mm high.'},
    ]}, {'usd': 0.0}))
    r = m.luna_hyde('house soffit and balcony guard')
    assert r['ranked'] and not r['invalid']
    assert set(r['ranked']) <= m.article_ids()
    assert '9.10.15.5.' in r['ranked'][:40]


def test_rrf_and_interleave():
    assert m.rrf([['a', 'b'], ['b', 'c']])[0] == 'b'
    assert m.interleave(['a', 'b', 'c'], ['x', 'a']) == ['a', 'x', 'b', 'c']


def test_no_network_in_tests(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('network')
    monkeypatch.setattr(live, 'openai_json', boom)
    with pytest.raises(AssertionError):
        m.luna_toc('x')
