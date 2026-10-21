"""Spend ledger with a hard dollar stop.

Every paid call goes through three steps: ``reserve`` (refused when ``spent + reserved + this call's worst case``
would pass the stop), the call itself, then ``settle`` with the usage the provider reported, or ``release`` when the
call failed before any usage existed. Spend is recomputed from the ledger file under a file lock on every operation
(only the bytes added since the last operation are read, so a long run stays fast); no in-memory total is trusted
across processes.

* One JSON line per operation, each carrying a hash of the exact text of the line before it, so an edited or
  truncated ledger is detected (``LedgerCorrupt``) when it is opened and the run stops.
* A reservation that was never settled or released (a crash, a kill) counts at its worst case until
  ``close_orphans`` records it as unknown spend. A call whose outcome is unknown (a client timeout after the request
  was sent) is settled with ``unknown`` at its worst case, because the provider may have billed it.
* The OpenAI ledger refuses a stop above ``OPENAI_HARD_CAP_USD``: the user's decision is US$10.00 for the whole
  benchmark, leaving the rest of the credit for the live demo.
* Jev has no stop (the user said to use as much as needed); its ledger is for accounting and takes one line per
  stage, not one per request.

Keys never reach this module. Lines hold model names, token counts, dollars and the case and arm they belong to.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

OPENAI_HARD_CAP_USD = Decimal('10.00')
_GENESIS = '0' * 12


class BudgetExceeded(RuntimeError):
    """The call could push total spend past the stop; it was not made."""


class LedgerCorrupt(RuntimeError):
    """The ledger's hash chain does not verify."""


@dataclass(frozen=True)
class Reservation:
    id: str
    model: str
    worst_case_usd: Decimal


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _line_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


