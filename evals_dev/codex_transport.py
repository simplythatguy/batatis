"""A resumable, network-free handoff to T3-owned Codex tasks.

Python prepares the engine's actual prompt. The parent delegates that prompt through
T3 and imports the returned JSON. No API key, subprocess agent or HTTP client is used.
PendingCall intentionally escapes broad engine exception handlers: pending work must
never become an apparently successful fallback. Request hashes bind every response.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


class PendingCall(BaseException):
    def __init__(self, path: Path):
        self.path = path


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix=path.name + '.', delete=False) as stream:
        tmp = Path(stream.name)
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class CodexTransport:
    def __init__(self, root: Path, case_id: str, stage: str, calls: list | None = None):
        self.root, self.case_id, self.stage, self.calls = root, case_id, stage, calls

    def __call__(self, system: str, user: str, schema: dict, *args, **kwargs) -> tuple[dict, dict]:
        request = {'system': system, 'user': user, 'schema': schema,
                   'provider': 'codex', 'model': 'gpt-6-luna',
                   'options': {'reasoningEffort': 'max', 'serviceTier': 'priority'}}
        raw = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        key = hashlib.sha256(raw.encode()).hexdigest()
        folder = self.root / 'calls' / key
        path = folder / 'request.json'
        if not path.exists():
            write_json(path, {**request, 'request_sha256': key, 'case_id': self.case_id, 'stage': self.stage})
        saved = json.loads(path.read_text())
        if {name: saved.get(name) for name in request} != request or saved.get('request_sha256') != key:
            raise ValueError('saved Codex request changed')
        response = folder / 'response.json'
        if not response.exists():
            raise PendingCall(path)
        data = json.loads(response.read_text())
        if data.get('request_sha256') != key or data.get('provider') != 'codex' \
                or data.get('model') != 'gpt-6-luna' or data.get('options') != request['options'] \
                or not data.get('task_id') or not isinstance(data.get('payload'), dict):
            raise ValueError('Codex response identity does not match its request')
        if data.get('error'):
            raise RuntimeError('Codex task failed')
        if self.calls is not None:
            self.calls.append({'request_sha256': key, 'task_id': data['task_id'],
                               'request_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'response_sha256': hashlib.sha256(response.read_bytes()).hexdigest()})
        # The engine accepts an empty usage object. Unknown usage/cost is retained in
        # the run manifest as unknown, never priced as zero API spend.
        return data['payload'], {}

    def identify(self, name, schema, system, user, **kwargs):
        return self(system, user, schema)


def pending(root: Path) -> list[dict]:
    return [json.loads(p.read_text()) | {'path': str(p)}
            for p in sorted((root / 'calls').glob('*/request.json'))
            if not p.with_name('response.json').exists()]
