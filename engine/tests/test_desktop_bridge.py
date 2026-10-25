"""The desktop bridge: the real engine behind private pipes, and the frame driver's fault paths."""
from __future__ import annotations

import asyncio
import io
import json
import threading

import pytest

from engine.desktop import bridge, host_provider
from engine.desktop.bridge import MAX_BODY, Bridge, ProtocolError, encode, read_frame
from engine.intake.model import GateClosed
from engine.tests.desktop_bridge_client import EngineProcess, engine_env
from engine.uploads import PDF_MAX_BYTES

PDF = b'%PDF-1.4\n' + bytes(range(256)) * (3 * 1024 * 4) + b'\n%%EOF\n'


def multipart(data: bytes, name: str = 'plan.pdf') -> tuple[bytes, str]:
    boundary = 'batatisDesktopBoundary7'
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            'Content-Type: application/pdf\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    return body, f'multipart/form-data; boundary={boundary}'


@pytest.fixture
def local_engine(tmp_path):
    engine = EngineProcess(engine_env('local', tmp_path))
    yield engine
    engine.close()


def test_hello_names_the_workspace_and_a_missing_code_database(local_engine):
    hello = local_engine.hello
    assert hello['t'] == 'hello' and hello['protocol'] == 'batatis.bridge.v1'
    assert hello['workspace']['kind'] == 'local' and len(hello['workspace']['id']) == 32
    assert hello['codedb']['available'] is False and hello['codedb']['build'] is None
    assert hello['codedb']['expectedBuild']
    assert 'dev' not in hello


def test_json_status_headers_and_errors_pass_through_like_http(local_engine):
    me = local_engine.request('GET', '/api/auth/me')
    assert me.status == 401 and me.json()['detail'] == 'Sign in to continue'
    created = local_engine.request('POST', '/api/cases', json_body={'title': 'Bridge case'})
    assert created.status == 201
    case = created.json()
    assert case['title'] == 'Bridge case'
    assert created.header('cache-control') == 'no-store'
    assert created.header('x-batatis-notice')
    got = local_engine.request('GET', f'/api/cases/{case["id"]}')
    assert got.status == 200 and got.json()['id'] == case['id']
    missing = local_engine.request('GET', '/api/cases/case_missing')
    assert missing.status == 404 and missing.json()['detail'] == 'case not found'
    invalid = local_engine.request('POST', '/api/cases', json_body={'title': 'x' * 501})
    assert invalid.status == 422
    unavailable = local_engine.request('GET', '/api/code/search', query='q=stairs')
    assert unavailable.status == 503 and unavailable.json()['detail'] == 'code database not found'


def test_pdf_bytes_survive_multipart_upload_download_and_delete_is_204(local_engine):
    case = local_engine.request('POST', '/api/cases', json_body={}).json()
    body, content_type = multipart(PDF)
    assert len(body) > 4 * MAX_BODY, 'the upload crosses several frames'
    uploaded = local_engine.request('POST', f'/api/cases/{case["id"]}/files', body=body,
                                    headers=[['content-type', content_type]])
    assert uploaded.status == 201, uploaded.body
    saved = uploaded.json()
    assert saved['size'] == len(PDF) and saved['name'] == 'plan.pdf'
    download = local_engine.request('GET', f'/api/cases/{case["id"]}/files/{saved["id"]}')
    assert download.status == 200 and download.body == PDF
    assert download.frames > 2, 'large responses are chunked'
    assert download.header('content-disposition').startswith('attachment; filename="plan.pdf"')
    deleted = local_engine.request('DELETE', f'/api/cases/{case["id"]}')
    assert deleted.status == 204 and deleted.body == b''
    assert local_engine.request('GET', f'/api/cases/{case["id"]}').status == 404


def test_an_upload_over_the_limit_is_refused_before_the_engine_reads_it(local_engine):
    case = local_engine.request('POST', '/api/cases', json_body={}).json()
    body, content_type = multipart(b'%PDF' + b'0' * (PDF_MAX_BYTES + 1))
    reply = local_engine.request('POST', f'/api/cases/{case["id"]}/files', body=body,
                                 headers=[['content-type', content_type]])
    assert reply.status == 413
    assert local_engine.request('GET', f'/api/cases/{case["id"]}/files').json()['items'] == []


