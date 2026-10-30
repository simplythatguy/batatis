"""The officer's Section D rows: blank form lines are not values, and one study is one row."""
from __future__ import annotations

from engine.models import Case, EvidenceItem
from engine.review.documents import attachment_row, case_rows
from engine.review.pdf_reader import PageText, ReadFile
from engine.tests.case_builder_fixtures import fact
from engine.models import Source


def read(text: str) -> ReadFile:
    file = ReadFile('study.pdf', 'sha', len(text), 1, 'attachment', text_pages=[PageText(0, text)])
    file._unreadable_cache = ()   # a text-only page: nothing drawn to look at
    return file


def test_a_label_with_its_blank_on_the_next_line_reads_as_unknown():
    row = attachment_row(read('SYNTHETIC engineering study\nPrepared by:\n________________\nDate: 2024-07-31\n'), 1)
    assert not row.issuer.known
    assert row.date.value == '2024-07-31'
    assert not attachment_row(read('Prepared by: ______\n'), 1).issuer.known
    assert attachment_row(read('Prepared by: SYNTHETIC Engineering Ltd.\n'), 1).issuer.value == 'SYNTHETIC Engineering Ltd.'


def test_a_study_listed_once_per_objective_is_one_row():
    def listing(eid, objective, file_id):
        return [fact(f'evidence.{eid}.{name}', value) for name, value in (
            ('title', 'SYNTHETIC City engineering study'), ('responsible_party', 'SYNTHETIC City'),
            ('date', 'v02, 31 July 2024'), ('objective', objective))] + [
            fact(f'evidence.{eid}.file_ref', file_id, source=Source(type='file', ref=file_id, quote='study.pdf'))]
    case = Case(evidence=[EvidenceItem(id='ev_os', objective='OS1.2', description='SYNTHETIC City engineering study'),
                          EvidenceItem(id='ev_op', objective='OP3.1', description='SYNTHETIC City engineering study')],
                facts=[*listing('ev_os', 'OS1.2', 'file_a'), *listing('ev_op', 'OP3.1', 'file_b'),
                       *listing('ev_other', 'OS1.2', 'file_c')[1:], fact('evidence.ev_other.title', 'SYNTHETIC drawing set')])
    rows = case_rows(case)
    assert [(row.id, row.file) for row in rows] == [('ev_op', 'file_b'), ('ev_other', 'file_c')]
