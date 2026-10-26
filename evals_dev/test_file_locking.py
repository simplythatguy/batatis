"""Portable cache and ledger checks use temporary files and spawned processes."""
from __future__ import annotations

import importlib
import multiprocessing
import os
from contextlib import contextmanager
from pathlib import Path

import pytest


WAIT_SECONDS = 15
CONTENTION_SECONDS = 0.25


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


def _claim_response(directory, ready, dispatched, deliver):
    from evals_dev.identify_bench.cache import Store

    store = Store('answers', Path(directory))
    ready.set()
    with store.claim('identical-request'):
        if store.get('identical-request') is None:
            with (Path(directory) / 'dispatches').open('ab') as handle:
                handle.write(b'dispatched\n')
            dispatched.set()
            assert deliver.wait(WAIT_SECONDS), 'fake provider response was never delivered'
            store.put('identical-request', {'answer': 42})


def _hold_lock(path, shared, mode, offset, attempting, acquired, release, payload, abrupt_exit):
    from evals_dev.file_lock import file_lock

    with Path(path).open(mode) as handle:
        handle.seek(offset)
        attempting.set()
        with file_lock(handle, shared=shared):
            assert handle.tell() == offset
            acquired.set()
            assert release.wait(WAIT_SECONDS), 'lock was never released'
            if payload:
                handle.seek(0, os.SEEK_END)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            position = handle.tell()
            if abrupt_exit:
                os._exit(0)
        assert handle.tell() == position


def _start_lock(context, start, path, *, shared=False, mode='a+b', offset=0,
                payload=b'', abrupt_exit=False):
    attempting, acquired, release = (context.Event() for _ in range(3))
    process = start(_hold_lock, str(path), shared, mode, offset, attempting, acquired,
                    release, payload, abrupt_exit)
    assert attempting.wait(WAIT_SECONDS), 'lock worker did not start'
    return process, acquired, release


@pytest.mark.parametrize('module', [
    'evals_dev.identify_bench.cache',
    'evals_dev.data_prompts.ledger',
])
def test_stores_import_on_this_platform(module):
    importlib.import_module(module)


def test_identical_cache_claims_dispatch_once_across_processes(tmp_path):
    from evals_dev.identify_bench.cache import Store

    with _processes() as (context, start):
        deliver = context.Event()
        first_ready, first_dispatched = context.Event(), context.Event()
        first = start(_claim_response, str(tmp_path), first_ready, first_dispatched, deliver)
        assert first_dispatched.wait(WAIT_SECONDS), 'first cache miss did not dispatch'
        ready = [context.Event() for _ in range(4)]
        dispatched = [context.Event() for _ in ready]
        workers = [start(_claim_response, str(tmp_path), event, called, deliver)
                   for event, called in zip(ready, dispatched)]
        for event in ready:
            assert event.wait(WAIT_SECONDS), 'cache worker did not start'
        for event in dispatched:
            assert not event.wait(CONTENTION_SECONDS), 'identical request dispatched before its claim'
        deliver.set()
        for worker in [first, *workers]:
            _join(worker)

    assert (tmp_path / 'dispatches').read_bytes() == b'dispatched\n'
    store = Store('answers', tmp_path)
    assert store.get('identical-request') == {'answer': 42}
    assert len(store.rows()) == 1


@pytest.mark.parametrize('initial', [b'', b'initial\n'], ids=['empty', 'nonempty'])
def test_shared_readers_coexist_and_writer_waits_for_every_reader(tmp_path, initial):
    path = tmp_path / 'locked'
    path.write_bytes(initial)
    with _processes() as (context, start):
        first, first_acquired, release_first = _start_lock(
            context, start, path, shared=True, mode='rb', offset=17)
        assert first_acquired.wait(WAIT_SECONDS), 'first reader could not acquire'
        second, second_acquired, release_second = _start_lock(
            context, start, path, shared=True, mode='rb', offset=89)
        assert second_acquired.wait(WAIT_SECONDS), 'shared readers could not coexist'
        writer, writer_acquired, release_writer = _start_lock(context, start, path, offset=193)
        assert not writer_acquired.wait(CONTENTION_SECONDS), 'writer bypassed shared readers'
        release_first.set()
        _join(first)
        assert not writer_acquired.wait(CONTENTION_SECONDS), 'writer bypassed the remaining reader'
        release_second.set()
        _join(second)
        assert writer_acquired.wait(WAIT_SECONDS), 'writer remained blocked after both readers released'
        release_writer.set()
        _join(writer)
    assert path.read_bytes() == initial


