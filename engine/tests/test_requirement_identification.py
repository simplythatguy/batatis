"""Production identification through its public seam, using synthetic source corpora.

These fixtures test provenance checks/retrieval/state, not building-code accuracy.
No provider credentials, production database, PDF files or network are required.
"""
import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest

from codedb import ids, store
from engine.codes import Codes
from engine.identify import pipeline
from engine.identify.config import IdentifyConfig, load_config
from engine.models import Fact, Source
from engine.models_identify import IdentifyResult
from engine.tests._network_guard import block_network


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    block_network(monkeypatch)
    monkeypatch.setattr(pipeline, 'default_transports', lambda *a, **k: pytest.fail('production discovery initialized providers'))


def database(tmp_path, articles, *, notes=(), metadata_change=None):
    path = tmp_path / 'source.sqlite'
    con = store.create(path)
    sha = hashlib.sha256(b'synthetic extracted source').hexdigest()
    src = dict(label='NBC(AE) 2023 p2', text_sha256=sha, pdf_sha256=hashlib.sha256(b'synthetic pdf').hexdigest(),
               citable_as_alberta_law=True)
    doc = dict(doc='NBC-AE', label='NBC(AE) 2023 p2', kind='code', citable=1, pdf='synthetic.pdf', text_jsonl='synthetic.jsonl', sha256=sha)
    if metadata_change:
        metadata_change(doc, src)
    con.execute('INSERT INTO docs VALUES (:doc,:label,:kind,:citable,:pdf,:text_jsonl,:sha256)', doc)
    con.execute("INSERT INTO meta VALUES ('build_version','2')")
    con.execute("INSERT INTO meta VALUES ('stats',?)", (json.dumps(dict(build_version='2', sources={'NBC-AE': src})),))
    inserted = set()

    def add(div, pid, title='', text=''):
        p = ids.parse(pid)
        if (div, pid) in inserted:
            return
        inserted.add((div, pid))
        row = dict(doc='NBC-AE', division=div, id=pid, level=p.level, part=p.part,
                   section=str(ids.Pid(p.nums[:2])) if len(p.nums) >= 2 else None,
                   subsection=str(ids.Pid(p.nums[:3])) if len(p.nums) >= 3 else None,
                   article=str(p.article) if p.article else None, parent_id=str(p.parent()) if p.parent() else None,
                   title=title, article_title=title, text=text, pdf_page=10 + len(inserted), pdf_page_end=10 + len(inserted),
                   sort_key='.'.join(f'{n:03}' for n in p.nums) + f'|{p.sentence or 0:03}')
        columns = ','.join(row)
        con.execute(f'INSERT INTO provisions ({columns}) VALUES ({",".join("?" for _ in row)})', tuple(row.values()))
    for div, pid, title, sentences in articles:
        p = ids.parse(pid)
        add(div, str(ids.Pid(p.nums[:2])))
        add(div, str(ids.Pid(p.nums[:3])))
        add(div, pid, title)
        for n, text in enumerate(sentences, 1):
            add(div, f'{pid}({n})', text=text)
    for div, note_id, title, text, target in notes:
        con.execute('INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?)', ('NBC-AE', div, note_id, title, text, text, 101, 101, 1))
        if target:
            con.execute('INSERT INTO note_links VALUES (?,?,?,?,?)', ('NBC-AE', div, note_id, target, 'note_id'))
    # Deliberately leave the persisted FTS tables empty. Production scans the
    # actual full passages and does not silently trust a stale search index.
    store.finalize(con, path)
    return Codes(path)


def run(codes, prose='', **kw):
    return pipeline.run(prose, codes=codes, config=kw.pop('config', load_config(env={})), **kw).result


def by_id(result, pid, division='B'):
    return next(r for r in result.requirements if r.provision_id == pid and r.division == division)


def fact(field, value, *, status='confirmed', fid='fact_1'):
    return Fact(id=fid, field=field, value=value, kind='pointed', status=status,
                source=Source(type='user_text', ref='synthetic description'))


