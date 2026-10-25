"""Exact structured requests for T3-owned inference tasks; no HTTP or model CLI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .codex_transport import PendingCall, write_json

LUNA_JUDGE = {'provider': 'codex', 'model': 'gpt-6-luna',
              'options': {'reasoningEffort': 'max', 'serviceTier': 'priority'}}


def haiku(effort: str) -> dict:
    if effort not in ('low', 'medium'):
        raise ValueError('Haiku comparison effort must be low or medium')
    return {'provider': 'claudeAgent', 'model': 'claude-haiku-5-5', 'options': {'effort': effort}}


class TaskTransport:
    def __init__(self, root: Path, case_id: str, stage: str, target: dict, calls: list | None = None):
        self.root, self.case_id, self.stage = root, case_id, stage
        self.target = {**target, 'options': dict(target['options'])}
        self.calls = calls

    def __call__(self, system: str, user: str, schema: dict, *args, **kwargs):
        request = {'system': system, 'user': user, 'schema': schema, **self.target}
        raw = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        key = hashlib.sha256(raw.encode()).hexdigest()
        path = self.root / 'calls' / key / 'request.json'
        if not path.exists():
            write_json(path, {**request, 'request_sha256': key, 'case_id': self.case_id, 'stage': self.stage})
        saved = json.loads(path.read_text())
        if {name: saved.get(name) for name in request} != request or saved.get('request_sha256') != key:
            raise ValueError('saved inference request changed')
        response = path.with_name('response.json')
        if not response.exists():
            raise PendingCall(path)
        data = json.loads(response.read_text())
        if data.get('request_sha256') != key or any(data.get(k) != v for k, v in self.target.items()) \
                or not data.get('task_id') or not isinstance(data.get('payload'), dict):
            raise ValueError('inference response identity does not match its request')
        if data.get('error'):
            raise RuntimeError('inference task failed')
        if self.calls is not None:
            self.calls.append({'request_sha256': key, 'task_id': data['task_id'],
                               'request_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'response_sha256': hashlib.sha256(response.read_bytes()).hexdigest()})
        return data['payload'], {}

    def identify(self, name, schema, system, user, **kwargs):
        return self(system, user, schema)