@pytest.mark.parametrize('abrupt_exit', [False, True], ids=['context-exit', 'process-exit'])
def test_exclusive_locks_serialize_appends_and_release_on_exit(tmp_path, abrupt_exit):
    path = tmp_path / 'locked'
    path.touch()
    with _processes() as (context, start):
        first, first_acquired, release_first = _start_lock(
            context, start, path, offset=23, payload=b'first\n', abrupt_exit=abrupt_exit)
        assert first_acquired.wait(WAIT_SECONDS), 'first writer could not acquire'
        second, second_acquired, release_second = _start_lock(
            context, start, path, offset=107, payload=b'second\n')
        assert not second_acquired.wait(CONTENTION_SECONDS), 'exclusive writers overlapped'
        release_first.set()
        _join(first)
        assert second_acquired.wait(WAIT_SECONDS), 'writer remained blocked after the first exited'
        release_second.set()
        _join(second)
    assert path.read_bytes() == b'first\nsecond\n'


@pytest.mark.skipif(os.name != 'nt', reason='Windows CRT has a limited blocking retry window')
def test_windows_exclusive_lock_waits_past_the_crt_retry_window(tmp_path):
    from evals_dev.file_lock import file_lock

    path = tmp_path / 'locked'
    with _processes() as (context, start):
        with path.open('a+b') as handle, file_lock(handle):
            worker, acquired, release = _start_lock(context, start, path)
            assert not acquired.wait(11), 'exclusive lock bypassed its holder'
            assert worker.is_alive(), 'blocking acquisition gave up before the holder released'
        assert acquired.wait(WAIT_SECONDS), 'exclusive lock did not acquire after the holder released'
        release.set()
        _join(worker)


def test_exception_unlocks_without_closing_the_handle(tmp_path):
    from evals_dev.file_lock import file_lock

    path = tmp_path / 'locked'
    with path.open('a+b') as handle, _processes() as (context, start):
        with pytest.raises(RuntimeError, match='caller failed'):
            with file_lock(handle):
                raise RuntimeError('caller failed')
        assert not handle.closed
        reader, acquired, release = _start_lock(context, start, path, shared=True, mode='rb')
        assert acquired.wait(WAIT_SECONDS), 'exception left the open handle locked'
        release.set()
        _join(reader)


@pytest.mark.parametrize(('mode', 'shared', 'expected'), [
    ('rb', True, b'alpha\n'),
    ('r+b', False, b'alXXa\n'),
    ('a', False, b'alpha\nXX'),
    ('a+b', False, b'alpha\nXX'),
])
def test_lock_preserves_mode_position_and_file_contents(tmp_path, mode, shared, expected):
    from evals_dev.file_lock import file_lock

    path = tmp_path / 'locked'
    path.write_bytes(b'alpha\n')
    with path.open(mode) as handle:
        handle.seek(2)
        original_mode = handle.mode
        with file_lock(handle, shared=shared):
            assert handle.tell() == 2
            assert handle.mode == original_mode
            if mode == 'rb':
                assert handle.read(2) == b'ph'
            else:
                handle.write(b'XX' if 'b' in mode else 'XX')
                handle.flush()
                os.fsync(handle.fileno())
            position = handle.tell()
        assert handle.tell() == position
        assert handle.mode == original_mode
        assert not handle.closed
    assert path.read_bytes() == expected


def test_lock_failure_is_an_oserror_and_never_enters_the_body(tmp_path):
    from evals_dev.file_lock import file_lock
    from evals_dev.identify_bench.live import error_tag

    with (tmp_path / 'locked').open('a+b') as handle:
        descriptor = handle.fileno()
    with pytest.raises(OSError) as error:
        with file_lock(descriptor):
            pytest.fail('a failed lock must not enter the protected body')
    assert error_tag(error.value) == 'io_error'


@pytest.mark.skipif(os.name == 'nt', reason='interoperability with existing POSIX flock users')
@pytest.mark.parametrize('shared', [False, True], ids=['legacy-writer', 'legacy-reader'])
def test_posix_locks_contend_with_existing_flock_users(tmp_path, shared):
    import fcntl

    path = tmp_path / 'locked'
    with path.open('a+b') as handle, _processes() as (context, start):
        fcntl.flock(handle, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        try:
            worker, acquired, release = _start_lock(context, start, path, shared=not shared)
            assert not acquired.wait(CONTENTION_SECONDS), 'new helper bypassed an existing flock'
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
        assert acquired.wait(WAIT_SECONDS), 'new helper remained blocked after flock released'
        release.set()
        _join(worker)
