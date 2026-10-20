"""The export form is selected from the jurisdiction registry, not a hardcoded path."""
import hashlib
import json

import pytest

from engine.export.forms import resolve_form
from engine.export.scc import FormMismatch, load_form


def test_official_entry_records_the_october_form_and_not_appendix_1():
    spec = resolve_form()
    field_map = json.loads(spec.field_map_path.read_text())
    assert spec.version == 'scc_2026-10'
    assert spec.pdf_last_modified == '2026-10-06'
    assert spec.page_count == 5 and spec.field_count == 87
    assert spec.sha256 == field_map['sha256']
    assert 'Appendix 1' in spec.note
    assert 'approximately equivalent or greater safety performance' in spec.note
    if spec.local_path.is_file():
        assert hashlib.sha256(spec.local_path.read_bytes()).hexdigest() == spec.sha256


def test_a_second_registry_entry_is_addressable_and_sha_gated(tmp_path):
    pdf = tmp_path / 'toy.pdf'
    pdf.write_bytes(b'%PDF-1.4\n%toy form\n')
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    field_map = tmp_path / 'toy.json'
    field_map.write_text(json.dumps({'version': 'toy-1', 'sha256': digest}))
    registry = {
        'default': {'jurisdiction': 'example', 'form_id': 'toy-variance'},
        'forms': {
            'alberta': {'scc-variance': {
                'version': 'scc_2026-10', 'source_url': 'https://example.invalid/scc',
                'pdf_last_modified': '2026-10-06', 'page_count': 5, 'field_count': 87,
                'sha256': 'f' * 64, 'field_map': str(field_map), 'local_path': str(pdf), 'note': ''}},
            'example': {'toy-variance': {
                'version': 'toy-2099', 'source_url': 'https://example.invalid/toy',
                'pdf_last_modified': '2099-01-02', 'page_count': 1, 'field_count': 1,
                'sha256': digest, 'field_map': str(field_map), 'local_path': str(pdf),
                'note': 'portable second form'}},
        },
    }
    path = tmp_path / 'forms.json'
    path.write_text(json.dumps(registry))
    spec = resolve_form('example', 'toy-variance', registry=path)
    assert spec.version == 'toy-2099' and spec.pdf_last_modified == '2099-01-02'
    assert load_form(pdf, json.loads(field_map.read_text()), expected_sha=spec.sha256, label=spec.label)
    pdf.write_bytes(pdf.read_bytes() + b'\n%changed\n')
    with pytest.raises(FormMismatch, match='SHA-256'):
        load_form(pdf, {'version': 'toy-1', 'sha256': digest}, expected_sha=digest, label=spec.label)
