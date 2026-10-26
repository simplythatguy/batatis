"""Portable cache and ledger checks use temporary files and spawned processes."""
from __future__ import annotations

import importlib
import multiprocessing
from contextlib import contextmanager
from pathlib import Path

import pytest


WAIT_SECONDS = 15


@contextmanager
def _processes():
    context = multiprocessing.get_context('spawn')
    processes = []

    def start(target, *args):
        process = context.Process(target=target, args=args)
        process.start()
        processes.append(process)
        return process

    try:
        yield context, start
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(WAIT_SECONDS)
            if process.is_alive():
                process.kill()
                process.join(WAIT_SECONDS)
            process.close()


def _join(process):
    process.join(WAIT_SECONDS)
    assert not process.is_alive(), 'worker did not finish'
    assert process.exitcode == 0


def _claim_response(directory, ready, begin):
    from evals_dev.identify_bench.cache import Store

    store = Store('answers', Path(directory))
    ready.set()
    assert begin.wait(WAIT_SECONDS), 'claim was never started'
    with store.claim('identical-request'):
        if store.get('identical-request') is None:
            with (Path(directory) / 'dispatches').open('ab') as handle:
                handle.write(b'dispatched\n')
            store.put('identical-request', {'answer': 42})


@pytest.mark.parametrize('module', [
    'evals_dev.identify_bench.cache',
    'evals_dev.data_prompts.ledger',
])
def test_stores_import_on_this_platform(module):
    importlib.import_module(module)


def test_identical_cache_claims_dispatch_once_across_processes(tmp_path):
    from evals_dev.identify_bench.cache import Store

    with _processes() as (context, start):
        begin = context.Event()
        ready = [context.Event() for _ in range(4)]
        workers = [start(_claim_response, str(tmp_path), event, begin) for event in ready]
        for event in ready:
            assert event.wait(WAIT_SECONDS), 'cache worker did not start'
        begin.set()
        for worker in workers:
            _join(worker)

    assert (tmp_path / 'dispatches').read_bytes() == b'dispatched\n'
    store = Store('answers', tmp_path)
    assert store.get('identical-request') == {'answer': 42}
    assert len(store.rows()) == 1
