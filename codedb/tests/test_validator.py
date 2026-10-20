import json
import subprocess
import sys
import pytest
from codedb import validate, validate_text

GOOD = 'NBC(AE) 2023 p2, Div B, Sentence 9.9.10.1.(1) [PDF p.873]. [F10-OS3.7] (Div B Table attribution, PDF p.1126)'


def codes(text):
    return [r['code'] for r in validate_text(text)['errors']]


def test_canonical_citation_and_separate_table_page():
    r = validate_text(GOOD)
    assert r['ok'] and r['citations_checked']==4 and not r['warnings']


@pytest.mark.parametrize('text,expected',[
    ('9.9.10.1.(99)','nonexistent_provision'),
    ('9.9.10.1.(1) [PDF p.100]','page_mismatch'),
    ('9.9.10.1.(1) [F10-OS1.5]','attribution_not_in_table'),
    ('Div C 2.3.1.1. [F10-OS3.7]','attribution_not_in_table'),
    ('9.9.10.1.(1) [F10-OS3.7] [PDF p.873]','page_mismatch'),
    ('1.2.1.1.(1)','ambiguous_division'),
    ('NBC(AE) 2019 Sentence 9.9.10.1.(1)','superseded_edition'),
    ('NBC(AE) 2023 first printing','superseded_edition'),
    ('NBC 2020 Article 9.9.10.1.','national_edition_as_law'),
    ('NFC(AE) 2023 p2 Article 9.9.9.9.','unsupported_document'),
    ('PDF p.9999','invalid_page'),
    ('Table 9.9.10.1.','nonexistent_table'),
    ('Table 9.23.3.5.-Z','nonexistent_table'),
    ('Table 9.23.3.5.-A [PDF p.100]','page_mismatch'),
])
def test_detects_invalid_citations(text, expected):
    assert expected in codes(text)


def test_lettered_table_resolves_by_its_letter():
    # Table 9.23.3.5.-A is printed on PDF p.966 of the 2023 2nd printing; the letter is part of the id.
    assert codes('Table 9.23.3.5.-A [PDF p.966]') == []
    assert codes('Table 9.23.3.5.-A.') == []


def test_2019_numbering_is_a_warning_and_a_bare_unknown_id_stays_an_error():
    r = validate_text('The 2019 text of 3.3.1.9.(7) allowed a 6 m dead end.')
    assert r['ok'] and [w['code'] for w in r['warnings']] == ['historical_number']
    assert validate_text('Sentence 3.2.2.50.(5) (2019) lets A-2 sit below the third storey.')['ok']
    assert codes('The Part 3 sentence 3.3.1.9.(7) allowed a 6 m dead end.') == ['nonexistent_provision']


def test_intent_label_later_in_a_row_does_not_recast_the_attribution_page():
    # The NBC-AE attribution page (p.1200) must not be checked against the later 2020 intent page.
    row = ('| 9.27.3.3.(1) sheathing membrane. Pairs [F61,F55-OS2.3] (Part 9 attribution table, PDF p.1200) | '
           'OS2.3 | F61 | Limit air infiltration. NBC 2020 Intent Statements, 9.27.3.3.(1) [PDF pp.2675 to 2676]. |\n')
    assert codes(row) == []


@pytest.mark.parametrize('text',[
    '23-BCV-001 CAN/ULC-S102 2026-10-18 v1.2.3 version 1.2.3.4',
    'Div C, Article 2.3.1.1. [PDF p.739]',
    'Section 9.9. and Subsection 9.9.10.',
    'NBC 2020 Intent Statements, 9.9.10.1.(1)',
    'NBC 2020 is explanatory context only.',
    'Never cite NBC(AE) 2019 or the first printing.',
    '9.9.10.1.(1) [PDF p.872]',
    '9.9.10.1.(1) [PDF p.874]',
    '9.9.10.1.(1)\n[F10-OS3.7] [PDF p.1126]',
])
def test_accepts_verified_and_noncode_text(text):
    assert validate_text(text)['ok']


