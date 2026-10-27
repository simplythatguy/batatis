"""SYNTHETIC HTTP regressions for upload identity and native Division C uncertainty."""
from __future__ import annotations

import hashlib
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from engine.account_models import User
from engine.accounts import COOKIE, digest
from engine.api import create_app
from engine.codes import Codes
from engine.export import scc
from engine.store import CaseStore
from engine.tests.package_review_fixtures import fillable, text_pdf

COORDINATOR = 'Single co-ordinator: SYNTHETIC Pat Example'
PREFIX = 'SYNTHETIC visible prefix only.'


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    store = CaseStore(tmp_path_factory.mktemp('upload-certainty') / 'cases.sqlite')
    user = User(id='synthetic-officer', email='synthetic@example.test', name='Synthetic officer',
                role='reviewer', authority='edmonton', onboarded=True)
    store.create_user(user)
    token = 'synthetic_upload_certainty_token'.ljust(43, '_')
    store.save_session(digest(token), user.id, time.time() + 3600)
    with TestClient(create_app(store=store, codes=Codes()), base_url='http://localhost') as http:
        http.cookies.set(COOKIE, token)
        yield http


def review(client, files):
    response = client.post('/package-review', files=[
        ('files', (name, data, 'application/pdf')) for name, data in files])
    assert response.status_code == 201, response.text
    result = response.json()
    stored = client.get('/package-review/' + result['package_id'])
    assert stored.status_code == 200, stored.text
    saved = stored.json()
    assert saved['latest'] == {key: value for key, value in result.items() if key != 'meta'}
    assert saved['sessions'][0]['required'] == saved['workspace']['tally']['required']
    return result


def officer_check(result, field, pointer, others=()):
    finding = next(item for item in result['findings'] if item['field'] == field)
    assert finding['status'] == 'not_found'
    assert finding['pointers'] == [pointer, *others]
    request = result['information_request']
    item = next(item for item in request['items'] if item['finding_key'] == finding['key'])
    assert item['officer_check'] and not item['included']
    assert item['text'] not in request['text']


def risk_pdf(*, raster=False, prefix=False):
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=(612, 792))
    c.setFont('Helvetica', 11)
    c.drawString(50, 740, 'Risk assessment')
    if prefix:
        c.drawString(50, 720, PREFIX)
    if raster:
        image = Image.new('RGB', (1000, 60), 'white')
        ImageDraw.Draw(image).text((6, 10), 'SYNTHETIC RISK ANSWER IN IMAGE', fill='black', font_size=30)
        c.drawImage(ImageReader(image), 50, 680, 500, 30)
    c.drawString(50, 650, 'Mitigating measures')
    c.drawString(50, 630, 'SYNTHETIC other answer.')
    c.drawString(50, 600, 'Code analysis')
    c.save()
    return output.getvalue()


@pytest.mark.parametrize('prefix', [False, True], ids=['raster', 'prefix-and-raster'])
@pytest.mark.parametrize('names', [
    ['report.pdf', 'other.pdf'],
    ['report.pdf', 'report.pdf'],
    ['a/report.pdf', 'a\\report.pdf'],
    ['report.pdf', 'report.pdf', 'report (2).pdf'],
    ['x' * 196 + '.pdf', 'x' * 196 + '.pdf'],
], ids=['distinct', 'duplicate', 'sanitized-collision', 'reserved-suffix', 'maximum-length'])
def test_upload_identity_keeps_raster_passage_uncertain_in_saved_review(client, prefix, names):
    first, second = risk_pdf(raster=True, prefix=prefix), risk_pdf(prefix=prefix)
    data = [first, second, text_pdf(['SYNTHETIC separate third upload.'])][:len(names)]
    result = review(client, list(zip(names, data)))
    reading = next(item for item in result['fields'] if item['field'] == 'risk_assessment')
    assert reading['status'] == 'not_found' and reading['value'] is None
    # Only the heading that locates the passage may be quoted, never words of the unestablished answer.
    assert reading['pointer']['quote'] in (None, 'Risk assessment')
    actual_names = [file['name'] for file in result['files']]
    assert len(set(actual_names)) == len(names), 'Each retained upload needs an unambiguous source name.'
    assert all(len(name) <= 200 for name in actual_names)
    assert [(file['sha256'], file['size']) for file in result['files']] == [
        (hashlib.sha256(pdf).hexdigest(), len(pdf)) for pdf in data]
    # Both labelled uploads are candidates; neither upload order nor name picks one. Each keeps its own identity.
    finding = next(item for item in result['findings'] if item['field'] == 'risk_assessment')
    assert finding['pointers'][0] == reading['pointer']
    assert sorted((p['file'], p['page']) for p in finding['pointers']) == sorted(
        [(actual_names[0], 1), (actual_names[1], 1)])
    officer_check(result, 'risk_assessment', reading['pointer'], finding['pointers'][1:])
    if len(names) == 3:
        assert actual_names[2] == 'report (2).pdf', 'A generated suffix must not take another supplied name.'