def test_identify_events_stream_as_separate_frames(local_engine):
    case = local_engine.request('POST', '/api/cases', json_body={}).json()
    reply = local_engine.request('POST', f'/api/cases/{case["id"]}/identify',
                                 json_body={'prose': 'A deck guard 900 mm high instead of 1070 mm.'},
                                 headers=[['accept', 'text/event-stream']])
    assert reply.status == 200 and reply.header('content-type').startswith('text/event-stream')
    events = [chunk for chunk in reply.chunks if chunk]
    assert events[0].startswith(b'event: start'), events[:2]
    assert len(events) >= 2, 'the start event arrives before the result, not buffered with it'
    assert b'event: done' in events[-1] or b'event: error' in events[-1]


def test_end_of_input_stops_the_engine(tmp_path):
    engine = EngineProcess(engine_env('local', tmp_path))
    assert engine.close(timeout=20) == 0


def test_a_shutdown_control_stops_the_engine_without_closing_its_input(tmp_path):
    engine = EngineProcess(engine_env('local', tmp_path))
    assert engine.control('shutdown')['ok'] is True
    assert engine.proc.wait(timeout=20) == 0
    engine.close()


def test_a_malformed_frame_stops_the_engine_instead_of_guessing(tmp_path):
    engine = EngineProcess(engine_env('local', tmp_path))
    engine.proc.stdin.write(b'\x00\x00\x00\x05\x00\x00\x00\x00{"t":')
    engine.proc.stdin.flush()
    assert engine.proc.wait(timeout=20) == 2
    engine.close()


def test_hosted_configuration_is_refused_before_any_database_opens(tmp_path):
    engine = EngineProcess(engine_env('local', tmp_path, VERCEL='1'))
    assert engine.hello['t'] == 'refused' and 'VERCEL' in engine.hello['reason']
    assert engine.proc.wait(timeout=20) == 3
    assert not (tmp_path / 'local' / 'cases.sqlite').exists()


# ---------------------------------------------------------------- the frame driver, in process

class Harness:
    def __init__(self, app, control=None, body_limit=PDF_MAX_BYTES):
        self.written: list[tuple[dict, bytes]] = []
        self.wrote = threading.Condition()
        self.frames: asyncio.Queue | None = None
        self.bridge = Bridge(app, hello={'workspace': {'kind': 'local', 'id': 'x'}}, write=self._write,
                             control=control, body_limit=body_limit)

    def _write(self, data: bytes):
        frame = read_frame(io.BytesIO(data))
        with self.wrote:
            self.written.append(frame)
            self.wrote.notify_all()

    async def wait_for(self, predicate, timeout=5.0):
        deadline = asyncio.get_running_loop().time() + timeout
        while not any(predicate(h, b) for h, b in self.written):
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError(f'no matching frame in {self.written}')
            await asyncio.sleep(0.01)

    async def send(self, header, body=b''):
        await self.frames.put((header, body))

    async def run(self, script):
        self.frames = asyncio.Queue()
        serving = asyncio.create_task(self.bridge.serve(self.frames))
        try:
            await self.wait_for(lambda head, _: head['t'] == 'hello')
            await script(self)
        finally:
            await self.frames.put(None)
            await asyncio.wait_for(serving, 10)


async def request(h: Harness, rid: str, path='/', method='GET', body=b''):
    await h.send({'t': 'req', 'id': rid, 'method': method, 'path': path, 'query': '', 'headers': []})
    await h.send({'t': 'body', 'id': rid, 'more': False}, body)


def frames_for(h: Harness, rid: str):
    return [(header, body) for header, body in h.written if header.get('id') == rid]


def test_a_stream_chunk_is_written_before_the_app_produces_the_next():
    release = asyncio.Event()

    async def app(scope, receive, send):
        if scope['type'] != 'http':
            return
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/event-stream')]})
        await send({'type': 'http.response.body', 'body': b'event: stage\n\n', 'more_body': True})
        await release.wait()
        await send({'type': 'http.response.body', 'body': b'event: done\n\n'})

    async def script(h):
        await request(h, 'r1')
        await h.wait_for(lambda head, body: head.get('id') == 'r1' and body == b'event: stage\n\n')
        assert not any(b == b'event: done\n\n' for _, b in h.written), 'nothing waited for the whole stream'
        release.set()
        await h.wait_for(lambda head, body: head.get('id') == 'r1' and head['t'] == 'body' and not head['more'])

    asyncio.run(Harness(app).run(script))