class Ledger:
    def __init__(self, path: Path | str, provider: str, stop_usd: Decimal | str | float | None = None):
        self.path = Path(path)
        self.provider = provider
        self.stop = None if stop_usd is None else _dec(stop_usd)
        if provider == 'openai' and (self.stop is None or self.stop > OPENAI_HARD_CAP_USD):
            raise ValueError(f'the OpenAI ledger needs a stop of at most US${OPENAI_HARD_CAP_USD}')
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._reset()
        with self._locked() as fd:                      # verify the whole chain once, when the ledger is opened
            self._sync(fd)

    # ---- incremental state ---------------------------------------------------------------------------------

    def _reset(self) -> None:
        self._pos = 0
        self._prev = _GENESIS
        self._seq = 0
        self._settled = Decimal(0)
        self._open: dict[str, Decimal] = {}
        self._requests = 0
        self._by_model: dict = defaultdict(lambda: {'requests': 0, 'input_tokens': 0, 'output_tokens': 0,
                                                    'reasoning_tokens': 0, 'cached_tokens': 0, 'usd': Decimal(0)})

    def _apply(self, r: dict) -> None:
        op = r['op']
        if op == 'reserve':
            self._open[r['id']] = _dec(r['worst_case_usd'])
        elif op in ('settle', 'unknown'):
            self._open.pop(r['id'], None)
            self._settled += _dec(r['usd'])
            self._requests += int(r.get('requests', 1))
            m = self._by_model[r.get('model') or 'unknown']
            m['requests'] += int(r.get('requests', 1))
            m['usd'] += _dec(r['usd'])
            for k in ('input_tokens', 'output_tokens', 'reasoning_tokens', 'cached_tokens'):
                m[k] += int(r.get(k, 0))
        elif op == 'release':
            self._open.pop(r['id'], None)

    def _sync(self, fd: int) -> None:
        size = os.fstat(fd).st_size
        if size < self._pos:
            raise LedgerCorrupt('ledger is shorter than it was; refusing to spend')
        os.lseek(fd, self._pos, os.SEEK_SET)
        raw = b''
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            raw += chunk
        text = raw.decode('utf-8')
        if text and not text.endswith('\n'):
            raise LedgerCorrupt('ledger ends in a partial line; refusing to spend')
        for line in text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get('prev') != self._prev or row.get('seq') != self._seq + 1:
                raise LedgerCorrupt('ledger hash chain broken; refusing to spend')
            self._apply(row)
            self._prev = _line_hash(line)
            self._seq += 1
        self._pos += len(raw)

    @contextmanager
    def _locked(self):
        with self._lock:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield fd
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def _write(self, fd: int, row: dict) -> None:
        line = json.dumps({'seq': self._seq + 1, 'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **row,
                           'prev': self._prev}, sort_keys=True)
        os.lseek(fd, 0, os.SEEK_END)
        os.write(fd, (line + '\n').encode('utf-8'))
        os.fsync(fd)
        self._sync(fd)                                   # re-read what was just written: state comes from the file

    @property
    def _reserved(self) -> Decimal:
        return sum(self._open.values(), Decimal(0))

    # ---- queries ---------------------------------------------------------------------------------------------

    def spent(self) -> Decimal:
        """Settled spend plus every open reservation at its worst case."""
        with self._locked() as fd:
            self._sync(fd)
            return self._settled + self._reserved

    def settled(self) -> Decimal:
        with self._locked() as fd:
            self._sync(fd)
            return self._settled

    # ---- operations ------------------------------------------------------------------------------------------

    def reserve(self, *, model: str, worst_case_usd: Decimal | str | float, arm: str = '', case: str = '') -> Reservation:
        worst = _dec(worst_case_usd)
        with self._locked() as fd:
            self._sync(fd)
            if self.stop is not None and self._settled + self._reserved + worst > self.stop:
                raise BudgetExceeded(
                    f'{self.provider}: spent {self._settled:.4f} + reserved {self._reserved:.4f} + this call '
                    f'{worst:.4f} would pass the stop of {self.stop}')
            rid = uuid.uuid4().hex[:12]
            self._write(fd, {'op': 'reserve', 'id': rid, 'model': model, 'worst_case_usd': str(worst), 'arm': arm,
                             'case': case})
        return Reservation(rid, model, worst)

    def settle(self, res: Reservation, *, usd: Decimal | str | float, input_tokens: int = 0, output_tokens: int = 0,
               cached_tokens: int = 0, reasoning_tokens: int = 0, requests: int = 1, request_id: str | None = None,
               returned_model: str | None = None, arm: str = '', case: str = '') -> Decimal:
        """Record what the provider reported. Returns total spend after this call, recomputed from the file."""
        with self._locked() as fd:
            self._sync(fd)
            self._write(fd, {'op': 'settle', 'id': res.id, 'model': res.model, 'usd': str(_dec(usd)),
                             'input_tokens': int(input_tokens), 'output_tokens': int(output_tokens),
                             'cached_tokens': int(cached_tokens), 'reasoning_tokens': int(reasoning_tokens),
                             'requests': int(requests), 'request_id': request_id, 'returned_model': returned_model,
                             'arm': arm, 'case': case})
            return self._settled + self._reserved

    def unknown(self, res: Reservation, reason: str, *, arm: str = '', case: str = '') -> Decimal:
        """The call may have been billed but no usage came back: charge its worst case."""
        with self._locked() as fd:
            self._sync(fd)
            self._write(fd, {'op': 'unknown', 'id': res.id, 'model': res.model, 'usd': str(res.worst_case_usd),
                             'reason': reason, 'arm': arm, 'case': case})
            return self._settled + self._reserved

    def record(self, *, model: str, usd: Decimal | str | float, requests: int = 1, input_tokens: int = 0,
               output_tokens: int = 0, arm: str = '', case: str = '') -> Decimal:
        """One accounting line for a provider with no stop (Jev): no reservation step, one line per stage."""
        if self.stop is not None:
            raise ValueError('a ledger with a stop must reserve before it spends')
        with self._locked() as fd:
            self._sync(fd)
            self._write(fd, {'op': 'settle', 'id': uuid.uuid4().hex[:12], 'model': model, 'usd': str(_dec(usd)),
                             'input_tokens': int(input_tokens), 'output_tokens': int(output_tokens),
                             'cached_tokens': 0, 'reasoning_tokens': 0, 'requests': int(requests), 'arm': arm, 'case': case})
            return self._settled + self._reserved

    def release(self, res: Reservation) -> None:
        """The request was never sent or was rejected before any usage: give the reservation back."""
        with self._locked() as fd:
            self._sync(fd)
            self._write(fd, {'op': 'release', 'id': res.id})

    def close_orphans(self, reason: str = 'orphaned reservation') -> int:
        """Charge every open reservation at its worst case and close it. Call only when no run is active."""
        n = 0
        with self._locked() as fd:
            self._sync(fd)
            for rid, worst in list(self._open.items()):
                self._write(fd, {'op': 'unknown', 'id': rid, 'model': '', 'usd': str(worst), 'reason': reason})
                n += 1
        return n

    # ---- reporting -------------------------------------------------------------------------------------------

    def summary(self) -> dict:
        with self._locked() as fd:
            self._sync(fd)
            return {
                'provider': self.provider,
                'stop_usd': None if self.stop is None else str(self.stop),
                'settled_usd': str(self._settled), 'reserved_open_usd': str(self._reserved),
                'spent_usd': str(self._settled + self._reserved),
                'remaining_usd': None if self.stop is None else str(self.stop - self._settled - self._reserved),
                'requests': self._requests, 'open_reservations': len(self._open),
                'by_model': {k: {**v, 'usd': str(v['usd'])} for k, v in sorted(self._by_model.items())},
            }
