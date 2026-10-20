"""Trimmed SCC appeal cases and their weak-label checks."""
import json
import sqlite3
from pathlib import Path

import pytest

from evals_dev.appeals.score_professional import (
    BASELINE, GOLD_ROWS, LINE, SYSTEM_COLS, VARIANTS, baseline_applies, confusion_rows,
    load_addressed, predict, render, score_cases,
)

from engine.section_d_flag_eval import load_codes
from evals_dev.appeals.checks import (
    LABEL_SOURCE, build_appeals_block, citation_resolution, engine_professional_flagger, professional_agreement,
)
from evals_dev.appeals.convert import WEAK_FLAG, convert_record, split_sentences
from evals_dev.appeals.mapping import attempt_mapping
from evals_dev.deterministic_checks import CODEDB_MISSING, build_report, load_schemas, score_citations
from evals_dev.stats import wilson_interval

CASES = Path(__file__).resolve().parents[1] / 'appeals' / 'cases'
DEV = Path(__file__).resolve().parents[1]
PROVISION = __import__('re').compile(r'\b\d{1,2}(?:\.\d{1,3}){2,}')


def _cases():
    """Load the committed appeal cases in stable order."""
    return [json.loads(path.read_text()) for path in sorted(CASES.glob('scc-*.json'))]


def test_converted_set_keeps_short_fields_and_no_2023_gold():
    """Verify converted set keeps short fields and no 2023 gold."""
    cases = _cases()
    assert len(cases) == 25
    editions = {}
    ocr = []
    for case in cases:
        editions[case['edition_original']] = editions.get(case['edition_original'], 0) + 1
        assert case['label_strength'] == 'weak'
        assert case['gold']['must_cite'] == []
        assert case['gold']['section_c'] == []
        assert case['gold']['engineering_citations'] == []
        assert case['source_url'].startswith('https://')
        assert 'pdf_path' not in case and 'text_path' not in case
        assert case['description'] and len(split_sentences(case['description'])) <= 2
        assert not PROVISION.search(case['description'])
        assert len(split_sentences(case['outcome_summary'])) <= 2
        for row in case['article_mapping']:
            assert row['nbc_ae_2023'] is None
            assert row['unmapped_reason']
        for quote in case['quotes']:
            assert quote['sentences'] <= 2
            assert len(split_sentences(quote['text'])) <= 2
            assert quote['source_url'] == case['source_url']
            if case['text_source_kind'] == 'ocr':
                assert quote['quote_confidence'] == 'low'
        if case['text_source_kind'] == 'ocr':
            ocr.append(case['id'])
    assert editions == {'ABC 2006': 18, 'ABC 2014': 1, 'NBC(AE) 2019': 5, 'unspecified': 1}
    assert len(ocr) == 4
    addressed = [case for case in cases if case['professional_involvement']['addressed']]
    assert len(addressed) == 12
    assert {case['id'] for case in addressed} == set(WEAK_FLAG)
    assert sum(case['professional_involvement']['weak_flag'] == 'yes' for case in addressed) == 5
    assert sum(case['professional_involvement']['weak_flag'] == 'depends' for case in addressed) == 7


def test_anchors_are_recorded_as_weak_labels():
    """Verify anchors are recorded as weak labels."""
    by_id = {case['id']: case for case in _cases()}
    section_c = by_id['scc-co-0015414-2012']
    assert 'objectives and functional statements' in section_c['quotes'][0]['text']
    assert section_c['quotes'][0]['quote_confidence'] == 'standard'
    info = by_id['scc-co-2022-06']['insufficient_information']
    assert info['source_provision'] == '2.2.10.8.(2)(b)'
    assert info['source_edition'] == 'NBC(AE) 2019'
    assert info['nbc_ae_2023'] is None and info['presented_as_2023'] is False
    assert by_id['scc-co-0015427-2012']['outcome'] == 'varied'
    assert by_id['scc-co-0015427-2012']['accepted_with_condition']['condition']
    assert by_id['scc-co-0015432-2013']['deference'] == 'officer_not_bound'
    assert by_id['scc-co-2024-06']['deference'] == 'issuer_must_not_dismiss_expert_without_competing_evidence'
    part10 = by_id['scc-co-0015414-2012']['article_mapping']
    assert any('Part 10' in row['unmapped_reason'] for row in part10)
    assert all(row['nbc_ae_2023'] is None for row in part10)


