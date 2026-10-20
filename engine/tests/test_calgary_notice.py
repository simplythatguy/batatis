"""Calgary's own variance form is a non-blocking notice. The SCC form still exports."""
import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from engine.api import create_app
from engine.completeness import calgary_form_gap
from engine.export.appendix import build_appendix
from engine.export.scc import ExportBlocked, ExportResult, blocking_gap_lines, export_case
from engine.jurisdiction_notice import CALGARY_FORM_NOTICE, calgary_form_notice
from engine.models import Case, Jurisdiction
from engine.store import CaseStore

NOTICE = (
    "Calgary's guide asks for its own Request for Specific Variance form. "
    "Confirm with your Safety Codes Officer which form they accept."
)


def _case(jurisdiction_id: str, name: str) -> Case:
    return Case(title='Synthetic notice fixture', jurisdiction=Jurisdiction(id=jurisdiction_id, name=name))


def _norm(text: str) -> str:
    return ' '.join(text.split())


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return _norm(' '.join((page.extract_text() or '') for page in reader.pages))


class _Plan:
    overflow: list = []
    rows_in_form = 0
    docs_in_form = 0


def _appendix(case: Case) -> bytes:
    return build_appendix(case, _Plan(), {}, {'version': 'test'}, codes=None, open_items=[])


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _stub_form(monkeypatch, blockers):
    from engine.export.scc import _Plan

    monkeypatch.setattr('engine.export.scc.load_form', lambda *args, **kwargs: _blank_pdf())
    monkeypatch.setattr('engine.export.scc._rects', lambda form, fmap: {})
    monkeypatch.setattr('engine.export.scc._plan', lambda case, values, fmap, rects: _Plan())
    monkeypatch.setattr('engine.export.scc._fill_and_flatten', lambda form, plan: (_blank_pdf(), []))
    monkeypatch.setattr('engine.export.scc._canonical_case', lambda current, codes: current)
    monkeypatch.setattr('engine.export.appendix.process_fields', lambda case, codes: [])
    monkeypatch.setattr('engine.export.scc.blockers', blockers)


def test_calgary_form_notice_exact_string():
    assert CALGARY_FORM_NOTICE == NOTICE
    assert calgary_form_notice(_case('calgary', 'City of Calgary')) == NOTICE
    assert calgary_form_notice(_case(' Calgary ', 'Calgary')) == NOTICE


def test_notice_does_not_claim_calgary_accepts_the_scc_form():
    folded = NOTICE.casefold()
    assert folded.count('accept') == 1
    assert 'which form they accept.' in folded
    assert 'calgary accepts' not in folded
    assert 'accepts the scc' not in folded
    assert 'scc form' not in folded


def test_edmonton_has_no_notice():
    assert calgary_form_notice(_case('edmonton', 'City of Edmonton')) is None
    assert calgary_form_notice(_case('alberta-other', 'City of Calgary')) is None
    assert calgary_form_notice(Case(title='no jurisdiction')) is None
    assert NOTICE not in _pdf_text(_appendix(_case('edmonton', 'City of Edmonton')))


def test_calgary_info_gap_does_not_block_export():
    gap = calgary_form_gap(_case('calgary', 'City of Calgary'))
    assert gap is not None
    assert gap.id == 'info:calgary_variance_form'
    assert gap.severity == 'info'
    assert gap.message == NOTICE
    assert blocking_gap_lines([gap], with_fix=True) == []
    assert calgary_form_gap(_case('edmonton', 'City of Edmonton')) is None
    assert 'calgary accepts' not in gap.fix_hint.casefold()
    assert 'accepts the scc' not in gap.fix_hint.casefold()


def test_calgary_appendix_carries_the_notice():
    text = _pdf_text(_appendix(_case('calgary', 'City of Calgary')))
    assert 'Local variance form' in text
    assert NOTICE in text
    assert 'calgary accepts' not in text.casefold()


def test_calgary_export_draft_and_final_carry_the_notice(monkeypatch):
    _stub_form(monkeypatch, lambda *args, **kwargs: [])
    for draft in (False, True):
        result = export_case(_case('calgary', 'City of Calgary'), draft=draft, codes=object())
        assert result.notice == NOTICE
        assert NOTICE in _pdf_text(result.pdf)
    edmonton = export_case(_case('edmonton', 'City of Edmonton'), draft=False, codes=object())
    assert edmonton.notice is None
    assert NOTICE not in _pdf_text(edmonton.pdf)


def test_calgary_notice_is_not_an_export_block_reason(monkeypatch):
    _stub_form(monkeypatch, lambda *args, **kwargs: ['required field "owner_name" is empty'])
    with pytest.raises(ExportBlocked) as error:
        export_case(_case('calgary', 'City of Calgary'), draft=False, codes=object())
    assert NOTICE not in ' '.join(error.value.reasons)
    draft = export_case(_case('calgary', 'City of Calgary'), draft=True, codes=object())
    assert draft.notice == NOTICE
    assert NOTICE in _pdf_text(draft.pdf)


def test_calgary_export_returns_200_with_notice(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / 'cases.sqlite')
    calgary = store.put(_case('calgary', 'City of Calgary'))

    def export_with_real_notice(current, draft=False, codes=None):
        return ExportResult(pdf=_appendix(current), field_map='test', form_pages=0, appendix_pages=1,
                            draft=draft, notice=calgary_form_notice(current))

    monkeypatch.setattr('engine.api.export_case', export_with_real_notice)
    client = TestClient(create_app(store=store, codes=object()))
    for body in (None, {'draft': True}):
        response = client.post(f'/cases/{calgary.id}/export', json=body)
        assert response.status_code == 200
        assert response.headers['x-batatis-notice'] == NOTICE
        assert NOTICE in _pdf_text(response.content)
        assert 'calgary accepts' not in _pdf_text(response.content).casefold()
    gaps = [calgary_form_gap(store.get(calgary.id))]
    assert gaps[0].severity == 'info'
    assert not any(gap.severity == 'blocking' for gap in gaps)


def test_edmonton_export_has_no_notice(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / 'cases.sqlite')
    edmonton = store.put(_case('edmonton', 'City of Edmonton'))

    def export_with_real_notice(current, draft=False, codes=None):
        return ExportResult(pdf=_appendix(current), field_map='test', form_pages=0, appendix_pages=1,
                            draft=draft, notice=calgary_form_notice(current))

    monkeypatch.setattr('engine.api.export_case', export_with_real_notice)
    client = TestClient(create_app(store=store, codes=object()))
    response = client.post(f'/cases/{edmonton.id}/export')
    assert response.status_code == 200
    assert 'x-batatis-notice' not in response.headers
    assert NOTICE not in _pdf_text(response.content)
    assert calgary_form_gap(store.get(edmonton.id)) is None
