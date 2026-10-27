"""Applicant reading regressions. Synthetic inputs and fake transports only."""
import pytest
import io
import json

from PIL import Image
from fastapi.testclient import TestClient
from engine.api import create_app
from engine.store import CaseStore
from engine.intake.extract import read_file
from engine.tests.test_intake_pdf import pdf

from engine.intake import service
from engine.intake.fork import assess
from engine.models import Case
from engine.models_intake import IntakePlan, IntakeRecord, Question, ScopeCheck


@pytest.mark.parametrize('opening', ['Can I build', 'Is it possible to build', 'Am I allowed to build',
                                     'Do I need a variance to build'])
def test_an_applicants_question_about_their_plan_still_supplies_facts(opening):
    text = f'{opening} a two-storey house in Edmonton with bigger windows?'
    facts = {f.field: f.value for f in service.run(text, []).facts}
    assert facts.items() >= {'storeys': 2, 'occupancy': 'single_family', 'municipality': 'Edmonton'}.items()
    assert service.run('Can you explain what a variance is?', []).facts == []
    assert assess('Can I build with one exit instead of two?').variance_needed == 'likely'


def answering(field):
    case = Case()
    case.intake = IntakeRecord(plan=IntakePlan(next='questions', scope=ScopeCheck(status='in_scope'),
        fork=assess(''), questions=[Question(id=f'intake.{field}', field=field, text='How much?', why='Needed')]))
    return case


@pytest.mark.parametrize('field,raw,want', [
    ('limiting_distance_m', '4 feet', 1.2192), ('span_m', '4 ft', 1.2192), ('span_m', "4'", 1.2192),
    ('span_m', '4 ft 6 in', 1.3716), ('span_m', '13\'6"', 4.1148), ('span_m', '1.2 m', 1.2),
    ('span_m', '4 ft and 6 in', 1.3716), ('limiting_distance_m', '.3 m', .3),
    ('span_m', '120 cm', 1.2), ('span_m', '1500 mm', 1.5),
    ('building_area_m2', '1500 sq ft', 139.35456), ('floor_area_m2', '140 m2', 140),
    ('building_area_m2', '140 m²', 140), ('span_m', '4', 4), ('storeys', 'two', 2),
])
def test_answers_convert_units_and_keep_what_the_applicant_typed(field, raw, want):
    case = answering(field)
    [fact] = service.answer(case, [{'question_id': f'intake.{field}', 'answer': raw}])
    assert fact.value == want
    assert fact.source.quote == raw


@pytest.mark.parametrize('field,raw', [('span_m', '4 bananas'), ('span_m', '4 sq ft'),
    ('building_area_m2', '4 feet'), ('storeys', '4 ft'), ('span_m', '4 ft 18 in'),
    ('span_m', '4 ft or 6 ft'), ('span_m', '-4 ft'), ('span_m', '9' * 400 + ' m')])
def test_unknown_or_wrong_units_and_ambiguous_answers_are_refused(field, raw):
    with pytest.raises(service.AnswerRejected):
        service.answer(answering(field), [{'question_id': f'intake.{field}', 'answer': raw}])


def picture(format='PNG', size=(32, 20)):
    buf = io.BytesIO()
    Image.new('RGB', size, 'white').save(buf, format=format)
    return buf.getvalue()


@pytest.mark.parametrize('format,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg'), ('WEBP', 'image/webp')])
def test_image_upload_checks_the_bytes_and_roundtrips_its_real_type(tmp_path, format, mime):
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')))
    cid = client.post('/cases').json()['id']
    data = picture(format)
    response = client.post(f'/cases/{cid}/files', files={'file': ('plan.picture', data, 'application/octet-stream')})
    assert response.status_code == 201, response.text
    assert response.json()['content_type'] == mime
    fetched = client.get(f'/cases/{cid}/files/{response.json()["id"]}')
    assert fetched.content == data and fetched.headers['content-type'] == mime
    rejected = client.post(f'/cases/{cid}/files', files={'file': ('pretend.png', b'not a picture', mime)})
    assert rejected.status_code == 415
    rejected = client.post(f'/cases/{cid}/files', content=data[:16], headers={'content-type': mime})
    assert rejected.status_code == 415