def test_same_identifier_is_not_promoted_to_a_2023_citation(tmp_path):
    """Verify same identifier is not promoted to a 2023 citation."""
    db = tmp_path / 'codedb.sqlite'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE provisions (doc TEXT, division TEXT, id TEXT, title TEXT)')
    con.execute("INSERT INTO provisions VALUES ('NBC-AE', 'B', '9.10.15.5.', 'Roof soffits')")
    con.commit()
    con.close()
    entry = {
        'source_article': '9.10.15.5.',
        'parsed_id': '9.10.15.5.',
        'source_division': 'B',
        'nbc_ae_2023': None,
        'method': None,
        'confidence': None,
        'unmapped_reason': 'pre-2023 citation; codedb was not available to compare titles or sentence text.',
    }
    mapped = attempt_mapping(entry, db)
    assert mapped['nbc_ae_2023'] is None
    assert mapped['method'] == 'same_identifier_in_codedb'
    assert mapped['confidence'] == 'insufficient'
    assert 'roof soffits' not in json.dumps(mapped).lower()
    missed = attempt_mapping(dict(entry, parsed_id='9.99.99.99.'), db)
    assert missed['nbc_ae_2023'] is None
    assert missed['confidence'] == 'none'


def test_professional_agreement_is_separate_and_not_forced(tmp_path):
    """Verify professional agreement is separate and not forced."""
    cases = _cases()
    skipped = professional_agreement(cases, None)
    assert skipped['label_source'] == LABEL_SOURCE
    assert skipped['decisions'] == 12
    assert skipped['weak_labels'] == {'yes': 5, 'depends': 7, 'no': 0}
    assert skipped['agreement']['skipped'] == CODEDB_MISSING
    # No stored fact produces a yes under the engine's own rules, so a depends screen hits the seven.
    depends = professional_agreement(cases, lambda case: 'depends')
    assert depends['agreement']['label'] == '7 of 12'
    assert depends['agreement']['wilson_95'] == wilson_interval(7, 12)
    echoed = professional_agreement(
        cases, lambda case: case['professional_involvement']['weak_flag'])
    assert echoed['agreement']['label'] == '12 of 12'
    block = build_appeals_block(cases, None, score_citations)
    assert block['label_source'] == LABEL_SOURCE
    assert block['section_c_anchor']['quote_recorded']['label'] == '1 of 1'
    assert block['section_c_anchor']['engine_flags_missing_section_c']['skipped'] == CODEDB_MISSING
    assert block['anchors']['insufficient_information_2022_06']['recorded']['label'] == '1 of 1'
    assert block['anchors']['accepted_with_condition_0015427']['recorded']['label'] == '1 of 1'
    assert block['anchors']['officer_deference_opposed']['recorded']['label'] == '1 of 1'
    report = build_report(
        root=tmp_path, db_path=None, cases=[], manifests=[], schemas=load_schemas(DEV / 'schemas'),
        appeals=cases, documents={'identify': []},
    )
    assert report['checks']['appeals']['label_source'] == LABEL_SOURCE
    assert 'model_grader_agreement' not in report
    assert report['checks']['appeals']['citation_resolution']['skipped'] == CODEDB_MISSING
    text = json.dumps(report)
    assert 'human-verified' not in text


def test_panel_conclusion_is_not_a_screen_fact_and_paraphrases_stay_summaries():
    by_id = {case['id']: case for case in _cases()}
    panel = by_id['scc-co-0015416-2012']['professional_involvement']
    assert panel['facts'] == {}
    assert 'weak yes label' in panel['facts_provenance']
    summaries = (
        'scc-co-0015439-2014', 'scc-co-2022-06', 'scc-co-0015427-2012',
        'scc-co-2023-03', 'scc-co-0015467-2016',
    )
    excerpts = ('scc-co-2024-06', 'scc-co-0015428-2012')
    for case_id in summaries:
        quotes = [quote for quote in by_id[case_id]['quotes'] if quote['field'] == 'professional_involvement']
        assert quotes and quotes[0]['kind'] == 'summary', case_id
    for case_id in excerpts:
        quotes = [quote for quote in by_id[case_id]['quotes'] if quote['field'] == 'professional_involvement']
        assert quotes and quotes[0]['kind'] == 'excerpt', case_id


def test_missing_division_c_skips_the_professional_screen(monkeypatch):
    from evals_dev.appeals.checks import engine_professional_flagger

    class EmptyCodes:
        def __init__(self, path):
            pass

        def provision(self, provision_id, division):
            return None

    monkeypatch.setattr('engine.codes.Codes', EmptyCodes)
    with pytest.raises(LookupError):
        engine_professional_flagger(Path('unused'))

    def missing(_path):
        raise LookupError('division C professional rules are not in codedb')

    monkeypatch.setattr('evals_dev.appeals.checks.engine_professional_flagger', missing)
    monkeypatch.setattr('evals_dev.appeals.checks.citation_resolution', lambda *args, **kwargs: {})
    monkeypatch.setattr('evals_dev.appeals.checks.section_c_anchor', lambda *args, **kwargs: {})
    monkeypatch.setattr('evals_dev.appeals.checks.other_anchors', lambda *args, **kwargs: {})
    block = build_appeals_block(
        [{'id': 'x', 'professional_involvement': {'addressed': True, 'weak_flag': 'yes'}}],
        Path('db'), score_citations)
    assert block['professional_involvement']['agreement']['skipped'] == 'skipped: engine unavailable (LookupError)'