def test_duplicate_name_pointer_identifies_the_second_actual_upload(client):
    result = review(client, [('report.pdf', text_pdf(['SYNTHETIC cover.'])),
                             ('report.pdf', risk_pdf(raster=True))])
    first, second = result['files']
    assert first['name'] != second['name']
    reading = next(item for item in result['fields'] if item['field'] == 'risk_assessment')
    assert reading['status'] == 'not_found' and reading['value'] is None
    assert reading['pointer']['file'] == second['name'] and reading['pointer']['page'] == 1
    officer_check(result, 'risk_assessment', reading['pointer'])


@pytest.mark.parametrize('prefix', [False, True], ids=['blank', 'readable'])
def test_duplicate_readable_uploads_keep_the_known_passage_and_both_sources(client, prefix):
    data = risk_pdf(prefix=prefix)
    result = review(client, [('report.pdf', data), ('report.pdf', data)])
    reading = next(item for item in result['fields'] if item['field'] == 'risk_assessment')
    assert reading['status'] == ('present' if prefix else 'blank')
    assert reading['value'] == (PREFIX if prefix else None)
    assert len({file['name'] for file in result['files']}) == 2
    assert all(file['sha256'] == hashlib.sha256(data).hexdigest() for file in result['files'])


def coordinator_form(kind, cell='Name Responsible3'):
    values = {'Owner': 'SYNTHETIC owner', 'Supporting Doc': 'SYNTHETIC first report',
              'Name Responsible': 'SYNTHETIC Firm One', 'Supporting Doc2': 'SYNTHETIC second report',
              'Name Responsible2': 'SYNTHETIC Firm Two', 'Supporting Doc3': 'SYNTHETIC third report',
              'Name Responsible3': COORDINATOR if kind == 'text' else ''}
    if kind == 'raster':
        values[cell] = ''
    writer = PdfWriter(clone_from=io.BytesIO(fillable(values)))
    page_no, _, widget = next(item for item in scc._widgets(writer.pages) if item[1] == cell)
    rect = tuple(map(float, widget['/Rect']))
    if kind == 'raster':
        image = Image.new('RGB', (1100, 55), 'white')
        ImageDraw.Draw(image).text((2, 8), COORDINATOR, fill='black', font_size=32)
        overlay = io.BytesIO()
        c = canvas.Canvas(overlay, pagesize=(612, 792))
        c.drawImage(ImageReader(image), rect[0] + 1, rect[1] + 1,
                    rect[2] - rect[0] - 2, rect[3] - rect[1] - 2)
        c.save()
        writer.pages[page_no].merge_page(PdfReader(io.BytesIO(overlay.getvalue())).pages[0])
    output = io.BytesIO()
    writer.write(output)
    pointer = {'file': 'form.pdf', 'page': page_no + 1, 'form_field': cell,
               'bbox': [round(value, 1) for value in rect], 'quote': None}
    return output.getvalue(), pointer


@pytest.mark.parametrize('cell', ['Name Responsible3', 'Supporting Doc3'])
def test_native_coordinator_uncertainty_keeps_its_exact_cell_in_saved_review(client, cell):
    data, pointer = coordinator_form('raster', cell)
    result = review(client, [('form.pdf', data)])
    reading = next(item for item in result['fields'] if item['field'] == cell)
    assert reading['status'] == 'not_found' and reading['value'] is None
    assert reading['pointer'] == pointer
    assert pointer['page'] == 2
    officer_check(result, 'div_c.coordinator', pointer)


def test_native_text_coordinator_is_found_in_saved_review(client):
    data, _ = coordinator_form('text')
    result = review(client, [('form.pdf', data)])
    reading = next(item for item in result['fields'] if item['field'] == 'Name Responsible3')
    assert reading['status'] == 'present' and reading['value'] == COORDINATOR
    assert not any(item['field'] == 'div_c.coordinator' for item in result['findings'])


@pytest.mark.parametrize('cell', [None, 'Signature1', 'Owner'], ids=['absent', 'unrelated-signature', 'unrelated-owner'])
def test_known_coordinator_absence_stays_an_applicant_gap_despite_unrelated_uncertainty(client, cell):
    kind = 'raster' if cell and cell != 'Signature1' else 'blank'
    data, _ = coordinator_form(kind, cell or 'Name Responsible3')
    result = review(client, [('form.pdf', data)])
    if cell:
        reading = next(item for item in result['fields'] if item['field'] == cell)
        assert reading['status'] == 'not_found' and reading['value'] is None
    finding = next(item for item in result['findings'] if item['field'] == 'div_c.coordinator')
    assert finding['status'] == 'missing'
    request = result['information_request']
    item = next(item for item in request['items'] if item['finding_key'] == finding['key'])
    assert item['included'] and not item['officer_check'] and item['text'] in request['text']