def test_plans_alone_start_and_image_off_reports_the_limit(tmp_path):
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')))
    cid = client.post('/cases').json()['id']
    uploaded = client.post(f'/cases/{cid}/files', files={'file': ('plan.pdf', pdf([[(72, 700, 'A two-storey house.')]]), 'application/pdf')}).json()
    response = client.post(f'/cases/{cid}/intake', json={'text': '', 'file_ids': [uploaded['id']], 'model': False})
    assert response.status_code == 200, response.text
    assert any(f['field'] == 'storeys' for f in response.json()['facts'])
    report = read_file('photo', 'plan.png', picture()).files[0]
    assert report.status == 'not_read' and report.pictures_not_read_reason == 'AI is off'
    assert report.image_pages_read == [] and report.pages == 1


class VisionReader:
    supports_images = True

    def __init__(self):
        self.pictures = []
        self.texts = []

    def __call__(self, system, user, schema):
        if isinstance(user, list):
            self.pictures.append(user)
            return {'facts': [{'field': 'storeys', 'value': '2', 'quote': 'Two storeys'},
                              {'field': 'owner_name', 'value': 'Invented Owner', 'quote': 'Invented Owner'}]}, {'input_tokens': 20, 'output_tokens': 10}
        text = json.loads(user)['text']
        self.texts.append(text)
        return {'facts': [{'field': 'statement', 'value': text, 'quote': text}]}, {'input_tokens': 20, 'output_tokens': 10}


def test_no_picture_leaves_the_machine_until_the_applicant_allows_it():
    reader = VisionReader()
    scan = pdf([[(72, 700, 'A house.')], []], shapes_only={1})
    out = service.run('', [('photo', 'elevation.png', picture()), ('scan', 'scan.pdf', scan)], transport=reader, status='fake')
    assert reader.pictures == []
    assert [f.pictures_not_read_reason for f in out.files] == ['waiting for your OK', 'waiting for your OK']
    assert out.files[1].text_pages_read == [1] and out.files[1].status == 'partly_read'


def test_pictures_are_downscaled_and_always_unconfirmed_proposals_with_sources():
    reader = VisionReader()
    out = service.run('', [('photo', 'elevation.png', picture(size=(2800, 1800)))], transport=reader, status='fake', pictures=True)
    assert len(reader.pictures) == 1
    [fact] = out.facts
    assert (fact.field, fact.kind, fact.status, fact.source.ref, fact.source.page) == ('storeys', 'proposed', 'unconfirmed', 'photo', 1)
    assert out.pointers[0].method == 'vision' and not out.pointers[0].verified
    assert out.pointers[0].source_name == 'elevation.png'
    assert out.files[0].image_pages_read == [1] and out.files[0].status == 'read'
    import base64
    encoded = reader.pictures[0][1]['image_url']['url'].split(',', 1)[1]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as sent:
        assert max(sent.size) <= 1280 and not sent.getexif()
    case = Case()
    service.apply(case, '', out)
    assert all(f.status == 'unconfirmed' and f.kind == 'proposed' for f in case.facts)


def test_scan_pages_go_to_vision_and_a_text_only_connection_reports_it_cannot_read_pictures():
    data = pdf([[(72, 700, 'A house.')], []], shapes_only={1})
    reader = VisionReader()
    out = service.run('', [('scan', 'scan.pdf', data)], transport=reader, status='fake', pictures=True)
    assert out.files[0].text_pages_read == [1] and out.files[0].semantic_pages_read == [1]
    assert out.files[0].image_pages_read == [2] and out.files[0].pages_read == [1, 2]
    def text_only(*args):
        return {'facts': []}, {}
    report = read_file('photo', 'picture.png', picture(), transport=text_only, status='fake').files[0]
    assert report.pictures_not_read_reason == 'this AI connection reads text only'