def test_practice_screen_uses_stored_facts_and_not_the_label():
    """Verify practice screen uses stored facts and not the label."""
    cases = load_addressed()
    assert len(cases) == 12
    codes, _codedb = load_codes()
    original = cases[0]
    flipped = json.loads(json.dumps(original))
    flipped['professional_involvement']['weak_flag'] = 'no'
    flipped['gold']['engineering_required'] = 'no'
    flipped['description'] = 'This project is a Part 4 design under part 4 with an 18 m span.'
    flipped['known_facts'] = ['part 4 design', '18 m span']
    for variant in ('rules_only', 'rules_plus_unknown', 'always_unknown'):
        assert predict(original, codes, variant) == predict(flipped, codes, variant)
    totals = score_cases(cases, codes)
    assert confusion_rows(cases) == 'weak_label'
    assert baseline_applies(cases, totals)
    text = render(totals, rows=confusion_rows(cases), baseline=baseline_applies(cases, totals))
    assert LINE in text
    assert text.splitlines()[0] == LINE
    assert BASELINE in text
    assert 'rows=gold' not in text
    for name, row in totals.items():
        assert row['n'] == 12
        assert f'{name}: {row["matched"]}/12 ' in text
        assert f'decided: {row["n"] - row["unknown"]}/{row["n"]}' in text
        assert f'confusion {name}  rows=weak_label  columns=system yes unknown no' in text
        assert sum(sum(cols.values()) for cols in row['matrix'].values()) == 12
        assert f'unknown {name}: {row["unknown"]}' in text
        assert 'confident_wrong' in text
    assert 'decided: 0/12' in text
    assert totals['always_unknown']['unknown'] == 12
    assert totals['always_unknown']['confident_wrong'] == []
    depends = sum(case['professional_involvement']['weak_flag'] == 'depends' for case in cases)
    assert totals['always_unknown']['matched'] == depends


def _blank_totals(n=1, unknown=0, matched=0):
    """A zero matrix large enough for render()."""
    return {
        name: {
            'matched': matched,
            'n': n,
            'unknown': unknown,
            'confident_wrong': [],
            'matrix': {gold: {column: 0 for column in SYSTEM_COLS} for gold in GOLD_ROWS},
        }
        for name in VARIANTS
    }


def test_confusion_rows_follow_label_strength():
    """Weak labels print rows=weak_label. Any other strength stays rows=gold."""
    weak = {'professional_involvement': {'label_strength': 'weak', 'weak_flag': 'yes', 'facts': {}}}
    assert confusion_rows([weak]) == 'weak_label'
    reviewed = {'professional_involvement': {'label_strength': 'reviewed', 'weak_flag': 'yes', 'facts': {}}}
    assert confusion_rows([weak, reviewed]) == 'gold'
    assert baseline_applies([weak], _blank_totals()) is False
    weak_text = render(_blank_totals(), rows='weak_label')
    assert 'rows=weak_label' in weak_text
    assert 'rows=gold' not in weak_text
    assert BASELINE not in weak_text
    gold_text = render(_blank_totals(), rows='gold')
    assert 'confusion rules_only  rows=gold  columns=system yes unknown no' in gold_text
    assert 'rows=weak_label' not in gold_text
    assert 'decided: 1/1' in gold_text


def test_repo_holds_no_appeal_pdf_or_unattributed_excerpt():
    """Verify repo holds no appeal pdf or unattributed excerpt."""
    appeals = CASES.parent
    assert list(appeals.rglob('*.pdf')) == []
    for path in CASES.glob('*.json'):
        text = path.read_text()
        assert 'pdf_path' not in text
        assert 'text_path' not in text
    for case in _cases():
        assert case['source_url'].startswith('https://')
        for quote in case['quotes']:
            assert quote['source_url'].startswith('https://ebs.safetycodes.ab.ca/')
            assert len(split_sentences(quote['text'])) <= 2