def test_unbound_pair_is_warning_and_bad_pair_errors():
    r = validate_text('[F10-OS3.7]')
    assert r['ok'] and r['warnings'][0]['code']=='unbound_attribution'
    assert codes('[F999-OS9.9]')==['attribution_not_in_table']


def test_locations_and_files(tmp_path):
    good=tmp_path/'good.md'; good.write_text(GOOD)
    bad=tmp_path/'bad.yaml'; bad.write_text('title: example\ncitation: 9.99.99.99.\n')
    r=validate([good,bad])
    assert not r['ok'] and r['files_checked']==2
    assert r['errors'][0]['line']==2
    assert r['errors'][0]['path']==str(bad)
    assert validate(tmp_path/'missing.md')['errors'][0]['code']=='unreadable_file'
    assert validate(tmp_path)['files_checked']==2


def test_cli_exit_and_json(tmp_path):
    from engine.tests._db_skip import require_repo_db
    require_repo_db()
    p=tmp_path/'check.json';p.write_text(json.dumps({'citation':GOOD}))
    run=lambda:subprocess.run([sys.executable,'-m','codedb','validate',str(p),'--json'],text=True,capture_output=True)
    r=run();assert r.returncode==0 and json.loads(r.stdout)['ok']
    p.write_text('{"citation":"9.9.10.1.(99)"}')
    r=run();assert r.returncode==1 and not json.loads(r.stdout)['ok']


def test_structured_division_and_mixed_source_kinds():
    assert validate_text('{\n "doc": "NBC-AE",\n "division": "A",\n "id": "1.2.1.1.(1)"\n}')['ok']
    assert validate_text('NBC 2020 Intent Statements, 9.9.10.1.(1); NBC(AE) 2023 p2, Div B, '
                         '9.9.10.1.(1) [PDF p.873]')['ok']


@pytest.mark.parametrize('text',['9.9.10.1.(0)','9.9.10.1.4.'])
def test_malformed_identifiers_do_not_silently_pass(text):
    assert codes(text)==['malformed_provision']


def test_continued_table_and_intent_page():
    assert validate_text('Table 9.38.1.1. [PDF p.1126]')['ok']
    assert validate_text('NBC 2020 Intent Statements, 9.9.10.1.(1) [PDF p.1333]')['ok']
    assert codes('NBC 2020 Intent Statements, 9.9.10.1.(1) [PDF p.873]')==['page_mismatch']


def test_structured_version_numbers_are_not_provisions():
    assert validate_text('{"version": "1.2.3.4"}')['citations_checked']==0
    assert validate_text('version: 1.2.3.4')['citations_checked']==0


def test_clause_parent_and_unattributed_exception():
    assert validate_text('9.9.10.1.(2)(a) [F10-OS3.7] [PDF p.1126]')['ok']
    assert codes('3.2.2.20.(1) [F02-OS1.2]')==['attribution_not_in_table']


def test_current_build_validates_without_source_page_files(monkeypatch):
    import codedb.validator as validator
    def unavailable(*args):
        raise AssertionError('current SQLite build must carry its source page counts')
    monkeypatch.setattr(validator,'load_pages',unavailable)
    assert validator.validate_text(GOOD)['ok']


def test_cli_missing_database_is_setup_error(tmp_path):
    p=tmp_path/'check.md';p.write_text(GOOD)
    r=subprocess.run([sys.executable,'-m','codedb','--db',str(tmp_path/'missing.sqlite'),
                      'validate',str(p),'--json'],capture_output=True,text=True)
    assert r.returncode==2
    assert json.loads(r.stdout)['errors'][0]['code']=='command_error'


def test_nfc_article_is_located_in_text_but_not_certified():
    # NFC(AE) is not built into the database: an article printed in the NFC text is a warning, and its page is bound.
    r = validate_text('NFC(AE) 2023 p2 Article 6.1.1.2. [PDF p.313]')
    assert r['ok'] and [w['code'] for w in r['warnings']] == ['nfc_text_only']
    assert codes('NFC(AE) 2023 p2 Article 6.1.1.2. [PDF p.68]') == ['page_mismatch']