def test_semantic_reading_reaches_every_text_page_and_the_tail_of_a_long_page():
    reader = VisionReader()
    data = pdf([[(72, 700, f'Page {n}: We propose a special wall.')] for n in range(1, 202)])
    out = service.run('', [('many', 'many.pdf', data)], transport=reader, status='fake', pictures=True)
    report = out.files[0]
    assert report.pages == 201 and report.text_pages_read == list(range(1, 201))
    assert report.semantic_pages_read == list(range(1, 201))
    assert report.pages_not_read == [201] and report.status == 'partly_read'
    assert len(reader.texts) < 10, 'short pages share bounded chunks'
    text = 'We propose a wall.\n' * 700 + 'We propose a green roof.'
    reader = VisionReader()
    out = service.run(text, [], transport=reader, status='fake')
    assert 'We propose a green roof.' in ''.join(reader.texts)


def test_the_picture_budget_is_per_file_and_per_request():
    reader = VisionReader()
    data = pdf([[] for _ in range(9)], shapes_only=set(range(9)))
    out = service.run('', [(str(n), f'{n}.pdf', data) for n in range(3)], transport=reader, status='fake', pictures=True)
    assert len(reader.pictures) == 8
    assert [len(r.image_pages_read) for r in out.files] == [4, 4, 0]
    assert all(r.status != 'read' and r.pictures_not_read_reason for r in out.files)


def test_repeated_metric_facts_are_one_fact_with_all_their_sources_and_conflicts_stay():
    data = pdf([[(72, 700, 'Building area: 1500 sq ft.')], [(72, 700, 'Building area: 139.35 m2.')]])
    out = service.run('', [('a', 'first.pdf', data), ('b', 'second.pdf', pdf([[(72, 700, 'Building area: 139.35 m2.')]]))])
    areas = [f for f in out.facts if f.field == 'building_area_m2']
    assert len(areas) == 1 and areas[0].value == 139.35
    pointers = [p for p in out.pointers if p.fact_id == areas[0].id]
    assert {(p.source_ref, p.page) for p in pointers} == {('a', 1), ('a', 2), ('b', 1)}
    case = Case()
    service.apply(case, '', out)
    assert {(p.source_ref, p.page) for p in case.intake.pointers if p.fact_id == areas[0].id} == {('a', 1), ('a', 2), ('b', 1)}
    out = service.run('', [('c', 'conflict.pdf', pdf([[(72, 700, 'A two-storey house.')], [(72, 700, 'A three-storey house.')]]))])
    service.apply(Case(), '', out)
    assert any(c.field == 'storeys' and set(c.values) == {2, 3} for c in out.conflicts)


def test_semantic_failures_and_budget_never_claim_full_coverage():
    from engine.intake.model import Budget, GateClosed
    def fail(*args):
        raise RuntimeError('private token')
    report = read_file('a', 'a.pdf', pdf([[(72, 700, 'A house.')]]), transport=fail, status='fake').files[0]
    assert report.text_pages_read == [1] and report.semantic_pages_read == []
    assert report.status == 'partly_read' and 'private' not in report.reason
    report = read_file('a', 'a.pdf', pdf([[(72, 700, 'A house.')]]), transport=VisionReader(), status='fake', budget=Budget(text_chars=2)).files[0]
    assert report.semantic_pages_read == [] and report.semantic_reason == 'Reading limit reached'
    def closed(*args):
        raise GateClosed('closed')
    report = read_file('a', 'a.pdf', pdf([[(72, 700, 'A house.')]]), transport=closed, status='fake').files[0]
    assert report.semantic_pages_sent == [] and report.semantic_pages_read == []
    assert report.semantic_reason == 'AI is paused'


