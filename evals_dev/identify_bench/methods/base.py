"""The arm interface every identification method implements, and the context the runner hands it.

An *arm* is one stage of a pipeline: a candidate generator (BM25, precedent matching, the Jev screen), a reranker, a
fusion, or a verifier. A pipeline is a chain of arms; each arm reads its upstream arm's stored row for the same case.
``config()`` is plain JSON and is hashed together with the upstream hashes, so changing any model id, size, prompt
or upstream arm gives the downstream rows a new key and nothing stale is reused.

The contract every adapter meets (see ``tests/test_identify_bench_contract.py``, which runs it against fakes):

* ``run`` returns a ``RowDraft``; provider failures become ``errors`` entries, never exceptions;
* ``order`` holds corpus article ids only, with no duplicates;
* ``probabilities`` are in [0, 1] and only for ids in ``order``;
* token counts and dollars are not negative, and ``config()`` is JSON-serialisable and stable.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from evals_dev.identify_bench.datasets import BenchCase
from evals_dev.identify_bench.ledger import Ledger
from evals_dev.identify_bench.rows import RowDraft, RowStore
from evals_dev.identify_bench.transports import OpenAIChat


class UpstreamMissing(RuntimeError):
    """The upstream arm has no usable row for this case and repeat."""


@dataclass
class RunContext:
    arts: dict[str, dict]
    store: RowStore
    arm_hashes: dict[str, str] = field(default_factory=dict)
    db_path: Path | None = None
    openai: OpenAIChat | None = None
    jev_ask: Callable[[str], Callable] | None = None        # model -> ask(state, questions, timeout)
    jev_ledger: Ledger | None = None
    profile: str = 'throughput'
    repo_root: Path | None = None
    clock: Callable[[], float] = time.monotonic

    def upstream(self, arm: str, case: BenchCase, repeat: int, *, clamp: bool = False) -> dict:
        """The latest stored row of ``arm`` for this case and repeat; raises ``UpstreamMissing`` if absent or failed.

        ``clamp`` falls back to the highest repeat below ``repeat``: a deterministic upstream arm has repeat 0 only.
        """
        chash = self.arm_hashes.get(arm)
        latest = self.store.latest(arm, chash, self.profile)
        row = latest.get((case.id, repeat))
        while row is None and clamp and repeat > 0:
            repeat -= 1
            row = latest.get((case.id, repeat))
        if row is None:
            raise UpstreamMissing(f'{arm} has no row for {case.id} repeat {repeat}')
        if not row['order']:
            raise UpstreamMissing(f'{arm} failed on {case.id} repeat {repeat}')
        return row


class Arm:
    """Base class. Subclasses set ``name`` and ``kind`` and implement ``config`` and ``run``."""

    name: str = ''
    kind: str = ''
    upstream_names: tuple[str, ...] = ()
    repeats: int = 1                      # how many repeats this arm needs by default (deterministic arms: 1)
    deterministic: bool = False           # True: one repeat is the whole answer, whatever --repeats asks for
    live: bool = False                    # True when run() may call a paid provider
    provider: str | None = None           # 'jev' or 'openai' when live

    def config(self) -> dict:
        raise NotImplementedError

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        raise NotImplementedError


def unique_in(order: list[str], arts: dict[str, dict]) -> list[str]:
    """``order`` restricted to corpus ids, first occurrence kept."""
    seen: set[str] = set()
    out: list[str] = []
    for a in order:
        if a in arts and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def append_rest(head: list[str], rest: list[str]) -> list[str]:
    """``head`` followed by the ids of ``rest`` not already in it."""
    seen = set(head)
    return head + [a for a in rest if a not in seen]
