"""Bridge shutdown owns all readers, including when the host keeps its pipe open."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import pytest

from engine.desktop.bridge import encode, read_frame

ROOT = Path(__file__).resolve().parents[2]
CHILD = '''
import asyncio, concurrent.futures, hashlib, io, json, sys, threading
from pathlib import Path
if sys.platform != 'win32':
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from engine.desktop import bridge

mode = sys.argv[1]
released = asyncio.Event()
executor_release = threading.Event()
serving_task = None
serving_loop = None

if mode == 'cancel-read':
    class ObservedBridge(bridge.Bridge):
        async def serve(self, frames):
            global serving_task, serving_loop
            serving_task = asyncio.current_task()
            serving_loop = asyncio.get_running_loop()
            try:
                await super().serve(frames)
            finally:
                print('serve-ended', file=sys.stderr, flush=True)
    bridge.Bridge = ObservedBridge

async def app(scope, receive, send):
    if scope['type'] == 'http':
        message = await receive()
        if mode == 'disconnect':
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'waiting', 'more_body': True})
            assert (await receive())['type'] == 'http.disconnect'
            await send({'type': 'http.response.body', 'body': b'disconnected'})
        else:
            released.set()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': message['body']})
        return
    while True:
        event = await receive()
        name = event['type'].split('.')[-1]
        if name == 'startup' and mode == 'default-executor-busy':
            loop = asyncio.get_running_loop()
            loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=1))
            loop.run_in_executor(None, executor_release.wait)
        if name == 'shutdown':
            executor_release.set()
        if mode == name + '-failure':
            await send({'type': 'lifespan.' + name + '.failed'})
            return
        await send({'type': 'lifespan.' + name + '.complete'})
        if name == 'shutdown':
            return

async def control(op, args):
    assert op == 'deferred'
    await released.wait()
    return {'released': True}

def write(data):
    raise OSError('write failure')

class ErrorInput:
    def read(self, size):
        raise OSError('read failure')

class ShortInput(io.BytesIO):
    def read(self, size):
        return super().read(min(size, 1))

class CancelInput:
    def read(self, size):
        print('read-entered', file=sys.stderr, flush=True)
        serving_loop.call_soon_threadsafe(serving_task.cancel)
        try:
            return sys.stdin.buffer.read(size)
        finally:
            print('read-ended', file=sys.stderr, flush=True)

source = None
if mode == 'read-error':
    source = ErrorInput()
elif mode == 'closed-input':
    source = io.BytesIO()
    source.close()
elif mode == 'short-input':
    source = ShortInput(bridge.encode({'t': 'ctl', 'id': 'stop', 'op': 'shutdown'}))
elif mode == 'cancel-read':
    source = CancelInput()
error = None
clean = None
try:
    clean = bridge.run(app, hello={}, control=control, body_limit=1024,
                       stdin=source, write=write if mode == 'write-failure' else None)
except BaseException as exc:
    error = type(exc).__name__
readers = [t for t in threading.enumerate() if t is not threading.current_thread()]
print('pump-result ' + json.dumps({
    'clean': clean, 'alive': [t.name for t in readers if t.is_alive()],
    'error': error, 'active': bridge.ACTIVE is not None,
    'injectedClosed': source.closed if isinstance(source, io.BytesIO) else None,
    'source': str(Path(bridge.__file__).resolve()),
    'sourceSha256': hashlib.sha256(Path(bridge.__file__).read_bytes()).hexdigest(),
}), file=sys.stderr, flush=True)
for thread in readers:
    thread.join(timeout=2)
'''


class PipedBridge:
    def __init__(self, mode='normal'):
        env = {k: v for k, v in os.environ.items()
               if k in {'PATH', 'SYSTEMROOT', 'WINDIR', 'LANG', 'TMPDIR', 'TMP', 'TEMP'}}
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1', PYTHONUTF8='1')
        self.child = subprocess.Popen([sys.executable, '-B', '-X', 'faulthandler', '-c', CHILD, mode],
                                      cwd=ROOT, env=env, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.lines = queue.Queue()
        self.frames = queue.Queue()
        self.stderr = []
        self.written = []

        def collect_errors():
            for line in self.child.stderr:
                self.stderr.append(line)
                self.lines.put(line)
            self.lines.put(None)

        def collect_frames():
            while (frame := read_frame(self.child.stdout)) is not None:
                self.written.append(frame)
                self.frames.put(frame)
            self.frames.put(None)

        self.observers = [threading.Thread(target=collect_errors), threading.Thread(target=collect_frames)]
        for observer in self.observers:
            observer.start()

    def __enter__(self):
        return self

    def send(self, header, body=b''):
        self.send_bytes(encode(header, body))

    def send_bytes(self, data):
        self.child.stdin.write(data)
        self.child.stdin.flush()

    def frame(self):
        frame = self.frames.get(timeout=5)
        assert frame is not None, b''.join(self.stderr)
        return frame

    def hello(self):
        assert self.frame() == ({'t': 'hello', 'protocol': 'batatis.bridge.v1'}, b'')

    def stop(self):
        self.send({'t': 'ctl', 'id': 'stop', 'op': 'shutdown', 'args': {}})

    def request(self, rid, body=b''):
        self.send({'t': 'req', 'id': rid, 'method': 'POST', 'path': '/', 'headers': []})
        self.send({'t': 'body', 'id': rid, 'more': False}, body)

    def finish(self, *, clean=True, error=None, hold_input_until_exit=False):
        while True:
            line = self.lines.get(timeout=5)
            assert line is not None, b''.join(self.stderr)
            if line.startswith(b'pump-result '):
                result = json.loads(line[len(b'pump-result '):])
                break
        if hold_input_until_exit:
            assert result['alive'] == [], b''.join(self.stderr)
            assert not self.child.stdin.closed
            assert self.child.wait(timeout=5) == 0
        if not self.child.stdin.closed:
            self.child.stdin.close()
        assert self.child.wait(timeout=5) == 0
        for observer in self.observers:
            observer.join(timeout=5)
            assert not observer.is_alive()
        diagnostic = b''.join(self.stderr).decode(errors='replace')
        print(diagnostic, end='')
        assert result['clean'] is clean
        assert result['error'] == error
        assert result['active'] is False
        assert Path(result['source']) == ROOT / 'engine/desktop/bridge.py'
        assert result['sourceSha256'] == hashlib.sha256((ROOT / 'engine/desktop/bridge.py').read_bytes()).hexdigest()
        assert result['alive'] == [], diagnostic
        assert 'Event loop is closed' not in diagnostic
        assert 'Exception in thread' not in diagnostic
        return result

    def __exit__(self, *_):
        if not self.child.stdin.closed:
            try:
                self.child.stdin.close()
            except BrokenPipeError:
                pass
        if self.child.poll() is None:
            self.child.kill()
        self.child.wait(timeout=5)
        for observer in self.observers:
            observer.join(timeout=5)
        self.child.stdout.close()
        self.child.stderr.close()


def test_shutdown_owns_reader_while_peer_holds_stdin_open():
    with PipedBridge() as host:
        host.hello()
        host.stop()
        assert host.frame() == ({'t': 'ctl.res', 'id': 'stop', 'ok': True, 'value': {}}, b'')
        assert not host.child.stdin.closed
        host.finish()


def test_python_finalizes_cleanly_while_peer_still_holds_stdin_open():
    with PipedBridge() as host:
        host.hello()
        host.stop()
        host.finish(hold_input_until_exit=True)


def test_protocol_read_does_not_wait_for_the_apps_busy_default_executor():
    with PipedBridge('default-executor-busy') as host:
        host.hello()
        host.stop()
        assert host.frame() == ({'t': 'ctl.res', 'id': 'stop', 'ok': True, 'value': {}}, b'')
        host.finish()


def test_cancellation_of_an_active_blocking_read_waits_for_the_peer_to_release_it():
    with PipedBridge('cancel-read') as host:
        host.hello()
        while True:
            line = host.lines.get(timeout=5)
            assert line is not None, b''.join(host.stderr)
            if line.strip() == b'serve-ended':
                break
        with pytest.raises(queue.Empty):
            host.lines.get(timeout=0.2)
        host.child.stdin.close()
        host.finish(clean=None, error='CancelledError')
        assert next(i for i, line in enumerate(host.stderr) if line.strip() == b'read-ended') < next(
            i for i, line in enumerate(host.stderr) if line.startswith(b'pump-result '))


@pytest.mark.parametrize('data', [encode({'t': 'unknown'}),
                                 encode({'t': 'req', 'id': 'same'}) * 2,
                                 b'\0' * 8])
def test_protocol_failure_owns_reader_with_stdin_held_open(data):
    with PipedBridge() as host:
        host.hello()
        host.send_bytes(data)
        host.finish(clean=False)


@pytest.mark.parametrize('mode,error', [('startup-failure', 'RuntimeError'),
                                      ('write-failure', 'OSError'),
                                      ('shutdown-failure', 'RuntimeError')])
def test_exceptional_exit_owns_reader_with_stdin_held_open(mode, error):
    with PipedBridge(mode) as host:
        if mode == 'shutdown-failure':
            host.hello()
            host.stop()
        host.finish(clean=None, error=error)


@pytest.mark.parametrize('data,clean', [(b'', True), (b'\0', False),
                                      (b'\0\0\0\x04\0\0\0\0{"t', False),
                                      (b'\0\0\0\x0b\0\0\0\x02{"t":"req"}x', False)])
def test_eof_keeps_clean_and_truncated_frame_results(data, clean):
    with PipedBridge() as host:
        host.hello()
        if data:
            host.send_bytes(data)
        host.child.stdin.close()
        host.finish(clean=clean)


@pytest.mark.parametrize('mode', ['short-input', 'closed-input', 'read-error'])
def test_injected_binary_inputs_keep_short_reads_and_read_error_behavior(mode):
    with PipedBridge(mode) as host:
        result = host.finish()
        if mode == 'short-input':
            assert result['injectedClosed'] is False
            assert host.written[-1] == ({'t': 'ctl.res', 'id': 'stop', 'ok': True, 'value': {}}, b'')


def test_shutdown_drains_a_stream_and_cancel_still_allows_a_fresh_request():
    with PipedBridge('disconnect') as host:
        host.hello()
        host.request('cancelled')
        assert host.frame()[0] == {'t': 'start', 'id': 'cancelled', 'status': 200, 'headers': []}
        assert host.frame() == ({'t': 'body', 'id': 'cancelled', 'more': True}, b'waiting')
        host.send({'t': 'cancel', 'id': 'cancelled'})
        assert host.frame() == ({'t': 'body', 'id': 'cancelled', 'more': False}, b'disconnected')
        host.request('drained')
        assert host.frame()[0] == {'t': 'start', 'id': 'drained', 'status': 200, 'headers': []}
        assert host.frame() == ({'t': 'body', 'id': 'drained', 'more': True}, b'waiting')
        host.stop()
        host.finish()
        assert ({'t': 'body', 'id': 'drained', 'more': False}, b'disconnected') in host.written
        assert ({'t': 'ctl.res', 'id': 'stop', 'ok': True, 'value': {}}, b'') in host.written


def test_non_shutdown_control_does_not_block_requests_or_reorder_their_body():
    with PipedBridge() as host:
        host.hello()
        host.send({'t': 'ctl', 'id': 'pending', 'op': 'deferred', 'args': {}})
        host.request('release', b'\0\xffpayload')
        frames = [host.frame() for _ in range(3)]
        assert ({'t': 'ctl.res', 'id': 'pending', 'ok': True, 'value': {'released': True}}, b'') in frames
        assert [frame for frame in frames if frame[0].get('id') == 'release'] == [
            ({'t': 'start', 'id': 'release', 'status': 200, 'headers': []}, b''),
            ({'t': 'body', 'id': 'release', 'more': False}, b'\0\xffpayload')]
        host.stop()
        host.finish()