def test_mapped_citation_resolves_only_after_a_2023_id_is_set(tmp_path):
    """Verify mapped citation resolves only after a 2023 id is set."""
    db = tmp_path / 'codedb.sqlite'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE provisions (doc TEXT, division TEXT, id TEXT)')
    con.execute("INSERT INTO provisions VALUES ('NBC-AE', 'C', '2.2.10.8.(2)')")
    con.execute("INSERT INTO provisions VALUES ('NBC-AE', 'B', '3.2.2.6.')")
    con.commit()
    con.close()
    case = {
        'id': 'example',
        'article_mapping': [{
            'parsed_id': '2.2.10.8.(2)',
            'source_division': 'C',
            'nbc_ae_2023': '2.2.10.8.(2)',
            'method': 'test_only',
            'confidence': 'high',
            'unmapped_reason': None,
        }],
    }
    row = citation_resolution([case], db, score_citations)
    assert row['label'] == '1 of 1'
    assert row['label_source'] == LABEL_SOURCE
    unmapped = citation_resolution(_cases(), db, score_citations)
    assert unmapped['n'] == 0
    assert unmapped['skipped'] == 'no mapped NBC(AE) 2023 citations'
    assert unmapped['mapping']['same_identifier_not_promoted'] > 0


@pytest.mark.parametrize('text,kind', [
    ("The engineer's slope stability study was requested.", 'summary'),
    ("The appellant's Code Review Report was inadequate.", 'summary'),
    ("A professional engineer's code review was supplied.", 'summary'),
    ("Professional Engineer's 6 April 2016 letter was supplied.", 'summary'),
    ("Appellant relied on a 'safety specialist'.", 'summary'),
    ("The panel relied on 'the professional opinion of the engineer'.", 'summary'),
    ("'The panel required professional involvement.'", 'excerpt'),
    ('  “The panel required professional involvement.”', 'excerpt'),
    ('“The engineer’s review was requested.”', 'excerpt'),
])
def test_converter_distinguishes_paraphrases_from_opening_quotes(text, kind):
    """Possessives and embedded fragments do not make researcher prose an excerpt."""
    rec = {'id': 'synthetic-appeal', 'professional_involvement': text,
           'refusal_reason_evidence': "The appellant's paraphrase."}
    case = convert_record(rec, {'professional_involvement_addressed': False})
    quotes = {q['field']: q for q in case['quotes']}
    assert quotes['professional_involvement']['kind'] == kind
    assert quotes['refusal_reason_evidence']['kind'] == 'excerpt'


def test_panel_conclusion_is_excluded_from_professional_inputs():
    """Both conversion and the stored case exclude facts that overlap the weak label."""
    original = next(c for c in _cases() if c['id'] == 'scc-co-0015416-2012')
    regenerated = convert_record({'id': original['id']}, {'professional_involvement_addressed': True})
    for case in (original, regenerated):
        assert case['professional_involvement']['facts'] == {}
        assert case['professional_involvement']['weak_flag'] == 'yes'
        assert 'panel conclusion' in case['authoring']['notes']
        assert 'not an independent authority statement' in case['authoring']['notes']


def test_committed_quote_kinds_match_converter():
    """Reclassifying retained professional text agrees with every committed case."""
    for case in _cases():
        for quote in case['quotes']:
            rec = {'id': case['id'], quote['field']: quote['text']}
            converted = convert_record(rec, {
                'professional_involvement_addressed': case['professional_involvement']['addressed'],
            })
            match = next(q for q in converted['quotes'] if q['field'] == quote['field'])
            assert match['kind'] == quote['kind'], case['id']


@pytest.mark.parametrize('sentinel_present', [False, True])
def test_incomplete_division_c_rules_skip_instead_of_crashing_report(tmp_path, monkeypatch, sentinel_present):
    """Missing all or part of Division C skips affected checks while keeping the report usable."""
    from codedb.store import SCHEMA

    db = tmp_path / 'codedb.sqlite'
    with sqlite3.connect(db) as con:
        con.executescript(SCHEMA)
        con.execute("INSERT INTO docs (doc, label) VALUES ('NBC-AE', 'Synthetic code fixture')")
        if sentinel_present:
            con.execute("INSERT INTO provisions (doc, division, id, level, pdf_page) "
                        "VALUES ('NBC-AE', 'C', '2.4.1.1.(1)', 'sentence', 1)")
    monkeypatch.setenv('BATATIS_CODEDB', str(db))
    with pytest.raises(LookupError, match='missing professional-involvement provision'):
        engine_professional_flagger(db)
    block = build_appeals_block(_cases(), db, score_citations)
    assert block['professional_involvement']['agreement']['n'] == 0
    assert 'LookupError' in block['professional_involvement']['agreement']['skipped']
    assert block['section_c_anchor']['engine_flags_missing_section_c']['skipped']
    report = build_report(root=DEV, db_path=db, cases=[], manifests=[],
                          schemas=load_schemas(DEV / 'schemas'), appeals=_cases())
    assert report['checks']['appeals']['professional_involvement']['agreement']['skipped']