def test_cancel_reaches_the_app_as_a_disconnect():
    seen = []

    async def app(scope, receive, send):
        if scope['type'] != 'http':
            return
        assert (await receive())['type'] == 'http.request'
        seen.append((await receive())['type'])
        await send({'type': 'http.response.start', 'status': 499, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    async def script(h):
        await request(h, 'r1')
        await asyncio.sleep(0.05)
        await h.send({'t': 'cancel', 'id': 'r1'})
        await h.wait_for(lambda head, _: head.get('id') == 'r1' and head['t'] == 'body')

    asyncio.run(Harness(app).run(script))
    assert seen == ['http.disconnect']


@pytest.mark.parametrize('after_start', [False, True])
def test_an_app_error_is_reported_as_a_failed_response(after_start):
    async def app(scope, receive, send):
        if scope['type'] != 'http':
            return
        if after_start:
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        raise RuntimeError('boom with private detail')

    async def script(h):
        await request(h, 'r1')
        await h.wait_for(lambda head, _: head.get('id') == 'r1' and head['t'] == 'fail')

    harness = Harness(app)
    asyncio.run(harness.run(script))
    kinds = [head['t'] for head, _ in frames_for(harness, 'r1')]
    assert kinds == (['start', 'fail'] if after_start else ['fail'])
    assert 'private' not in json.dumps([head for head, _ in harness.written])


def test_a_body_over_the_limit_is_answered_413_without_running_the_app():
    ran = []

    async def app(scope, receive, send):
        if scope['type'] == 'http':
            ran.append(True)

    async def script(h):
        await h.send({'t': 'req', 'id': 'r1', 'method': 'POST', 'path': '/', 'query': '', 'headers': []})
        await h.send({'t': 'body', 'id': 'r1', 'more': True}, b'x' * 10)
        await h.send({'t': 'body', 'id': 'r1', 'more': False}, b'x' * 10)
        await h.wait_for(lambda head, _: head.get('id') == 'r1' and head['t'] == 'body')

    harness = Harness(app, body_limit=15)
    asyncio.run(harness.run(script))
    assert ran == [] and frames_for(harness, 'r1')[0][0]['status'] == 413


def test_frames_reject_oversize_and_truncation():
    with pytest.raises(ProtocolError):
        encode({'t': 'body'}, b'x' * (MAX_BODY + 1))
    with pytest.raises(ProtocolError):
        read_frame(io.BytesIO(encode({'t': 'body'}, b'abc')[:-1]))
    assert read_frame(io.BytesIO(b'')) is None


def test_a_host_call_carries_the_exact_model_and_keeps_unknown_usage_unknown():
    results = []

    def run_calls():
        transport = host_provider.host_transport('intake', model='model-exact', effort='low')
        assert transport is not None
        for user in ('first', 'unknown usage', 'substituted', 'unverified'):
            try:
                results.append(transport('system', user, {'type': 'object'}))
            except GateClosed:
                results.append('gate closed')

    async def app(scope, receive, send):
        if scope['type'] != 'http':
            return
        await asyncio.to_thread(run_calls)
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    async def script(h):
        bridge.ACTIVE = h.bridge
        try:
            await request(h, 'r1')

            async def answer(user, reply):
                await h.wait_for(lambda head, _: head['t'] == 'call' and head['args']['user'] == user)
                call = [head for head, _ in h.written if head['t'] == 'call'][-1]
                assert call['requestId'] == 'r1'
                await h.send({'t': 'call.res', 'id': call['id'], **reply})
                return call

            call = await answer('first', {'ok': True, 'value': {
                'json': {'facts': []}, 'model': 'model-exact', 'effort': 'low',
                'usage': {'inputTokens': 7, 'outputTokens': 3}}})
            assert call['op'] == 'provider.completeJson'
            assert {k: call['args'][k] for k in ('task', 'model', 'effort', 'schema', 'maxOutputTokens')} == {
                'task': 'intake', 'model': 'model-exact', 'effort': 'low', 'schema': {'type': 'object'},
                'maxOutputTokens': None}
            await answer('unknown usage', {'ok': True, 'value': {
                'json': {'facts': []}, 'model': 'model-exact', 'effort': 'low', 'usage': None}})
            await answer('substituted', {'ok': True, 'value': {
                'json': {'facts': []}, 'model': 'another-model', 'effort': 'low', 'usage': None}})
            await answer('unverified', {'ok': False, 'reason': 'context_unverified', 'message': 'Not yet'})
            await h.wait_for(lambda head, _: head.get('id') == 'r1' and head['t'] == 'body')
        finally:
            bridge.ACTIVE = None

    asyncio.run(Harness(app).run(script))
    assert results == [({'facts': []}, {'input_tokens': 7, 'output_tokens': 3}),
                       ({'facts': []}, {'input_tokens': None, 'output_tokens': None}),
                       'gate closed', 'gate closed']
    assert host_provider.host_transport('intake', model='m', effort='low') is None, 'outside the bridge'
