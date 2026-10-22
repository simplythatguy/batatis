"""Actual API PDF round-trips, including multipart framing and bounded failures."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.privacy import PII_NOTICE
from engine.store import CaseStore
from engine.uploads import PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL


@pytest.fixture
def upload(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store=store))
    cid = client.post('/api/cases').json()['id']
    return client, store, cid


def multipart(boundary, parts):
    body = bytearray()
    for name, filename, data in parts:
        body += b'--' + boundary.encode() + b'\r\n'
        body += f'Content-Disposition: form-data; name="{name}"'.encode()
        if filename is not None:
            body += f'; filename="{filename}"\r\nContent-Type: application/pdf'.encode()
        body += b'\r\n\r\n' + data + b'\r\n'
    return bytes(body) + b'--' + boundary.encode() + b'--\r\n'


@pytest.mark.parametrize('boundary', ['lowercase_boundary', 'ReviewBoundaryABC', '----WebKitFormBoundaryAbC123'])
@pytest.mark.parametrize('prefix', ['', '/api'])
def test_multipart_file_selection_and_exact_binary_roundtrip(upload, boundary, prefix):
    client, store, cid = upload
    pdf = (b'%PDF-1.4\r\n\x00\xff\x80 binary\r\n--' + boundary.encode() +
           b'-like-but-not-a-delimiter\r\n%%EOF\r\n\r\n')
    body = multipart(boundary, [('description', None, b'preceding text'), ('file', 'plan.pdf', pdf),
                                ('after', None, b'following text')])
    response = client.post(f'{prefix}/cases/{cid}/files', content=body,
                           headers={'content-type': f'Multipart/Form-Data; boundary="{boundary}"; charset=utf-8'})
    assert response.status_code == 201, response.text
    assert response.json()['name'] == 'plan.pdf' and response.json()['size'] == len(pdf)
    assert store.get_file(cid, response.json()['id'])['data'] == pdf


@pytest.mark.parametrize('multipart_body', [False, True], ids=['raw', 'multipart'])
@pytest.mark.parametrize('extra', [0, 1], ids=['at-pdf-cap', 'over-pdf-cap'])
def test_pdf_payload_limit_excludes_bounded_multipart_framing(upload, multipart_body, extra):
    client, store, cid = upload
    pdf = b'%PDF' + b'x' * (PDF_MAX_BYTES - 4 + extra)
    body = multipart('BoundaryABC', [('file', 'limit.pdf', pdf)]) if multipart_body else pdf
    content_type = 'multipart/form-data; boundary=BoundaryABC' if multipart_body else 'application/pdf'
    response = client.post(f'/api/cases/{cid}/files', content=body, headers={'content-type': content_type})
    if extra:
        assert response.status_code == 413 and response.json()['detail'] == PDF_TOO_LARGE_DETAIL
    else:
        assert response.status_code == 201, response.text
        assert store.get_file(cid, response.json()['id'])['data'] == pdf


@pytest.mark.parametrize('malformation', ['missing-boundary', 'wrong-boundary', 'empty-boundary',
                                        'missing-close', 'text-only', 'multiple-files', 'invalid-headers'])
def test_malformed_multipart_rejected_without_storing_bytes(upload, malformation):
    client, store, cid = upload
    content_type = 'multipart/form-data; boundary=BoundaryABC'
    body = multipart('BoundaryABC', [('file', 'plan.pdf', b'%PDF synthetic')])
    if malformation == 'missing-boundary':
        content_type = 'multipart/form-data'
    elif malformation == 'wrong-boundary':
        content_type = 'multipart/form-data; boundary=DifferentBoundary'
    elif malformation == 'empty-boundary':
        content_type = 'multipart/form-data; boundary=""'
    elif malformation == 'missing-close':
        body = body.removesuffix(b'--BoundaryABC--\r\n')
    elif malformation == 'text-only':
        body = multipart('BoundaryABC', [('description', None, b'%PDF this is a text field')])
    elif malformation == 'multiple-files':
        body = multipart('BoundaryABC', [('file', 'one.pdf', b'%PDF one'), ('other', 'two.pdf', b'%PDF two')])
    else:
        body = body.replace(b'Content-Type: application/pdf', b'invalid header line')
    response = client.post(f'/api/cases/{cid}/files', content=body, headers={'content-type': content_type})
    assert response.status_code == 400, response.text
    assert response.json()['meta']['notice'] == PII_NOTICE
    assert response.headers.get_list('x-batatis-notice') == [PII_NOTICE]
    with sqlite3.connect(store.path) as con:
        assert con.execute('SELECT count(*) FROM case_files WHERE case_id=?', (cid,)).fetchone()[0] == 0


def test_multipart_metadata_and_part_counts_are_bounded(upload):
    client, store, cid = upload
    content_type = {'content-type': 'multipart/form-data; boundary=BoundaryABC'}
    for parts, expected in [([('description', None, b'x' * (64 * 1024)), ('file', 'plan.pdf', b'%PDF')], 413),
                            ([(f'field{i}', None, b'x') for i in range(33)] + [('file', 'plan.pdf', b'%PDF')], 400)]:
        response = client.post(f'/api/cases/{cid}/files', content=multipart('BoundaryABC', parts),
                               headers=content_type)
        assert response.status_code == expected, response.text
    with sqlite3.connect(store.path) as con:
        assert con.execute('SELECT count(*) FROM case_files WHERE case_id=?', (cid,)).fetchone()[0] == 0
