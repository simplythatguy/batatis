"""Failure containment at the PDF storage boundary."""
from pathlib import Path

import pytest

from engine.files import DEFAULT_MAX_BYTES, max_upload_bytes, save_pdf


@pytest.mark.parametrize('raw', ['', ' ', 'not-a-number', '0', '-1', '1.5', '1024'])
def test_upload_limit_uses_a_positive_integer_or_the_default(monkeypatch, raw):
    monkeypatch.setenv('BATATIS_FILE_MAX_BYTES', raw)
    assert max_upload_bytes() == (1024 if raw == '1024' else DEFAULT_MAX_BYTES)


@pytest.mark.parametrize('failure_point', ['write', 'replace'])
def test_failed_storage_removes_partial_files(tmp_path, monkeypatch, failure_point):
    monkeypatch.setenv('BATATIS_FILES', str(tmp_path))
    monkeypatch.setattr('engine.files._page_count', lambda _data: 1)
    failure = OSError('synthetic storage failure')
    original_write = Path.write_bytes

    def broken_write(path, data):
        original_write(path, data[:5])
        raise failure

    def broken_replace(*_args):
        raise failure

    monkeypatch.setattr(Path, 'write_bytes' if failure_point == 'write' else 'replace',
                        broken_write if failure_point == 'write' else broken_replace)
    with pytest.raises(OSError) as raised:
        save_pdf('case_fixture', 'plans.pdf', b'%PDF-synthetic')
    assert raised.value is failure
    assert not list(tmp_path.rglob('*.part'))
    assert not list(tmp_path.rglob('*.pdf'))


def test_invalid_case_id_is_rejected_before_parsing(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_FILES', str(tmp_path))

    def unexpected_parse(_data):
        pytest.fail('invalid case id reached PDF parsing')

    monkeypatch.setattr('engine.files._page_count', unexpected_parse)
    with pytest.raises(ValueError, match='invalid case id'):
        save_pdf('../escape', 'plans.pdf', b'%PDF-synthetic')
    assert not list(tmp_path.iterdir())
