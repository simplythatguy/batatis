"""Run the system under test in a separate process and classify the outcome.

The SUT contract is ``engine/cli_sut.py``'s: the applicant's words on stdin, one JSON object on stdout.
A run that does not produce a valid object is a trial failure with a category, never silently dropped:

    launch_failed  the command could not be started
    timeout        no answer within the limit (the process group is killed)
    no_response    exit 0 with empty stdout
    nonzero_exit   non-zero exit status
    invalid_json   stdout is not one JSON object
    schema_invalid the object lacks the fields the judge scores with

Neither stdout nor stderr of the SUT is ever echoed by the judge.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .dataset import ENGINEERING, INTAKE_ACTIONS

CATEGORIES = ('launch_failed', 'timeout', 'no_response', 'nonzero_exit', 'invalid_json', 'schema_invalid')
MAX_STDOUT = 8_000_000


@dataclass
class SutResult:
    category: str | None          # None means a valid answer
    output: dict | None
    seconds: float
    returncode: int | None = None


def check_output(obj) -> str | None:
    """None when ``obj`` has the fields the judge scores with, else ``schema_invalid``."""
    if not isinstance(obj, dict) or not isinstance(obj.get('articles'), list):
        return 'schema_invalid'
    for a in obj['articles']:
        if not isinstance(a, dict) or not isinstance(a.get('provision'), str) or not isinstance(a.get('committed', False), bool):
            return 'schema_invalid'
    if obj.get('intake_action') is not None and obj['intake_action'] not in INTAKE_ACTIONS:
        return 'schema_invalid'
    if obj.get('engineering_required') is not None and obj['engineering_required'] not in ENGINEERING:
        return 'schema_invalid'
    return None


def run_sut(argv: Sequence[str], prose: str, *, env: Mapping[str, str], cwd: str, timeout: float,
            prefix: Sequence[str] | None = None) -> SutResult:
    started = time.monotonic()
    full = [*(prefix or []), *argv]
    try:
        proc = subprocess.Popen(full, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
                                env=dict(env), start_new_session=True)
    except OSError:
        return SutResult('launch_failed', None, time.monotonic() - started)
    try:
        stdout, _stderr = proc.communicate(prose.encode('utf-8'), timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.communicate()
        return SutResult('timeout', None, time.monotonic() - started)
    seconds = time.monotonic() - started
    if proc.returncode != 0:
        return SutResult('nonzero_exit', None, seconds, proc.returncode)
    if not stdout.strip():
        return SutResult('no_response', None, seconds, 0)
    if len(stdout) > MAX_STDOUT:
        return SutResult('invalid_json', None, seconds, 0)
    try:
        obj = json.loads(stdout.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return SutResult('invalid_json', None, seconds, 0)
    bad = check_output(obj)
    return SutResult(bad, obj if bad is None else None, seconds, 0)