def test_removing_a_file_keeps_confirmed_and_shared_facts_and_cannot_resurrect_them(tmp_path):
    from engine.intake.extract import Extraction, Origin
    from engine.models import Fact, Source
    from engine.models_intake import FactPointer, FileReport
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    a = store.put_file(case.id, 'a.pdf', pdf([[(72, 700, 'A two-storey house.')]]))['id']
    b = store.put_file(case.id, 'b.pdf', pdf([[(72, 700, 'A two-storey house.')]]))['id']
    def fact(id, field, status='unconfirmed'):
        return Fact(id=id, field=field, value=2, kind='pointed', status=status,
                    source=Source(type='file', ref=a, page=1, quote='two-storey'))
    case.facts = [fact('only', 'storeys'), fact('shared', 'dwelling_units'), fact('confirmed', 'storeys', 'confirmed')]
    case.intake = IntakeRecord(pointers=[FactPointer(fact_id=id, field=field, method='rules', source_ref=ref, page=1)
        for id, field, ref in [('only', 'storeys', a), ('shared', 'dwelling_units', a), ('shared', 'dwelling_units', b), ('confirmed', 'storeys', a)]],
        files=[FileReport(file_id=id, name=id + '.pdf', status='read') for id in (a, b)])
    store.put(case)
    client = TestClient(create_app(store=store))
    response = client.request('DELETE', f'/cases/{case.id}/intake/files/{a}', json={'expected_version': store.get(case.id).version})
    assert response.status_code == 200, response.text
    assert response.json()['removed_facts'] == 1
    saved = store.get(case.id)
    assert {f.id for f in saved.facts} == {'shared', 'confirmed'}
    assert next(f for f in saved.facts if f.id == 'shared').source.ref == b
    assert not any(p.source_ref == a for p in saved.intake.pointers)
    assert [f['id'] for f in client.get(f'/cases/{case.id}/files').json()['items']] == [b]
    reread = client.post(f'/cases/{case.id}/intake', json={'text': '', 'file_ids': [a], 'model': False})
    assert reread.status_code == 200, reread.text
    assert 'only' not in {f.id for f in store.get(case.id).facts}
    assert not any(p.source_ref == a for p in store.get(case.id).intake.pointers)


@pytest.mark.parametrize('filename', ['notes.txt', 'notes'])
def test_text_notes_are_read_and_inventory_carries_the_read_report(tmp_path, filename):
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')))
    cid = client.post('/cases').json()['id']
    saved = client.post(f'/cases/{cid}/files', files={'file': (filename, b'A two-storey house in Edmonton.', 'text/plain')}).json()
    response = client.post(f'/cases/{cid}/intake', json={'file_ids': [saved['id']], 'model': False})
    assert response.status_code == 200, response.text
    assert any(f['field'] == 'municipality' for f in response.json()['facts'])
    [file] = client.get(f'/cases/{cid}/files').json()['items']
    assert file['read_report']['media_type'] == 'text/plain'
    assert file['read_report']['text_pages_read'] == [1]


def test_picture_statements_survive_settling_and_disagreeing_pictures_stay_a_conflict():
    class Drawings:
        supports_images = True
        count = 0
        def __call__(self, system, user, schema):
            self.count += 1
            return {'facts': [{'field': 'storeys', 'value': str(self.count + 1), 'quote': f'{self.count + 1} storeys'},
                              {'field': 'statement', 'value': 'A green roof', 'quote': 'A green roof'}]}, {}
    out = service.run('', [('a', 'a.png', picture()), ('b', 'b.png', picture())], transport=Drawings(), status='fake', pictures=True)
    service.apply(Case(), '', out)
    assert any(c.field == 'storeys' and set(c.values) == {2, 3} for c in out.conflicts)
    [statement] = [f for f in out.facts if f.field.startswith('statement.')]
    assert statement.kind == 'proposed' and statement.status == 'unconfirmed'
    assert {p.source_ref for p in out.pointers if p.fact_id == statement.id} == {'a', 'b'}


