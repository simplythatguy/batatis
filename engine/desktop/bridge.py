"""Serve one ASGI app over the desktop host's private pipes; no socket listener.

Wire format (batatis.bridge.v1): u32 BE header length, u32 BE body length, a JSON object header,
then raw body bytes. The host owns the other end; see desktop/src/main/bridge.ts.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from contextvars import ContextVar
from dataclasses import dataclass
import itertools
import json
import os
import struct
import sys
import threading
from typing import Any, Awaitable, BinaryIO, Callable
from urllib.parse import unquote

PROTOCOL = 'batatis.bridge.v1'
MAX_HEADER = 64 * 1024
MAX_BODY = 256 * 1024
METHODS = frozenset({'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'})
DRAIN_SECONDS = 5.0

_PREFIX = struct.Struct('>II')

Control = Callable[[str, dict], Awaitable[dict]]


class ProtocolError(Exception):
    """The peer broke the frame contract. The bridge stops instead of guessing."""


class ControlError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class HostUnavailable(Exception):
    """The host did not answer a call: no bridge, a timeout, or the bridge stopped."""


@dataclass(frozen=True)
class RequestContext:
    bridge: Bridge
    request_id: str


REQUEST_CONTEXT: ContextVar[RequestContext | None] = ContextVar('desktop_request', default=None)


def encode(header: dict, body: bytes = b'') -> bytes:
    raw = json.dumps(header, separators=(',', ':')).encode()
    if len(raw) > MAX_HEADER or len(body) > MAX_BODY:
        raise ProtocolError('frame too large')
    return _PREFIX.pack(len(raw), len(body)) + raw + body


def read_frame(stream: BinaryIO) -> tuple[dict, bytes] | None:
    """One frame, or None at a clean end of stream. Raises ProtocolError on a malformed frame."""
    prefix = _read_exact(stream, _PREFIX.size, allow_eof=True)
    if prefix is None:
        return None
    header_length, body_length = _PREFIX.unpack(prefix)
    if header_length == 0 or header_length > MAX_HEADER or body_length > MAX_BODY:
        raise ProtocolError('frame too large')
    raw = _read_exact(stream, header_length)
    body = _read_exact(stream, body_length) if body_length else b''
    try:
        header = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProtocolError('header is not JSON') from exc
    if not isinstance(header, dict) or not isinstance(header.get('t'), str):
        raise ProtocolError('header has no type')
    return header, body


def _read_exact(stream: BinaryIO, size: int, allow_eof: bool = False) -> bytes | None:
    buf = bytearray()
    while len(buf) < size:
        chunk = stream.read(size - len(buf))
        if not chunk:
            if allow_eof and not buf:
                return None
            raise ProtocolError('truncated frame')
        buf += chunk
    return bytes(buf)


def _scope(header: dict, body_length: int) -> dict:
    method, path, query = header.get('method'), header.get('path'), header.get('query', '')
    if method not in METHODS or not isinstance(path, str) or not path.startswith('/') or '\x00' in path:
        raise ProtocolError('invalid request line')
    if not isinstance(query, str) or len(path) + len(query) > 8192:
        raise ProtocolError('invalid request line')
    headers = []
    for pair in header.get('headers') or []:
        if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(part, str) for part in pair)):
            raise ProtocolError('invalid header')
        name = pair[0].lower()
        if name not in {'host', 'content-length'}:
            headers.append((name.encode('latin-1'), pair[1].encode('latin-1')))
    headers.append((b'host', b'localhost'))
    if body_length:
        headers.append((b'content-length', str(body_length).encode()))
    return {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.3'}, 'http_version': '1.1',
            'method': method, 'scheme': 'http', 'path': unquote(path), 'raw_path': path.encode('latin-1'),
            'query_string': query.encode('latin-1'), 'root_path': '', 'headers': headers,
            'client': ('127.0.0.1', 0), 'server': ('localhost', 80), 'state': {}}


class _Request:
    def __init__(self, header: dict):
        self.header = header
        self.chunks: list[bytes] = []
        self.size = 0
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.started = False
        self.finished = False


class Bridge:
    """Dispatches frames to the app, one task per request, and writes its responses as frames."""

    def __init__(self, app, *, hello: dict, write: Callable[[bytes], None], control: Control | None = None,
                 body_limit: int):
        self.app, self.hello, self.control, self.body_limit = app, hello, control, body_limit
        self._write_raw, self._write_lock = write, threading.Lock()
        self._requests: dict[str, _Request] = {}
        self._calls: dict[str, concurrent.futures.Future] = {}
        self._call_ids = itertools.count(1)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lifespan: tuple[asyncio.Queue, asyncio.Queue] | None = None
        self._frames: asyncio.Queue | None = None
        self._stopping = False
        self.protocol_error = False

    def write(self, header: dict, body: bytes = b'') -> None:
        frame = encode(header, body)
        with self._write_lock:
            self._write_raw(frame)

    async def serve(self, frames: asyncio.Queue) -> None:
        """Run until EOF (None in `frames`), a shutdown control or a protocol error."""
        self._loop = asyncio.get_running_loop()
        self._frames = frames
        self._lifespan = (asyncio.Queue(), asyncio.Queue())
        lifespan = asyncio.create_task(self._run_lifespan(*self._lifespan))
        await self._lifespan_event('startup')
        self.write({'t': 'hello', 'protocol': PROTOCOL, **self.hello})
        try:
            while not self._stopping:
                item = await frames.get()
                if item is None:
                    break
                if isinstance(item, ProtocolError):
                    self.protocol_error = True
                    break
                header, body = item
                try:
                    await self._dispatch(header, body)
                except ProtocolError as error:
                    print(f'bridge: {error}', file=sys.stderr)
                    self.protocol_error = True
                    break
        finally:
            await self._drain()
            await self._lifespan_event('shutdown')
            lifespan.cancel()
            for future in self._calls.values():
                future.set_exception(HostUnavailable('bridge stopped'))
            self._calls.clear()

    async def _dispatch(self, header: dict, body: bytes) -> None:
        kind, rid = header['t'], header.get('id')
        if kind == 'req':
            if not isinstance(rid, str) or rid in self._requests:
                raise ProtocolError('duplicate request id')
            self._requests[rid] = _Request(header)
        elif kind == 'body':
            request = self._requests.get(rid)
            if request is None or request.task is not None:
                return
            request.size += len(body)
            if request.size > self.body_limit:
                self._requests.pop(rid)
                self.write({'t': 'start', 'id': rid, 'status': 413,
                            'headers': [['content-type', 'application/json']]})
                self.write({'t': 'body', 'id': rid, 'more': False},
                           json.dumps({'detail': 'request body too large'}).encode())
                return
            request.chunks.append(body)
            if not header.get('more'):
                request.task = asyncio.create_task(self._handle(rid, request))
        elif kind == 'cancel':
            request = self._requests.get(rid)
            if request is not None:
                request.inbox.put_nowait({'type': 'http.disconnect'})
                if request.task is None:
                    self._requests.pop(rid)
        elif kind == 'ctl':
            asyncio.create_task(self._control(rid, header))
        elif kind == 'call.res':
            future = self._calls.pop(rid, None)
            if future is not None and not future.done():
                future.set_result(header)
        else:
            raise ProtocolError(f'unknown frame type {kind}')

    async def _handle(self, rid: str, request: _Request) -> None:
        body = b''.join(request.chunks)
        request.chunks = []
        try:
            scope = _scope(request.header, len(body))
        except ProtocolError:
            self._requests.pop(rid, None)
            self.write({'t': 'fail', 'id': rid, 'detail': 'invalid request'})
            return
        request.inbox.put_nowait({'type': 'http.request', 'body': body, 'more_body': False})

        async def receive():
            return await request.inbox.get()

        async def send(message):
            if request.finished:
                return
            if message['type'] == 'http.response.start':
                request.started = True
                headers = [[k.decode('latin-1'), v.decode('latin-1')] for k, v in message.get('headers', [])]
                self.write({'t': 'start', 'id': rid, 'status': message['status'], 'headers': headers})
            elif message['type'] == 'http.response.body':
                data, more = message.get('body', b''), message.get('more_body', False)
                for offset in range(0, max(len(data), 1), MAX_BODY):
                    last = offset + MAX_BODY >= len(data)
                    self.write({'t': 'body', 'id': rid, 'more': more or not last}, data[offset:offset + MAX_BODY])
                request.finished = not more

        token = REQUEST_CONTEXT.set(RequestContext(self, rid))
        try:
            await self.app(scope, receive, send)
            if not request.finished:
                self.write({'t': 'fail', 'id': rid, 'detail': 'incomplete response'})
        except asyncio.CancelledError:
            if not request.finished:
                self.write({'t': 'fail', 'id': rid, 'detail': 'engine stopped'})
            raise
        except Exception as exc:
            # Only the type: exception text can carry case content or a database location.
            print(f'bridge: request failed: {type(exc).__name__}', file=sys.stderr)
            if not request.finished:
                self.write({'t': 'fail', 'id': rid, 'detail': 'engine error'})
        finally:
            REQUEST_CONTEXT.reset(token)
            self._requests.pop(rid, None)

    async def _control(self, rid: str, header: dict) -> None:
        op, args = header.get('op'), header.get('args') or {}
        if op == 'shutdown':
            self._stopping = True
            self.write({'t': 'ctl.res', 'id': rid, 'ok': True, 'value': {}})
            self._frames.put_nowait(None)
            return
        try:
            if self.control is None or not isinstance(op, str) or not isinstance(args, dict):
                raise ControlError('unavailable')
            value = await self.control(op, args)
            self.write({'t': 'ctl.res', 'id': rid, 'ok': True, 'value': value})
        except ControlError as error:
            self.write({'t': 'ctl.res', 'id': rid, 'ok': False, 'error': error.code})
        except Exception as exc:
            print(f'bridge: control {op} failed: {type(exc).__name__}', file=sys.stderr)
            self.write({'t': 'ctl.res', 'id': rid, 'ok': False, 'error': 'failed'})

    async def _drain(self) -> None:
        for request in self._requests.values():
            request.inbox.put_nowait({'type': 'http.disconnect'})
        tasks = [request.task for request in self._requests.values() if request.task is not None]
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=DRAIN_SECONDS)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.wait(pending, timeout=1)

    def call_host(self, op: str, args: dict, timeout: float, *, request_id: str | None = None) -> dict:
        """Ask the host and block this worker thread for the answer. Never call it on the event loop."""
        if self._loop is None or self._stopping:
            raise HostUnavailable('bridge not running')
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            raise RuntimeError('call_host blocks; run it in a worker thread')
        rid = f'c{next(self._call_ids)}'
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._calls[rid] = future
        self.write({'t': 'call', 'id': rid, 'requestId': request_id, 'op': op, 'args': args})
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            raise HostUnavailable('host did not answer') from exc
        finally:
            self._calls.pop(rid, None)

    async def _run_lifespan(self, inbox: asyncio.Queue, outbox: asyncio.Queue) -> None:
        async def receive():
            return await inbox.get()

        try:
            await self.app({'type': 'lifespan', 'asgi': {'version': '3.0'}, 'state': {}}, receive, outbox.put)
        except Exception:
            pass
        await outbox.put(None)

    async def _lifespan_event(self, name: str) -> None:
        if self._lifespan is None:
            return
        inbox, outbox = self._lifespan
        await inbox.put({'type': f'lifespan.{name}'})
        message = await asyncio.wait_for(outbox.get(), timeout=10)
        if message is None:
            self._lifespan = None
        elif message['type'] == f'lifespan.{name}.failed':
            raise RuntimeError(f'lifespan {name} failed')


ACTIVE: Bridge | None = None


def protocol_output() -> Callable[[bytes], None]:
    """Keep fd 1 for frames only: stray prints and native writes go to stderr from here on."""
    fd = os.dup(1)
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.setmode(fd, os.O_BINARY)
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def write(data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
    return write


def run(app, *, hello: dict, control: Control | None, body_limit: int,
        stdin: BinaryIO | None = None, write: Callable[[bytes], None] | None = None) -> bool:
    """Serve frames from stdin until EOF or shutdown. Blocking. False when the peer broke the protocol."""
    global ACTIVE
    source = stdin or sys.stdin.buffer
    writer = write or protocol_output()

    async def main():
        global ACTIVE
        loop = asyncio.get_running_loop()
        frames: asyncio.Queue = asyncio.Queue()

        def pump():
            try:
                while (frame := read_frame(source)) is not None:
                    loop.call_soon_threadsafe(frames.put_nowait, frame)
                loop.call_soon_threadsafe(frames.put_nowait, None)
            except ProtocolError as error:
                print(f'bridge: {error}', file=sys.stderr)
                loop.call_soon_threadsafe(frames.put_nowait, error)
            except (OSError, ValueError):
                loop.call_soon_threadsafe(frames.put_nowait, None)

        threading.Thread(target=pump, name='bridge-stdin', daemon=True).start()
        bridge = Bridge(app, hello=hello, write=writer, control=control, body_limit=body_limit)
        ACTIVE = bridge
        try:
            await bridge.serve(frames)
        finally:
            ACTIVE = None
        return not bridge.protocol_error

    try:
        return asyncio.run(main())
    finally:
        ACTIVE = None
