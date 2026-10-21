"""Registration and the run-once lock for the held-out test split.

The 32 test scenarios are run once, at gate G4 time, for the arms registered beforehand (the winner and the BM25
floor). This module keeps that promise mechanically, in the judge folder, outside the repository clone:

* ``register_arm`` freezes what will be run (label, command, environment overrides, pipeline config hash). An arm
  cannot be registered twice.
* ``acquire_run`` takes ``run-test-<arm>.lock`` with ``O_CREAT | O_EXCL``, so two processes cannot both pass. The lock
  is taken before the SUT starts: a crash still consumes the run.
* A second run, or a re-registration, refuses (exit 3) unless the caller gives an override reason of at least
  ``MIN_REASON`` characters. Every override is appended to ``state/overrides.log`` with the previous lock, and the
  printed result says ``override: true`` so a report cannot hide it.
"""
from __future__ import annotations

import fcntl
import getpass
import hashlib
import json
import os
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from .dataset import JudgeDir

MIN_REASON = 20
_NAME = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,39}$')


class RunOnceError(Exception):
    """A refusal the CLI reports with exit status 3."""


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def git_sha(cwd: Path | None = None) -> str | None:
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=cwd or Path(__file__).resolve().parents[2],
                              capture_output=True, text=True, timeout=10, check=True).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _state(jd: JudgeDir) -> Path:
    jd.state.mkdir(mode=0o700, exist_ok=True)
    return jd.state


@contextmanager
def _guard(jd: JudgeDir):
    fd = os.open(_state(jd) / '.guard', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _check_name(name: str) -> None:
    if not _NAME.match(name):
        raise RunOnceError('arm names are lower-case letters, digits, dot, dash and underscore (at most 40)')


def _check_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    if len(reason.strip()) < MIN_REASON:
        raise RunOnceError(f'an override needs a written reason of at least {MIN_REASON} characters')
    return reason.strip()


def _log_override(jd: JudgeDir, action: str, arm: str, reason: str, previous: dict | None) -> None:
    line = {'at': _now(), 'by': getpass.getuser(), 'action': action, 'arm': arm, 'reason': reason,
            'git_sha': git_sha(), 'previous': previous}
    with open(_state(jd) / 'overrides.log', 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(line, sort_keys=True) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def _write_new(path: Path, data: dict) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(data, indent=1, sort_keys=True) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def _replace(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def registration_path(jd: JudgeDir, name: str) -> Path:
    return _state(jd) / f'arm-{name}.json'


def lock_path(jd: JudgeDir, name: str, split: str = 'test') -> Path:
    return _state(jd) / f'run-{split}-{name}.lock'


def register_arm(jd: JudgeDir, name: str, *, label: str, argv: Sequence[str], env: Mapping[str, str],
                 config_hash: str, note: str = '', override_reason: str | None = None) -> dict:
    _check_name(name)
    reason = _check_reason(override_reason)
    if not argv:
        raise RunOnceError('an arm needs a command')
    record = {'name': name, 'label': label, 'argv': list(argv), 'env': dict(env), 'config_hash': config_hash,
              'argv_sha256': hashlib.sha256(json.dumps(list(argv)).encode()).hexdigest(), 'note': note,
              'registered_at': _now(), 'git_sha': git_sha()}
    path = registration_path(jd, name)
    with _guard(jd):
        if path.exists():
            if reason is None:
                raise RunOnceError(f'arm {name} is already registered; registration is frozen')
            previous = json.loads(path.read_text())
            _log_override(jd, 'reregister', name, reason, previous)
            record['reregistered_over'] = previous.get('registered_at')
            _replace(path, record)
        else:
            _write_new(path, record)
    return record


def load_registration(jd: JudgeDir, name: str) -> dict:
    _check_name(name)
    path = registration_path(jd, name)
    if not path.is_file():
        raise RunOnceError(f'arm {name} is not registered; register it before the test run')
    return json.loads(path.read_text())


def acquire_run(jd: JudgeDir, name: str, *, split: str = 'test', override_reason: str | None = None) -> dict:
    """Take the run-once lock for this arm. Raises ``RunOnceError`` when it is already taken."""
    _check_name(name)
    reason = _check_reason(override_reason)
    path = lock_path(jd, name, split)
    info = {'arm': name, 'split': split, 'started_at': _now(), 'pid': os.getpid(), 'git_sha': git_sha(),
            'run_number': 1, 'override': False}
    with _guard(jd):
        try:
            _write_new(path, info)
            return info
        except FileExistsError:
            pass
        previous = json.loads(path.read_text()) if path.is_file() else None
        if reason is None:
            when = (previous or {}).get('started_at', 'an earlier time')
            raise RunOnceError(f'the {split} split was already run for arm {name} (started {when}); '
                               'a second run needs --override-run-once with a written reason')
        _log_override(jd, 'rerun', name, reason, previous)
        info.update(run_number=(previous or {}).get('run_number', 1) + 1, override=True, override_reason=reason)
        _replace(path, info)
        return info


def finish_run(jd: JudgeDir, name: str, summary: dict, detail: list[dict] | None = None, split: str = 'test') -> None:
    """Record the aggregate result (and, judge-side only, the per-scenario detail) next to the lock."""
    state = _state(jd)
    run_no = summary.get('run_once', {}).get('run_number', 1)
    _replace(state / f'run-{split}-{name}.result-{run_no}.json', summary)
    if detail is not None:
        with open(state / f'run-{split}-{name}.detail-{run_no}.jsonl', 'w', encoding='utf-8') as fh:
            for row in detail:
                fh.write(json.dumps(row, sort_keys=True) + '\n')
    path = lock_path(jd, name, split)
    if path.is_file():
        lock = json.loads(path.read_text())
        lock['finished_at'] = _now()
        _replace(path, lock)


def status(jd: JudgeDir) -> dict:
    """Which arms are registered and which test runs exist. No scenario data."""
    state = _state(jd)
    arms = {}
    for p in sorted(state.glob('arm-*.json')):
        rec = json.loads(p.read_text())
        arms[rec['name']] = {'label': rec['label'], 'registered_at': rec['registered_at'],
                             'config_hash': rec['config_hash']}
    runs = {}
    for p in sorted(state.glob('run-*.lock')):
        lock = json.loads(p.read_text())
        runs[p.stem[len('run-'):]] = {k: lock.get(k) for k in ('started_at', 'finished_at', 'run_number', 'override')}
    overrides = 0
    log = state / 'overrides.log'
    if log.is_file():
        overrides = sum(1 for line in log.read_text().splitlines() if line.strip())
    return {'arms': arms, 'runs': runs, 'overrides_logged': overrides}
