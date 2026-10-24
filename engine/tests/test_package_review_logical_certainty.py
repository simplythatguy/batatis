"""Uncertain component cells cannot become logical applicant blanks or attribution mismatches."""
import io

import pytest
from pypdf import PdfWriter

from engine.codes import Codes
from engine.export import scc
from engine.review import information_request as ir
from engine.review.package import review_uploads
from engine.tests.package_review_fixtures import CLEAN_FORM, fillable


def hidden_cell(name, values=None):
    writer = PdfWriter(clone_from=io.BytesIO(fillable(values or CLEAN_FORM)))
    widget = next(w for _p, field, w in scc._widgets(writer.pages) if field == name)
    appearance = widget['/AP']['/N']
    appearance.set_data(appearance.get_data().replace(b'BT', b'BT 3 Tr'))
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def assert_excluded(parts, field, cell):
    reading = next(x for x in parts.fields if x.field == cell)
    assert reading.status == 'not_found' and reading.value is None and reading.pointer.quote is None
    finding = next(x for x in parts.findings if x.field == field)
    assert finding.status == 'not_found'
    assert [(p.file, p.page, p.form_field, p.quote) for p in finding.pointers] == [('form.pdf', 1, cell, None)]
    item = next(x for x in ir.build(parts.findings).items if x.finding_key == finding.key)
    assert not item.included and item.officer_check and finding.key not in ir.open_gaps(parts.findings)


@pytest.mark.parametrize('cell', ['Lot', 'Block', 'Plan'])
def test_partial_legal_description_preserves_uncertain_components(cell):
    parts = review_uploads([('form.pdf', hidden_cell(cell))], None)
    assert_excluded(parts, 'legal_description', cell)


@pytest.mark.parametrize('cell', ['Objective', 'Function'])
def test_uncertain_pair_cell_prevents_a_table_comparison(cell):
    parts = review_uploads([('form.pdf', hidden_cell(cell))], Codes())
    assert_excluded(parts, 'section_c.row1.pair', cell)
    assert parts.section_c[0].status == 'not_checked'
    assert parts.section_c[0].pointer.form_field == cell


def test_complete_alternative_legal_group_remains_readable():
    values = dict(CLEAN_FORM, QTR='NW', SEC='1', TWP='2', RGE='3', MER='4')
    parts = review_uploads([('form.pdf', hidden_cell('Block', values))], None)
    assert not any(x.field == 'legal_description' for x in parts.findings)


def test_genuinely_empty_legal_component_remains_an_applicant_gap():
    parts = review_uploads([('form.pdf', fillable(dict(CLEAN_FORM, Block='')))], None)
    finding = next(x for x in parts.findings if x.field == 'legal_description')
    assert finding.status == 'blank'
    assert next(x for x in ir.build(parts.findings).items if x.finding_key == finding.key).included


def test_genuinely_empty_objective_remains_a_table_mismatch():
    parts = review_uploads([('form.pdf', fillable(dict(CLEAN_FORM, Objective='')))], Codes())
    assert parts.section_c[0].status == 'mismatch'
    finding = next(x for x in parts.findings if x.field == 'section_c.row1.pair')
    assert finding.problem == 'pair_mismatch'
    assert next(x for x in ir.build(parts.findings).items if x.finding_key == finding.key).included


def test_unreadable_supplement_cannot_establish_a_missing_coordinator():
    from engine.tests.package_review_fixtures import scanned, text_pdf

    values = dict(CLEAN_FORM, **{'Supporting Doc2': 'SYNTHETIC second document',
                                'Name Responsible2': 'SYNTHETIC second firm'})
    supplement = scanned(text_pdf(['SYNTHETIC single co-ordinator: fictional person']))
    parts = review_uploads([('form.pdf', fillable(values)), ('supplement.pdf', supplement)], None)
    finding = next(x for x in parts.findings if x.field == 'div_c.coordinator')
    assert finding.status == 'not_found' and 'Ask the applicant' not in finding.message
    assert [(p.file, p.page, p.quote) for p in finding.pointers] == [('supplement.pdf', 1, None)]
    item = next(x for x in ir.build(parts.findings).items if x.finding_key == finding.key)
    assert item.officer_check and not item.included and finding.key not in ir.open_gaps(parts.findings)