def test_default_is_zero_provider_and_historical_hashes_are_retained(tmp_path):
    codes = database(tmp_path, [('B', '9.1.1.1.', 'Egress', ['An egress window.'])])
    result = run(codes, 'egress', verifier=object(), transports=object())
    assert load_config(env={}).screen == 'requirements'
    assert result.trace.usd == 0 and result.requirement_coverage.provider_requests == 0
    assert all(s.requests == 0 and s.input_tokens == 0 and s.output_tokens == 0 for s in result.trace.stages)
    assert result.model_ids == dict(screen=None, rerank=None, verifier=None)
    assert result.committed == [] and not result.benchmark.identified and not result.trace.exhaustive
    assert IdentifyConfig().config_hash == '464590da27f5cbf1'
    assert load_config(env={'BATATIS_IDENTIFY_SCREEN': 'jev', 'BATATIS_IDENTIFY_RERANK': 'jev'}).config_hash == '5f1c92331550984a'
    assert load_config(env={'BATATIS_IDENTIFY_SCREEN': 'decisions', 'BATATIS_IDENTIFY_RERANK': 'decisions'}).config_hash == '43272040048a6036'


def test_no_card_or_candidate_cutoff_and_late_passage_is_the_quote(tmp_path):
    rows = [('B', f'9.1.1.{n}.', f'Synthetic item {n}', ['Unrelated opening. ' * 100,
             f'{n}) Fenestration shall address synthetic condition {n}.']) for n in range(1, 86)]
    result = run(database(tmp_path, rows), 'fenestration',
                 config=replace(load_config(env={}), card_chars=1, rerank_n=1, verify_n=1, top_k=1, choices_k=1))
    assert len(result.articles) == len(result.requirements) == 85
    assert all(a.provision_id.endswith('(2)') and 'Fenestration' in a.quote and 'Unrelated' not in a.quote for a in result.articles)
    assert all(r.disposition == 'review' and r.needs_review and not r.human_confirmed for r in result.requirements)
    assert not result.requirement_coverage.exhaustive


def test_exact_id_anywhere_without_keywords_or_model_has_no_arbitrary_quote(tmp_path):
    codes = database(tmp_path, [('B', '9.7.2.1.', 'Glazing', ['An unrelated opening sentence.'])])
    result = run(codes, ('z' * 50000) + ' 9.7.2.1')
    record = by_id(result, '9.7.2.1.')
    assert any(d.kind == 'explicit' for d in record.discoveries)
    assert record.quote is None and result.articles[0].quote is None
    assert result.requirement_coverage.provisions_scanned == 4
    assert result.trace.usd == 0


