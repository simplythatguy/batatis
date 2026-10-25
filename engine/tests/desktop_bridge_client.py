"""A test-side host for `python -m engine.desktop`: real process, real pipes, no socket."""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import threading
import queue
from dataclasses import dataclass, field
from pathlib import Path

from engine.desktop.bridge import MAX_BODY, encode, read_frame

ROOT = Path(__file__).resolve().parents[2]
STDERR_LIMIT = 64 * 1024


@dataclass
class Reply:
    status: int
    headers: dict[str, list[str]]
    body: bytes
    frames: int = 0
    failed: str | None = None
    chunks: list[bytes] = field(default_factory=list)

    def json(self):
        return json.loads(self.body)

    def header(self, name: str) -> str | None:
        values = self.headers.get(name.lower())
        return values[-1] if values else None


def engine_env(kind: str, root: Path, codedb: Path | None = None, **extra: str) -> dict[str, str]:
    home = root / 'engine-home'
    home.mkdir(parents=True, exist_ok=True)
    env = {key.upper(): value for key, value in os.environ.items()
           if key.upper() in {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR',
                              'LANG', 'LC_ALL', 'LC_CTYPE'}}
    env.update(HOME=str(home), USERPROFILE=str(home), PYTHONNOUSERSITE='1')
    env.update(BATATIS_DESKTOP_WORKSPACE=kind, BATATIS_CASES=str(root / kind / 'cases.sqlite'),
               BATATIS_CODEDB=str(codedb or root / 'no-codedb' / 'codedb.sqlite'), PYTHONDONTWRITEBYTECODE='1')
    env.update(extra)
    return env


def engine_command() -> tuple[list[str], Path]:
    """BATATIS_DESKTOP_ENGINE_EXE runs these tests against a frozen engine build instead of the source."""
    frozen = os.environ.get('BATATIS_DESKTOP_ENGINE_EXE')
    if frozen:
        return [frozen], Path(frozen).parent
    return [sys.executable, '-m', 'engine.desktop'], ROOT


class EngineProcess:
    def __init__(self, env: dict[str, str]):
        command, cwd = engine_command()
        self.proc = subprocess.Popen(command, cwd=cwd, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.frames: queue.Queue = queue.Queue()
        self.ids = itertools.count(1)
        self.lock = threading.Lock()
        self.stderr = bytearray()
        self.readers = (threading.Thread(target=self._pump, daemon=True),
                        threading.Thread(target=self._collect_stderr, daemon=True))
        for reader in self.readers:
            reader.start()
        try:
            self.hello, _ = self.next_frame(timeout=60)
        except Exception as error:
            try:
                self.close(timeout=5)
            except Exception as cleanup_error:
                error.add_note(f'engine startup cleanup raised {cleanup_error!r}')
            diagnostic = self.stderr.decode('utf-8', errors='replace')
            error.add_note(f'engine startup failed; exit code {self.proc.poll()}\n'
                           f'stderr tail ({STDERR_LIMIT} byte limit):\n{diagnostic or "<empty>"}')
            raise

    def _collect_stderr(self):
        while chunk := self.proc.stderr.read1(4096):
            self.stderr.extend(chunk)
            del self.stderr[:-STDERR_LIMIT]

    def _pump(self):
        try:
            while (frame := read_frame(self.proc.stdout)) is not None:
                self.frames.put(frame)
        except Exception as error:   # surfaced to the test through the queue
            self.frames.put(('error', error))
        self.frames.put(None)

    def next_frame(self, timeout: float = 30):
        item = self.frames.get(timeout=timeout)
        if item is None:
            raise EOFError('engine closed its output')
        if item[0] == 'error':
            raise item[1]
        return item

    def send(self, header: dict, body: bytes = b''):
        with self.lock:
            self.proc.stdin.write(encode(header, body))
            self.proc.stdin.flush()

    def start(self, method: str, path: str, *, body: bytes = b'', headers: list[list[str]] | None = None,
              query: str = '', token: str | None = None) -> str:
        rid = f'r{next(self.ids)}'
        hdrs = list(headers or [])
        if token:
            hdrs.append(['cookie', f'batatis_session={token}'])
        self.send({'t': 'req', 'id': rid, 'method': method, 'path': path, 'query': query, 'headers': hdrs})
        chunks = [body[i:i + MAX_BODY] for i in range(0, len(body), MAX_BODY)] or [b'']
        for n, chunk in enumerate(chunks):
            self.send({'t': 'body', 'id': rid, 'more': n < len(chunks) - 1}, chunk)
        return rid

    def collect(self, rid: str, timeout: float = 60) -> Reply:
        reply = Reply(status=0, headers={}, body=b'')
        while True:
            header, body = self.next_frame(timeout)
            if header.get('id') != rid:
                continue
            reply.frames += 1
            if header['t'] == 'start':
                reply.status = header['status']
                for name, value in header['headers']:
                    reply.headers.setdefault(name.lower(), []).append(value)
            elif header['t'] == 'body':
                reply.chunks.append(body)
                if not header['more']:
                    reply.body = b''.join(reply.chunks)
                    return reply
            elif header['t'] == 'fail':
                reply.failed = header['detail']
                return reply

    def request(self, method: str, path: str, *, json_body=None, token: str | None = None, **kwargs) -> Reply:
        if json_body is not None:
            kwargs['body'] = json.dumps(json_body).encode()
            kwargs['headers'] = [['content-type', 'application/json'], *(kwargs.get('headers') or [])]
        return self.collect(self.start(method, path, token=token, **kwargs))

    def control(self, op: str, args: dict | None = None, timeout: float = 30) -> dict:
        rid = f'k{next(self.ids)}'
        self.send({'t': 'ctl', 'id': rid, 'op': op, 'args': args or {}})
        while True:
            header, _ = self.next_frame(timeout)
            if header.get('t') == 'ctl.res' and header.get('id') == rid:
                return header

    def close(self, timeout: float = 20) -> int:
        try:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
            return self.proc.wait(timeout=timeout)
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(timeout=5)
            for reader in self.readers:
                reader.join(timeout=5)
            if any(reader.is_alive() for reader in self.readers):
                raise RuntimeError('engine pipe collectors did not stop')
            self.proc.stdout.close()
            self.proc.stderr.close()
