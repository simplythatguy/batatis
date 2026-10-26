"""Cache crash/race and corpus identity checks use temporary files only."""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from evals_dev.identify_bench import cache, candidates_lexical, pipeline_bench as bench


def test_partial_crash_tail_does_not_destroy_saved_answers(tmp_path):
    store = cache.Store('answers', tmp_path)
    store.put('saved', {'answer': 1})
    with store.path.open('ab') as f:
        f.write(b'{"key":"interrupted","response":')
    reader = cache.Store('answers', tmp_path)
    assert reader.get('saved') == {'answer': 1}
    store.put('new', {'answer': 2})
    assert reader.get('new') == {'answer': 2}
    assert cache.Store('answers', tmp_path).get('saved') == {'answer': 1}
    assert len([json.loads(line) for line in store.path.read_text().splitlines()]) == 2


def test_claim_serializes_separate_store_instances(tmp_path):
    stores = [cache.Store('answers', tmp_path) for _ in range(4)]

    def one(store):
        with store.claim('request'):
            hit = store.get('request')
            if hit is None:
                store.put('request', {'answer': 1})

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(one, stores))
    assert len(stores[0].path.read_text().splitlines()) == 1


def test_atomic_save_rejects_nonfinite_without_replacing_previous_report(tmp_path):
    path = tmp_path / 'report.json'
    path.write_text('{"saved":true}\n')
    with pytest.raises(ValueError):
        cache.atomic_json(path, {'bad': float('nan')})
    assert json.loads(path.read_text()) == {'saved': True}
    cache.atomic_json(path, {'complete': True})
    assert json.loads(path.read_text()) == {'complete': True}


def test_lexical_cache_changes_with_db_content_and_preserves_old_entry(monkeypatch, tmp_path):
    db = tmp_path / 'corpus.sqlite'
    db.write_bytes(b'first corpus')
    store = cache.Store('lexical', tmp_path)
    monkeypatch.setattr(bench, 'DB', db)
    monkeypatch.setattr(bench, '_LEX', store)
    monkeypatch.setattr(candidates_lexical, 'build_graph', lambda *a, **k: object())
    calls = []

    def rank(*a, **k):
        calls.append(1)
        return [str(len(calls))]

    monkeypatch.setattr(candidates_lexical, 'bm25_v3', rank)
    monkeypatch.setattr(candidates_lexical, 'pool', lambda base, *a, **k: base)
    recipe = bench.Recipe()
    assert bench._lexical_pool('same proposal', recipe) == ['1']
    assert bench._lexical_pool('same proposal', recipe) == ['1']
    stamp = db.stat()
    db.write_bytes(b'other corpus')
    os.utime(db, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
    assert bench._lexical_pool('same proposal', recipe) == ['2']
    assert len(store.rows()) == 2


def test_wal_content_is_part_of_corpus_identity(tmp_path):
    db = tmp_path / 'corpus.sqlite'
    db.write_bytes(b'database')
    before = cache.corpus_fingerprint(db)
    (tmp_path / 'corpus.sqlite-wal').write_bytes(b'new committed content')
    assert cache.corpus_fingerprint(db) != before