def test_long_query_chunks_keep_last_term_and_fact_values_are_searched(tmp_path):
    codes = database(tmp_path, [('B', '3.1.1.1.', 'Acoustic', ['Resonance control.']),
                                ('B', '9.1.1.1.', 'Windows', ['Fenestration control.'])])
    words = ' '.join('token' + chr(97 + n // 26) + chr(97 + n % 26) for n in range(200))
    result = run(codes, words + ' resonance', facts=[fact('custom.description', 'fenestration 9.1.1.1.(1)')])
    assert {'3.1.1.1.', '9.1.1.1.'} <= {a.provision for a in result.articles}
    assert result.requirement_coverage.query_chunks >= 4
    assert by_id(result, '9.1.1.1.').quote == 'Fenestration control.'


def test_transitive_forward_reverse_cycles_and_unresolved_references(tmp_path):
    codes = database(tmp_path, [
        ('B', '9.1.1.1.', 'Seed', ['Seedword. See Article 9.1.1.2.']),
        ('B', '9.1.1.2.', 'Dependency', ['See Article 9.1.1.3.']),
        ('B', '9.1.1.3.', 'Cycle', ['See Article 9.1.1.1. and Article 9.1.1.99.']),
        ('B', '9.1.1.4.', 'Reverse', ['This depends on Article 9.1.1.2.']),
    ])
    result = run(codes, 'seedword')
    assert len(result.articles) == 4
    assert any(d.kind == 'reverse_reference' for d in by_id(result, '9.1.1.4.').discoveries)
    third = by_id(result, '9.1.1.3.')
    assert any(d.path == ['NBC-AE:B:9.1.1.1.', 'NBC-AE:B:9.1.1.2.', 'NBC-AE:B:9.1.1.3.'] for d in third.discoveries)
    assert any(g.code == 'unresolved_reference' and '9.1.1.99.' in g.reference for g in result.requirement_coverage.gaps)
    assert not any('99.' in a.provision for a in result.articles)
    pool = {e.id: e for e in result.requirement_evidence}
    assert all(eid in pool for r in result.requirements for eid in r.evidence_ids)
    assert any('See Article 9.1.1.3.' in pool[d.evidence_id].quote for d in third.discoveries if d.kind == 'reference')


def test_division_qualified_references_admin_subtrees_and_context_notes(tmp_path):
    codes = database(tmp_path, [
        ('B', '9.1.1.1.', 'Seed', ['Seedword. See Article 1.2.1.1. of Division A.']),
        ('A', '1.2.1.1.', 'Alternative Solutions', ['Alternative solutions require documentation.']),
        ('B', '1.2.1.1.', 'Different rule', ['Differentcontent.']),
        ('C', '2.3.1.1.', 'Alternative Solutions', ['Alternative solutions require analysis.']),
        ('C', '2.3.1.2.', 'Tests', ['Tests shall be documented.']),
    ], notes=[('B', 'A-9.1.1.1.', 'Context', 'Glossaryword explains the context.', '9.1.1.1.')])
    # Give the extracted administrative parent its source heading.
    with sqlite3.connect(codes.db_path) as con:
        con.execute("UPDATE provisions SET title='Alternative Solutions' WHERE division='C' AND id='2.3.1.'")
    result = run(codes, 'seedword glossaryword')
    assert by_id(result, '1.2.1.1.', 'A').role == 'admin'
    assert not any(a.provision == '1.2.1.1.' for a in result.articles)
    assert by_id(result, '2.3.1.2.', 'C').role == 'admin'
    assert any(e.kind == 'note' and e.contextual for e in result.requirement_evidence)
    assert all(r.disposition == 'review' for r in result.requirements)


@pytest.mark.parametrize('change', [
    lambda d, s: d.update(label='NBC(AE) 2019 p2'),
    lambda d, s: s.update(label='NBC(AE) 2023 p1'),
    lambda d, s: d.update(sha256='0' * 64),
    lambda d, s: s.pop('pdf_sha256'),
    lambda d, s: d.update(citable=0),
])
def test_wrong_edition_or_missing_provenance_fails_closed(tmp_path, change):
    result = run(database(tmp_path, [('B', '9.1.1.1.', 'Egress', ['Egress.'])], metadata_change=change), 'egress 9.1.1.1.')
    assert result.requirement_status == 'source_unavailable'
    assert result.articles == [] and result.requirements == [] and result.process_refs == []
    assert result.requirement_coverage.source is None and result.trace.usd == 0


def test_foreign_codes_standards_tables_and_missing_sources_are_gaps(tmp_path):
    codes = database(tmp_path, [('B', '9.1.1.1.', 'Seed', [
        'Seedword. See Article 9.1.1.2. of the National Fire Code, NECB, CSA A23.3, Table 9.1.1.1. and Appendix D.']),
        ('B', '9.1.1.2.', 'Unrelated', ['Unrelatedcontent.'])])
    result = run(codes, 'seedword')
    assert not any(a.provision == '9.1.1.2.' for a in result.articles)
    gap_codes = {g.code for g in result.requirement_coverage.gaps}
    assert {'fire_code_unavailable', 'energy_code_unavailable', 'referenced_standard_unavailable',
            'table_content_unavailable', 'appendix_content_unavailable'} <= gap_codes
    assert all(e.citation.startswith('NBC(AE) 2023 p2,') for e in result.requirement_evidence)


def test_scope_inputs_remain_unknown_or_conflicting_without_part_filter(tmp_path):
    codes = database(tmp_path, [('B', '3.1.1.1.', 'Egress', ['Egress for occupancy.']),
                                ('B', '9.1.1.1.', 'Egress', ['Egress if building area and storeys are limited.'])])
    unknown = run(codes, 'egress')
    assert all(c.status == 'unknown' for r in unknown.requirements for c in r.conditions)
    conflict = run(codes, 'egress', facts=[fact('storeys', 2), fact('building.storeys', 8, fid='fact_2')])
    assert {a.part for a in conflict.articles} == {3, 9}
    assert next(c for c in by_id(conflict, '9.1.1.1.').conditions if c.field == 'storeys').status == 'conflict'
    assert by_id(conflict, '9.1.1.1.').disposition == 'review'


def test_confirmations_and_reason_survive_unchanged_input_and_become_review_after_changes(tmp_path):
    codes = database(tmp_path, [('B', '9.1.1.1.', 'Egress', ['Egress for storeys.'])])
    previous = run(codes, 'egress', facts=[fact('storeys', 2)], confirmed_provisions=['9.1.1.1.'])
    selected = by_id(previous, '9.1.1.1.')
    selected.confirmation_reason, selected.confirmed_at, selected.role = 'Applicant supplied a rationale.', '2026-10-26T10:00:00Z', 'varied'
    unchanged = run(codes, 'egress', facts=[fact('storeys', 2)], previous=previous)
    row = by_id(unchanged, '9.1.1.1.')
    assert row.disposition == 'include' and row.applicability == 'confirmed' and not row.needs_review
    assert row.confirmation_reason == selected.confirmation_reason and row.confirmed_at == selected.confirmed_at
    # The parent supplies active facts, so replacement is provided, not conflict.
    changed = run(codes, 'egress', facts=[fact('storeys', 8)], previous=unchanged, confirmed_provisions=['9.1.1.1.'])
    row = by_id(changed, '9.1.1.1.')
    assert row.disposition == 'review' and row.applicability == 'needs_review' and row.human_confirmed
    assert row.role == 'varied' and row.confirmation_reason == selected.confirmation_reason and row.confirmed_at == selected.confirmed_at
    assert row.confirmation_fingerprint == previous.input_fingerprint
    assert next(c for c in row.conditions if c.field == 'storeys').status == 'provided'
    assert changed.input_fingerprint != previous.input_fingerprint
    rerun = run(codes, 'egress', facts=[fact('storeys', 8)], previous=changed, confirmed_provisions=['9.1.1.1.'])
    assert by_id(rerun, '9.1.1.1.').needs_review   # old selection cannot silently reconfirm itself


def test_source_change_preserves_human_history_and_missing_source_strips_current_citations(tmp_path):
    codes = database(tmp_path, [('B', '9.1.1.1.', 'Egress', ['Egress.'])])
    old = run(codes, 'egress', confirmed_provisions=['9.1.1.1.'])
    by_id(old, '9.1.1.1.').confirmation_reason = 'Human explanation.'
    with sqlite3.connect(codes.db_path) as con:
        con.execute("UPDATE provisions SET text='Egress changed.' WHERE id='9.1.1.1.(1)'")
    changed = run(codes, 'egress', previous=old)
    row = by_id(changed, '9.1.1.1.')
    assert row.needs_review and row.disposition == 'review' and row.confirmation_reason == 'Human explanation.'
    with sqlite3.connect(codes.db_path) as con:
        con.execute("UPDATE docs SET label='NBC(AE) 2023 p1'")
    unavailable = run(codes, 'egress', previous=changed)
    row = unavailable.requirements[0]
    assert row.human_confirmed and row.confirmation_reason == 'Human explanation.'
    assert row.source_status == 'unavailable' and row.provision_id is None and row.quote is None and row.citation is None
    assert unavailable.articles == [] and unavailable.requirement_evidence == []


def test_old_identify_results_load_additive_fields_as_not_run(tmp_path):
    result = run(database(tmp_path, [('B', '9.1.1.1.', 'Egress', ['Egress.'])]), 'egress')
    data = result.model_dump()
    for field in ('requirements', 'requirement_evidence', 'requirement_status', 'requirement_coverage',
                  'input_fingerprint', 'input_sha256', 'input_coverage_gaps'):
        data.pop(field)
    old = IdentifyResult.model_validate(data)
    assert old.requirements == [] and old.requirement_status == 'not_run'
    assert old.input_sha256 is None and old.input_coverage_gaps == []


def test_reference_lists_use_their_explicit_division_and_tables_are_not_articles(tmp_path):
    codes = database(tmp_path, [
        ('B', '9.1.1.1.', 'Seed', ['Seedword. See Articles 1.2.1.1. and 1.2.1.2. of Division A. See Table 9.1.1.2.']),
        ('A', '1.2.1.1.', 'First', ['Firstcontent.']),
        ('A', '1.2.1.2.', 'Second', ['Secondcontent.']),
        ('B', '1.2.1.1.', 'Wrong division', ['Wrongcontentone.']),
        ('B', '1.2.1.2.', 'Wrong division', ['Wrongcontenttwo.']),
        ('B', '9.1.1.2.', 'Unrelated article', ['Unrelatedcontent.']),
    ])
    result = run(codes, 'seedword')
    assert {(r.division, r.provision_id) for r in result.requirements} == {
        ('B', '9.1.1.1.'), ('A', '1.2.1.1.'), ('A', '1.2.1.2.')}


def test_missing_source_and_late_foreign_code_id_are_honest_gaps(tmp_path):
    codes = database(tmp_path, [('B', '9.1.1.1.', 'Unrelated', ['Unrelatedcontent.'])])
    foreign = run(codes, 'NFC(AE) 2023 p2, Article 9.1.1.1.')
    assert foreign.articles == []
    codes.db_path.unlink()
    result = run(codes, '9.1.1.1.')
    assert result.requirement_status == 'source_unavailable'
    assert result.articles == [] and result.requirement_coverage.scan_status == 'unavailable'
