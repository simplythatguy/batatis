"""Appendix explainer, Section D statements, intent text, role, scope question, and edition label.

These tests do not open the SCC form PDF and do not require the code database.
Nothing here is a finding that a design complies or is safe.
"""
import json
import sqlite3

from engine.completeness import check_completeness
from engine.export.appendix import build_appendix
from engine.export.article_notes import NRC_NBC_AE_2023, notes_for, snippet
from engine.export.edition import EDITION_PLAIN, EDITION_PROVEN, code_or_standard_value, edition_label
from engine.export.scc import load_field_map, owner_representative_name
from engine.export.text import CONTINUED_IN_APPENDIX, fit_words
from engine.models import Case, Fact, SectionCRow, Source
from engine.section_d import applicant_statements, supply_status, supporting_documents


class _Codes:
    """Lookup stand-in. Citations here are fixtures, not code text."""

    db_path = None

    def __init__(self, text=' '.join(f'w{i}' for i in range(1, 41)), known=None):
        self.text = text
        self.known = known

    def provision(self, provision_id, division=None):
        if self.known is not None and provision_id not in self.known:
            return None
        return {'id': provision_id, 'text': self.text, 'citation': 'fixture citation',
                'article': provision_id, 'article_title': 'Fixture'}

    def citation(self, provision_id, division=None):
        rec = self.provision(provision_id, division)
        return rec['citation'] if rec else None


def _fact(field, value, source_type='user_text', ref='applicant', status='confirmed', kind='pointed'):
    return Fact(field=field, value=value, kind=kind, status=status,
                source=Source(type=source_type, ref=ref))


def _row(provision_id='9.10.1.1.(1)'):
    return SectionCRow(provision_id=provision_id, citation='fixture citation',
                       attribution_status='direct', pairs=[], intents=[])


def _case(*facts, provision='9.10.1.1.(1)'):
    return Case(title='Synthetic appendix case', facts=list(facts), section_c=[_row(provision)])


def test_snippet_is_at_most_25_words_and_keeps_the_provision_id():
    codes = _Codes()
    note = notes_for(_case(), _row(), codes)
    quoted = snippet(codes.text)
    assert len(quoted.split()) == 25
    assert 'w26' not in note.explainer
    assert 'w25' in note.explainer
    assert note.explainer.startswith('9.10.1.1.(1):')
    assert note.citation == 'fixture citation'
    assert note.source_url == NRC_NBC_AE_2023
    assert '2nd printing' not in note.explainer
    assert 'complies' not in note.explainer.lower()
    assert note.benchmark.startswith('The benchmark acceptable solution is 9.10.1.1.(1).')
    assert 'w26' not in note.benchmark


def test_stored_identify_quote_is_used_only_when_it_is_codedb_text():
    codes = _Codes(text='alpha beta gamma delta')
    kept = _case(_fact('identify.9.10.1.1.(1).explainer', 'alpha beta'))
    note = notes_for(kept, kept.section_c[0], codes)
    assert 'alpha beta' in note.explainer
    invented = _case(_fact('identify.9.10.1.1.(1).explainer', 'INVENTED SENTENCE NOT IN THE DATABASE'))
    rejected = notes_for(invented, invented.section_c[0], codes)
    assert 'INVENTED SENTENCE' not in rejected.explainer
    assert 'alpha beta gamma delta' in rejected.explainer


def test_missing_database_and_unknown_benchmark_do_not_invent_a_citation():
    bare = notes_for(_case(), _row(), None)
    assert bare.citation is None
    assert bare.source_url is None
    assert 'No citation is supplied' in bare.explainer
    assert '9.99.99.99' not in bare.explainer
    codes = _Codes(known={'9.10.1.1.(1)'})
    case = _case(_fact('benchmark_acceptable_solution', '9.99.99.99.(1)'))
    note = notes_for(case, case.section_c[0], codes)
    assert '9.99.99.99' not in note.benchmark
    assert 'not in the code database' in note.benchmark
    assert 'No citation is given' in note.benchmark


def test_user_typed_statement_is_provided_and_not_verified():
    case = Case(facts=[
        _fact('evidence.note-1.statement', 'The applicant describes a synthetic attachment.'),
        _fact('evidence.note-1.title', 'Synthetic note'),
        _fact('evidence.sealed.statement', 'A file is not a typed statement.', source_type='file', ref='file_abc'),
    ])
    statements = applicant_statements(case)
    assert len(statements) == 1
    assert statements[0].label == 'stated by applicant, not verified'
    assert statements[0].title == 'Synthetic note'
    assert not hasattr(statements[0], 'professional_seal')
    assert supply_status(False, True) == 'provided'
    assert supply_status(False, False) == 'not provided'
    assert 'verified' not in supply_status(True, True)


