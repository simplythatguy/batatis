"""One runner for every arm: resumable, keyed by config hash, with cost, latency and error accounting.

* Rows are keyed by ``sha256(config_hash | case | repeat | profile)``. A row that exists is skipped; a failed row is retried only
  with ``retry_errors`` and the new attempt is appended, so the first failure stays on record.
* Arms run interleaved case by case (A, B, A, B) in upstream-first order, so drift, warm-up and cache state fall on
  every arm alike. Repeats are the outer loop.
* The ``interactive`` profile runs one case at a time, as the product does, and is the only source of latency figures;
  ``throughput`` runs several cases at once for the accuracy runs.
* A ``budget_stop`` error ends the run at once. Nothing is retried past the ledger's stop.
"""
from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .arms import arm_hashes, topo_order
from .datasets import BenchCase
from .methods.base import Arm, RunContext
from .rows import RowStore, failed, make_row, row_key

REPO = Path(__file__).resolve().parents[2]


@dataclass
class RunSummary:
    ran: int = 0
    skipped: int = 0
    errored: int = 0
    stopped: str | None = None
    by_arm: dict[str, dict] = field(default_factory=dict)


def git_state(repo: Path = REPO) -> str | None:
    try:
        sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True, text=True, timeout=10,
                             check=True).stdout.strip()
        dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=repo, capture_output=True,
                               text=True, timeout=10, check=True).stdout.strip()
        return sha + ('+dirty' if dirty else '')
    except (OSError, subprocess.SubprocessError):
        return None


def run_arms(arms: dict[str, Arm], wanted: Sequence[str], cases: Iterable[BenchCase], ctx: RunContext, *,
             repeats: int | None = None, retry_errors: bool = False, workers: int = 1, profile: str = 'throughput',
             upstream_profile: str | None = None,
             codedb_sha256: str | None = None, git_sha: str | None = None, on_row: Callable[[dict], None] | None = None,
             stop: threading.Event | None = None) -> RunSummary:
    """Run the wanted arms (and their upstream arms) over the cases. Safe to call again: finished rows are skipped."""
    cases = list(cases)
    order = topo_order(arms, list(wanted))
    if upstream_profile:                       # shortlists come from stored rows of that profile; run only the wanted arms
        order = [n for n in order if n in wanted]
    hashes = arm_hashes(arms)
    ctx.arm_hashes = hashes
    ctx.profile = profile
    ctx.upstream_profile = upstream_profile
    if profile == 'interactive':
        workers = 1
    stop = stop or threading.Event()
    summary = RunSummary(by_arm={n: {'ran': 0, 'skipped': 0, 'errored': 0} for n in order})
    lock = threading.Lock()
    wanted_repeats = lambda a: 1 if a.deterministic else (repeats if repeats is not None else a.repeats)
    max_repeats = max(wanted_repeats(arms[n]) for n in order)

    def one(case: BenchCase, repeat: int) -> None:
        for name in order:
            if stop.is_set():
                return
            arm = arms[name]
            n_rep = wanted_repeats(arm)
            if repeat >= n_rep:
                continue
            chash = hashes[name]
            existing = ctx.store.latest(name, chash, profile).get((case.id, repeat))
            if existing is not None and not (retry_errors and existing['errors']):
                with lock:
                    summary.skipped += 1
                    summary.by_arm[name]['skipped'] += 1
                continue
            attempt = (existing['attempt'] + 1) if existing else 1
            try:
                draft = arm.run(case, repeat, ctx)
            except Exception as e:                                   # noqa: BLE001 - an arm bug must not stop the run
                from .rows import RowDraft
                draft = RowDraft(errors=[{'stage': name, 'category': 'arm_exception', 'detail': type(e).__name__}])
            row = make_row(draft, arm=name, chash=chash, case=case, repeat=repeat, attempt=attempt, profile=profile,
                           git_sha=git_sha, codedb_sha256=codedb_sha256)
            ctx.store.append(row)
            with lock:
                summary.ran += 1
                summary.by_arm[name]['ran'] += 1
                if row['errors']:
                    summary.errored += 1
                    summary.by_arm[name]['errored'] += 1
            if on_row:
                on_row(row)
            if any(e.get('category') == 'budget_stop' for e in row['errors']):
                summary.stopped = 'budget_stop'
                stop.set()
                return

    for repeat in range(max_repeats):
        if stop.is_set():
            break
        if workers <= 1:
            for case in cases:
                if stop.is_set():
                    break
                one(case, repeat)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(lambda c: one(c, repeat), cases))
    return summary


def pending(arms: dict[str, Arm], name: str, cases: Iterable[BenchCase], ctx_store: RowStore,
            repeats: int | None = None, profile: str = 'throughput') -> int:
    """How many rows of this arm are still missing (not counting failures that could be retried)."""
    chash = arm_hashes(arms)[name]
    have = ctx_store.latest(name, chash, profile)
    n_rep = 1 if arms[name].deterministic else (repeats if repeats is not None else arms[name].repeats)
    return sum(1 for c in cases for r in range(n_rep) if (c.id, r) not in have)


__all__ = ['RunSummary', 'git_state', 'pending', 'row_key', 'run_arms', 'failed']
