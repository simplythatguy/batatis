"""Explicit curation must govern both the assembled packet and grouping."""
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize('role,included', [('outcome_reference', True), ('supporting_evidence', False)])
def test_assembled_packet_honors_explicit_input_selection(tmp_path, monkeypatch, role, included):
    tools = Path(__file__).resolve().parents[2] / 'Data Prompts' / '_tools'
    monkeypatch.syspath_prepend(str(tools))
    spec = importlib.util.spec_from_file_location('corpus_assembler_under_test', tools / 'assemble.py')
    assembler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(assembler)
    monkeypatch.setattr(assembler, 'BASE', tmp_path)
    geography = {'country': 'Canada', 'province_or_state': 'Alberta', 'city_or_town': 'Calgary'}
    monkeypatch.setattr(assembler, 'load_geography', lambda base: {'TEST-001': geography})
    monkeypatch.setattr(assembler, 'case_folder', lambda case, location: 'test-case')
    worker = tmp_path / '_research' / 'workers' / 'TEST'
    worker.mkdir(parents=True)
    # These are labelled unit fixtures, never corpus additions or applicant records.
    files = []
    for name, selected_role in (('reference.txt', role), ('packet.txt', 'input')):
        path = worker / name
        path.write_text('Unit fixture: no real applicant or professional evidence. ' + name)
        item = {'path': str(path), 'url': 'https://example.invalid/' + name, 'role': selected_role}
        if name == 'reference.txt':
            item['included_in_default_input'] = included
        files.append(item)
    case = {'id': 'TEST-001', 'title': 'Unit fixture', 'jurisdiction': 'Calgary, Alberta',
            'case_type': 'issued_variance', 'source_url': 'https://example.invalid/fixture',
            'prompt': 'Unit fixture only.', 'facts': [{'text': 'Unit fixture.', 'locator': 'line 1'}],
            'attachments': files}
    (worker / 'candidates.json').write_text(json.dumps({'cases': [case]}))
    assembler.main()
    folder = tmp_path / 'test-case'
    source = json.loads((folder / 'source.json').read_text())
    reference = next(a for a in source['attachments'] if a['url'].endswith('/reference.txt'))
    assert reference['included_in_default_input'] is included
    assert reference['filename'] == ('reference.txt' if included else '_evaluation/reference.txt')
    listed = (folder / 'prompt.txt').read_text().split('Attachments:\n')[1].split('\n\n')[0]
    assert ('- reference.txt' in listed) is included