def test_upload_fact_from_the_case_api_is_a_file_sourced_document():
    """POST /cases/{id}/files on #21 writes file.{id}.name. This branch reads that fact."""
    case = Case(facts=[_fact('file.file_abc123.name', 'sheet.pdf', source_type='file', ref='file_abc123', kind='exact')])
    docs = supporting_documents(case)
    assert len(docs) == 1
    assert docs[0].id == 'file_abc123'
    assert docs[0].title == 'sheet.pdf'
    assert docs[0].file.type == 'file'
    assert docs[0].file.ref == 'file_abc123'
    mismatched = Case(facts=[_fact('file.file_abc123.name', 'sheet.pdf', source_type='file', ref='other')])
    assert supporting_documents(mismatched) == []


def test_intent_cell_uses_intent_text_cut_on_a_word_boundary():
    words = ' '.join(f'intent{i}' for i in range(1, 80))
    shown = fit_words(words, (0, 0, 140, 22))
    assert shown.startswith('intent1')
    assert '(continued in appendix)' in shown
    assert pdf_safe_ellipsis()
    assert not any(token.endswith('inten') for token in shown.split())
    full = fit_words('short intent', (0, 0, 400, 80))
    assert full == 'short intent'
    assert '(continued in appendix)' not in full


def pdf_safe_ellipsis():
    assert '…' in CONTINUED_IN_APPENDIX
    return True


def test_applicant_name_fills_owner_rep_only_after_the_role_is_confirmed():
    name = {'applicant_name': 'Ada Applicant'}
    assert owner_representative_name(name) is None
    confirmed = {**name, 'applicant_role': 'owner_representative'}
    assert owner_representative_name(confirmed) == 'Ada Applicant'
    explicit = {'owner_rep_name': 'Named Representative', 'applicant_name': 'Ada Applicant'}
    assert owner_representative_name(explicit) == 'Named Representative'

    codes = _Codes()
    named = Case(facts=[_fact('applicant_name', 'Ada Applicant')])
    gaps = {gap.field for gap in check_completeness(named, codes)}
    assert 'applicant_role' in gaps
    role = named.model_copy(deep=True)
    role.facts.append(_fact('applicant_role', 'owner_representative'))
    assert 'applicant_role' not in {gap.field for gap in check_completeness(role, codes)}
    question = next(gap for gap in check_completeness(named, codes) if gap.field == 'applicant_role')
    assert question.message.startswith('Your application appears to be missing ')
    assert 'complies' not in question.message.lower()


def test_not_site_specific_is_a_fact_and_a_gap_until_answered():
    codes = _Codes()
    empty = Case()
    gap = next(item for item in check_completeness(empty, codes) if item.field == 'not_site_specific')
    assert 'not site-specific' in gap.message
    assert 'Safety Codes Council' in gap.fix_hint
    assert 'submitted_to_scc' not in gap.field
    for value in (True, False):
        answered = Case(facts=[_fact('not_site_specific', value)])
        assert 'not_site_specific' not in {item.field for item in check_completeness(answered, codes)}


def test_edition_says_second_printing_only_when_the_manifest_proves_it(tmp_path):
    assert edition_label(None) == EDITION_PLAIN
    assert '2nd printing' not in load_field_map()['text_fields']['Code or Standard']['default']
    assert code_or_standard_value('National Building Code - 2023 Alberta Edition (2nd printing)', None) == EDITION_PLAIN

    plain = tmp_path / 'plain.sqlite'
    _manifest(plain, 'NBC(AE) 2023')
    proven = tmp_path / 'proven.sqlite'
    _manifest(proven, 'NBC(AE) 2023 p2')

    class Db:
        def __init__(self, path):
            self.db_path = path

    assert edition_label(Db(plain)) == EDITION_PLAIN
    assert edition_label(Db(proven)) == EDITION_PROVEN
    assert '2nd printing' in code_or_standard_value(None, Db(proven))


def test_appendix_carries_the_explainer_and_benchmark_without_a_printing_claim():
    case = _case()
    plan = type('Plan', (), {'overflow': [], 'rows_in_form': 1, 'docs_in_form': 0})()
    pdf = build_appendix(case, plan, {}, {'version': 'scc_2026-10'}, codes=_Codes(), open_items=[])
    text = _pdf_text(pdf)
    assert 'Explainer' in text
    assert 'Benchmark acceptable solution' in text
    assert NRC_NBC_AE_2023 in text
    assert 'w26' not in text.split('Provision text')[0]
    assert '2nd printing' not in text
    assert 'does not state that the proposed design complies' in text


def _manifest(path, label):
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
    con.execute("INSERT INTO meta VALUES ('stats', ?)", (json.dumps({'sources': {'NBC-AE': {'label': label}}}),))
    con.commit()
    con.close()


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    import io
    return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages)