def test_hosted_vision_uses_image_content_parts_and_the_existing_meter(monkeypatch):
    from engine import llm_gate
    from engine.intake import model
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-not-a-key')
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    llm_gate.reset_for_tests()
    requests = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {'choices': [{'message': {'content': '{"facts":[]}'}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}
    def post(self, url, json=None, headers=None):
        requests.append(json)
        return Response()
    monkeypatch.setattr('httpx.Client.post', post)
    try:
        transport, status = model.default_transport()
        out = service.run('', [('a', 'a.png', picture())], transport=transport, status=status, pictures=True)
        assert out.files[0].image_pages_read == [1] and out.model.input_tokens == 100
        [body] = requests
        assert body['model'] == model.MODEL and body['reasoning_effort'] == model.EFFORT
        assert 'service_tier' not in body
        assert body['messages'][1]['content'][1]['type'] == 'image_url'
        assert llm_gate._memory.today() > 0
    finally:
        llm_gate.reset_for_tests()


def test_outbound_chunks_keep_scrubbing_and_invalid_model_payloads_are_reported():
    seen = []
    def transport(system, user, schema):
        seen.append(user)
        return {'facts': []}, {}
    text = 'Owner: Jane Example\n' + 'We propose timber.\n' * 800 + 'Mailing address: 12 Elm Street\n'
    service.run(text, [], transport=transport, status='fake')
    assert len(seen) > 1 and 'Jane Example' not in ''.join(seen) and '12 Elm Street' not in ''.join(seen)
    report = read_file('a', 'a.pdf', pdf([[(72, 700, 'A house.')]]), transport=lambda *args: ([], {}), status='fake').files[0]
    assert report.status == 'partly_read' and report.semantic_pages_read == []


def test_image_and_text_uploads_share_the_size_cap_and_invalid_utf8_is_refused(tmp_path):
    from engine.uploads import PDF_MAX_BYTES
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')))
    cid = client.post('/cases').json()['id']
    for mime, data in [('image/png', picture() + b'x' * PDF_MAX_BYTES), ('text/plain', b'x' * (PDF_MAX_BYTES + 1))]:
        response = client.post(f'/cases/{cid}/files', content=data, headers={'content-type': mime})
        assert response.status_code == 413
    assert client.post(f'/cases/{cid}/files', files={'file': ('notes.txt', b'\xff\x00', 'text/plain')}).status_code == 415


def test_transparent_drawings_keep_a_white_background_and_thumbnails_drop_metadata():
    from engine.intake.images import open_image, picture_url
    import base64
    buf = io.BytesIO()
    with Image.new('RGBA', (40, 20), (0, 0, 0, 0)) as image:
        image.putpixel((4, 4), (0, 0, 0, 255))
        exif = Image.Exif()
        exif[315] = 'Synthetic private artist'
        image.save(buf, 'PNG', exif=exif)
    with open_image(buf.getvalue()) as image:
        assert image.getpixel((0, 0)) == (255, 255, 255)
        assert image.getpixel((4, 4)) == (0, 0, 0)
    outbound = base64.b64decode(picture_url(buf.getvalue()).split(',', 1)[1])
    assert b'Synthetic private artist' not in outbound
    with Image.open(io.BytesIO(outbound)) as image:
        assert not image.getexif()


@pytest.mark.parametrize('remaining_method', ['vision', 'model'])
def test_removing_a_text_source_leaves_an_unverified_fact_as_a_proposal(remaining_method):
    from engine.models import Fact, Source
    from engine.models_intake import FactPointer
    case = Case(facts=[Fact(id='shared', field='storeys', value=2, kind='exact', source=Source(type='file', ref='a', page=1))],
        intake=IntakeRecord(pointers=[FactPointer(fact_id='shared', field='storeys', method=method, source_ref=ref, page=1, verified=verified)
            for method, ref, verified in [('form', 'a', True), (remaining_method, 'b', False)]]))
    assert service.remove_file(case, 'a') == 0
    assert case.facts[0].kind == 'proposed' and case.facts[0].status == 'unconfirmed'
    assert case.facts[0].source.type == 'file' and case.facts[0].source.ref == 'b'
    assert case.facts[0].source.quote is None, 'a quote from a removed file must not be relabelled as another file\'s words'


def test_concurrent_scan_reading_keeps_native_pdf_handles_safe():
    import subprocess
    import sys
    probe = '''
from concurrent.futures import ThreadPoolExecutor
from engine.intake.service import run
from engine.tests.test_journey_reading import VisionReader
from engine.tests.test_intake_pdf import pdf
data = pdf([[], []], shapes_only={0, 1})
def read_one(index):
    out = run('', [(str(index), 'scan.pdf', data)], transport=VisionReader(), status='fake', pictures=True)
    assert out.files[0].image_pages_read == [1, 2]
    assert all(f.kind == 'proposed' for f in out.facts)
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(read_one, range(16)))
print('16 concurrent scan reads completed')
'''
    result = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', probe], capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr
    assert '16 concurrent scan reads completed' in result.stdout


class ThreeStoreys(VisionReader):
    def __call__(self, system, user, schema):
        if isinstance(user, list):
            self.pictures.append(user)
            return {'facts': [{'field': 'storeys', 'value': '3', 'quote': 'Three storeys'}]}, {'input_tokens': 20, 'output_tokens': 10}
        return {'facts': []}, {'input_tokens': 20, 'output_tokens': 10}


def test_a_picture_that_disagrees_with_the_text_stays_to_check():
    out = service.run('', [('plans', 'plans.pdf', pdf([[(72, 720, 'Project brief'), (72, 700, 'A two-storey house.')]])), ('photo', 'elevation.png', picture())],
                      transport=ThreeStoreys(), status='fake', pictures=True)
    case = Case()
    service.apply(case, '', out)
    storeys = {(f.value, f.status, f.kind) for f in case.facts if f.field == 'storeys'}
    assert (2, 'confirmed', 'pointed') in storeys and (3, 'unconfirmed', 'proposed') in storeys


def test_removing_a_file_withdraws_only_its_values_from_a_conflict():
    from engine.models_intake import FieldConflict
    case = Case()
    case.intake = IntakeRecord(conflicts=[FieldConflict(field='storeys', values=[2, 3], quotes=['two', 'three'],
                                                        source_ref='a', source_refs=['a', 'b'])])
    service.remove_file(case, 'b')
    assert case.intake.conflicts == []
    case.intake.conflicts = [FieldConflict(field='storeys', values=[2, 3, 4], quotes=['two', 'three', 'four'],
                                           source_ref='a', source_refs=['a', 'b', 'c'])]
    service.remove_file(case, 'a')
    [left] = case.intake.conflicts
    assert (left.values, left.source_refs, left.source_ref) == ([3, 4], ['b', 'c'], 'b')


@pytest.mark.parametrize('text', ['Can I use Batatis instead of hiring a professional?',
                                  'Can I have examples of a two-storey house in Edmonton?'])
def test_a_question_about_the_tool_is_not_read_as_the_plan(text):
    assert not {f.field for f in service.run(text, []).facts} & {'alternative_description', 'storeys', 'municipality'}
    assert assess(text).variance_needed != 'likely'


@pytest.mark.parametrize(('typed', 'metres'), [('1199 mm', 1.199), ('1.199 m', 1.199), ('4 mm', 0.004), ('4 ft', 1.2192)])
def test_answer_units_keep_their_precision(typed, metres):
    from engine.intake.text import measurement
    assert measurement(typed, 'length') == metres


def test_no_reading_call_starts_that_could_outrun_the_deadline():
    import time
    from engine.intake.model import CALL_SECONDS, Budget
    assert Budget(deadline=time.monotonic() + CALL_SECONDS - 1).expired()
    assert not Budget(deadline=time.monotonic() + CALL_SECONDS + 5).expired()


def test_the_reading_record_names_no_model():
    out = service.run('', [('photo', 'elevation.png', picture())], transport=VisionReader(), status='live', pictures=True)
    assert out.model.model in (None, 'reader-1')
    assert 'gpt' not in json.dumps(out.model.model_dump()).lower()


@pytest.mark.parametrize('text', ['Exposing building face (east wall): 31.5 m².', 'W5 1800 x 1700 mm 3.06 m²',
                                  'Total unprotected openings on the east face: 6.12 m² (19.4 % of the exposing building face).'])
def test_wall_and_window_areas_on_plans_are_not_the_building_area(text):
    from engine.intake.rules import read
    assert not [h for h in read(text).hits if h.field == 'building_area_m2']


def test_a_title_block_row_without_a_colon_gives_the_owner_and_address_but_not_guesses():
    from engine.intake.rules import read
    text = 'Civic address 10234 87 Ave NW, Edmonton, AB\r\nOwner Dana Whitfield\r\nOwner Approval Required\r\nOwner wants a bigger window\r\n'
    got = [(h.field, h.value) for h in read(text).hits if h.field in ('owner_name', 'municipal_address')]
    assert got == [('municipal_address', '10234 87 Ave NW, Edmonton, AB'), ('owner_name', 'Dana Whitfield')]


def test_plans_alone_can_put_the_application_on_the_variance_route():
    from engine.intake.plan import build_plan
    plans = pdf([[(72, 700, 'We propose these larger windows instead of the smaller openings the table allows.')]])
    case = Case()
    service.apply(case, '', service.run('', [('plans', 'plans.pdf', plans)]))
    assert build_plan(case).fork.variance_needed == 'likely'
