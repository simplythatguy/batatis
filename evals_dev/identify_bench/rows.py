"""Result rows and their store.

One row is one stage of one arm on one case and repeat. Every number in every report is a pure function of these
rows plus the datasets. Rows are append-only JSON lines: a re-run of a failed row appends a new attempt, and the
latest attempt wins while the earlier error stays in the file.

    {key, case_id, dataset, fold, part_group, arm, config_hash, repeat, attempt, profile,
     order[], probabilities{}, picks[], dropped[], upstream{arm: key}, tokens{provider: {...}}, usd,
     latency_ms{stage}, errors[], model_ids{}, cached, source, git_sha, codedb_sha256, started_at, notes{}}

``order`` is the ranked list this stage hands on (a verifier arm puts its quote-checked picks first, then the rest of
its upstream order). ``tokens`` and ``usd`` and ``latency_ms`` are this stage's own; a pipeline's cost and latency
are the sums along ``upstream``. Cached or recorded rows are marked and excluded from every latency figure.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / 'results'
ORDER_KEEP = 100                       # ranked ids kept per row
SCREEN_ORDER_KEEP = 300                # screens and rerankers: recall@200 is a reported ceiling, so keep past it
PROB_KEEP = 60


def config_hash(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]


def row_key(chash: str, case_id: str, repeat: int) -> str:
    return hashlib.sha256(f'{chash}|{case_id}|{repeat}'.encode()).hexdigest()[:16]


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


@dataclass
class RowDraft:
    """What an arm returns; the runner turns it into a stored row."""
    order: list[str] = field(default_factory=list)
    probabilities: dict[str, float] = field(default_factory=dict)
    picks: list[dict] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    upstream: dict[str, str] = field(default_factory=dict)
    tokens: dict[str, dict] = field(default_factory=dict)
    usd: float = 0.0
    latency_ms: dict[str, float] = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)
    model_ids: dict = field(default_factory=dict)
    cached: bool = False
    source: str = 'live'
    notes: dict = field(default_factory=dict)
    order_keep: int | None = ORDER_KEEP         # None keeps the whole ranking (recorded Stage 0 rows)


def make_row(draft: RowDraft, *, arm: str, chash: str, case, repeat: int, attempt: int, profile: str, git_sha: str | None,
             codedb_sha256: str | None, started_at: str | None = None) -> dict:
    return {
        'key': row_key(chash, case.id, repeat), 'case_id': case.id, 'dataset': case.dataset, 'fold': case.fold,
        'part_group': case.part_group, 'arm': arm, 'config_hash': chash, 'repeat': repeat, 'attempt': attempt,
        'profile': profile,
        'order': draft.order if draft.order_keep is None else draft.order[:draft.order_keep],
        'probabilities': {a: round(p, 4) for a, p in list(draft.probabilities.items())[:PROB_KEEP]},
        'picks': draft.picks, 'dropped': draft.dropped, 'upstream': draft.upstream, 'tokens': draft.tokens,
        'usd': round(float(draft.usd), 8), 'latency_ms': {k: round(v, 1) for k, v in draft.latency_ms.items()},
        'errors': draft.errors, 'model_ids': draft.model_ids, 'cached': draft.cached, 'source': draft.source,
        'git_sha': git_sha, 'codedb_sha256': codedb_sha256, 'started_at': started_at or now(), 'notes': draft.notes,
    }


def failed(row: dict) -> bool:
    """A row that produced no usable ranking."""
    return bool(row['errors']) and not row['order']


class RowStore:
    """Rows on disk: ``<dir>/<arm>.jsonl`` while a run is active, ``<arm>.jsonl.gz`` once packed."""

    def __init__(self, directory: Path | str = RESULTS):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, list[dict]] = {}

    def _paths(self, arm: str) -> list[Path]:
        return [p for p in (self.dir / f'{arm}.jsonl.gz', self.dir / f'{arm}.jsonl') if p.exists()]

    @staticmethod
    def _read(path: Path) -> Iterator[dict]:
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)

    def arm_rows(self, arm: str) -> list[dict]:
        """Every row of an arm in file order, packed rows first. Earlier attempts are kept."""
        with self._lock:
            if arm not in self._cache:
                seen, rows = set(), []
                for path in self._paths(arm):
                    for r in self._read(path):
                        ident = (r['key'], r['attempt'])
                        if ident not in seen:
                            seen.add(ident)
                            rows.append(r)
                self._cache[arm] = rows
            return list(self._cache[arm])

    def append(self, row: dict) -> None:
        line = json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n'
        path = self.dir / f"{row['arm']}.jsonl"
        with self._lock:
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                os.write(fd, line.encode('utf-8'))
                os.fsync(fd)
            finally:
                os.close(fd)
            if row['arm'] in self._cache:
                self._cache[row['arm']].append(row)

    def latest(self, arm: str, chash: str | None = None) -> dict[tuple[str, int], dict]:
        """(case_id, repeat) -> the latest attempt of each row, for one config hash (default: the newest in the file)."""
        rows = self.arm_rows(arm)
        if chash is None and rows:
            chash = rows[-1]['config_hash']
        out: dict[tuple[str, int], dict] = {}
        for r in rows:
            if r['config_hash'] == chash:
                prev = out.get((r['case_id'], r['repeat']))
                if prev is None or r['attempt'] >= prev['attempt']:
                    out[(r['case_id'], r['repeat'])] = r
        return out

    def arms(self) -> list[str]:
        names = {p.name.split('.jsonl')[0] for p in self.dir.glob('*.jsonl*')}
        return sorted(names)

    def by_key(self, arm: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for r in self.arm_rows(arm):
            if r['key'] not in out or r['attempt'] >= out[r['key']]['attempt']:
                out[r['key']] = r
        return out

    def pack(self, arm: str) -> Path:
        """Write ``<arm>.jsonl.gz`` deterministically (sorted by key and attempt, no timestamp in the gzip header)."""
        rows = sorted(self.arm_rows(arm), key=lambda r: (r['key'], r['attempt']))
        target = self.dir / f'{arm}.jsonl.gz'
        tmp = target.with_suffix('.gz.tmp')
        with open(tmp, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, compresslevel=9) as gz:
            for r in rows:
                gz.write((json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8'))
        os.replace(tmp, target)
        plain = self.dir / f'{arm}.jsonl'
        if plain.exists():
            plain.unlink()
        self._cache.pop(arm, None)
        return target


def group_by_case(rows: Iterable[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out[r['case_id']].append(r)
    return out
