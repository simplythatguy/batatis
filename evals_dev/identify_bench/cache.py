"""Content-addressed response cache: a provider request is never sent twice.

Keys are the sha256 of the canonical request. Entries are appended to one JSONL file per provider
under evals_dev/identify_bench/cache/ (git-ignored). Elephant's free quota is small, so every
answer is kept; rerunning an arm replays cached answers and only sends what is new.

Several benchmark processes may run at once: appends take an exclusive file lock, and a miss
re-reads rows other processes appended since this process loaded the file.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from evals_dev.file_lock import file_lock

CACHE_DIR = Path(__file__).resolve().parent / 'cache'
_claim_locks: dict[str, threading.Lock] = {}
_claim_guard = threading.Lock()


class CacheError(RuntimeError):
    """Corrupt complete cache rows fail closed, without exposing their contents or local path."""


def atomic_json(path: Path, value) -> None:
    """Serialize before touching the destination, then replace it with one complete JSON document."""
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=1) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '-', delete=False) as f:
            temporary = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _stamp(paths) -> tuple:
    return tuple((p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ctime_ns)
                 if p.exists() else None for p in paths)


@lru_cache(maxsize=8)
def _fingerprint(paths: tuple[Path, ...], stamp: tuple) -> str:
    h = hashlib.sha256()
    for i, path in enumerate(paths):
        h.update(str(i).encode())
        if stamp[i] is None:
            h.update(b'absent')
            continue
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
    if _stamp(paths) != stamp:
        raise CacheError('corpus_changed')
    return h.hexdigest()


def corpus_fingerprint(db: Path) -> str:
    """Content identity, including SQLite WAL if present. Returns no path or machine identity."""
    paths = (db.resolve(), Path(str(db.resolve()) + '-wal'))
    stamp = _stamp(paths)
    if stamp[0] is None:
        raise CacheError('corpus_unavailable')
    return _fingerprint(paths, stamp)


def request_key(kind: str, request) -> str:
    blob = json.dumps({'kind': kind, 'request': request}, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


class Store:
    def __init__(self, name: str, directory: Path = CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f'{name}.jsonl'
        self._lock = threading.Lock()
        self._rows: dict[str, dict] = {}
        self._offset = 0
        self._inode = None
        self._load()

    def _load(self) -> None:
        """Read rows appended since the last load (whole lines only)."""
        if not self.path.is_file():
            return
        with self.path.open('rb') as f, file_lock(f, shared=True):
            stat = os.fstat(f.fileno())
            if self._inode != stat.st_ino or stat.st_size < self._offset:
                self._rows.clear()
                self._offset = 0
            self._inode = stat.st_ino
            f.seek(self._offset)
            data = f.read()
        end = data.rfind(b'\n') + 1
        try:
            # JSONL records end only at LF bytes. Unicode line separators are valid
            # literal characters inside JSON strings written with ensure_ascii=False.
            for line in data[:end].split(b'\n'):
                if line.strip():
                    row = json.loads(line.decode('utf-8'))
                    self._rows[row['key']] = row
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise CacheError('cache_corrupt') from None
        self._offset += end

    def get(self, key: str):
        with self._lock:
            self._load()
            row = self._rows.get(key)
        return None if row is None else row['response']

    def put(self, key: str, response, **meta) -> None:
        row = {'key': key, 'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'response': response, **meta}
        line = (json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
        with self._lock:
            with self.path.open('a+b') as f, file_lock(f):
                # A process may have died halfway through its append. Keep all complete rows,
                # remove only the unfinished tail before appending another complete record.
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size:
                    f.seek(-1, os.SEEK_END)
                    if f.read(1) != b'\n':
                        end = size
                        while end:
                            start = max(0, end - 8192)
                            f.seek(start)
                            block = f.read(end - start)
                            newline = block.rfind(b'\n')
                            if newline >= 0:
                                f.truncate(start + newline + 1)
                                break
                            end = start
                        else:
                            f.truncate(0)
                f.seek(0, os.SEEK_END)
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            self._rows[key] = row

    @contextmanager
    def claim(self, key: str):
        """Serialize check -> dispatch -> save for a key across threads AND processes.

        Separate lock files remain stable while the JSONL grows. Callers must recheck the cache
        after acquiring the claim. A spend-ledger claim can also serialize conservative reservations.
        """
        directory = self.path.parent / '.locks'
        directory.mkdir(exist_ok=True)
        path = directory / (self.path.name + '-' + request_key('claim', key) + '.lock')
        with _claim_guard:
            lock = _claim_locks.setdefault(str(path.resolve()), threading.Lock())
        with lock, path.open('a+b') as f, file_lock(f):
            yield

    def __len__(self) -> int:
        return len(self.rows())

    def rows(self, refresh: bool = True) -> list[dict]:
        with self._lock:
            if refresh:
                self._load()
            return list(self._rows.values())
