"""A document-review transport that runs DeepSeek V4.1 Flash Free through the OpenCode client.

The free model only answers through OpenCode's own client, so each review runs `opencode run` in an empty
folder whose agent has no tools, attaches the request and page text as one file, and asks for JSON that
matches the engine's review schema. The engine checks the answer exactly as it checks Luna's. This is a
harness transport for comparison runs; the engine itself is unchanged.

    DPE_REVIEW_TRANSPORT=opencode .venv/bin/python -m evals_dev.data_prompts run --name it-deepseek --split dev
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

MODEL = os.environ.get('DPE_OPENCODE_MODEL', 'opencode/deepseek-v4.1-flash-free#max')
BINARY = os.environ.get('DPE_OPENCODE_BIN', str(Path.home() / '.opencode' / 'bin' / 'opencode'))
TIMEOUT = int(os.environ.get('DPE_OPENCODE_TIMEOUT', '1200'))
AGENT = {
    '$schema': 'https://opencode.ai/config.json',
    'agent': {'reviewer': {
        'description': 'Plain completion with no tools',
        'mode': 'primary',
        'prompt': "You answer the user's message directly. You have no tools. Return only what the message asks for.",
        'tools': {name: False for name in ('bash', 'edit', 'write', 'read', 'grep', 'glob', 'list', 'patch',
                                           'todowrite', 'todoread', 'webfetch', 'task')},
    }},
}


class OpenCodeError(RuntimeError):
    pass


def _json(text: str) -> dict:
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise OpenCodeError('no JSON object in the answer')
    return json.loads(text[start:end + 1])


def transport(system: str, user: str, schema: dict, model: str, effort: str) -> tuple[dict, dict]:
    """Same signature as engine.intake.review transports; `model` and `effort` name the Luna slot it replaces."""
    with tempfile.TemporaryDirectory(prefix='dpe-oc-') as folder:
        Path(folder, 'opencode.json').write_text(json.dumps(AGENT))
        Path(folder, 'request-and-pages.json').write_text(user)
        message = (system + '\n\nThe attached file holds the request and the page text, as JSON. Answer with one JSON '
                   'object only, no prose and no code fences, that matches this JSON Schema exactly (every listed '
                   'key present, no other keys):\n' + json.dumps(schema, separators=(',', ':')))
        try:
            done = subprocess.run([BINARY, 'run', '--standalone', '--agent', 'reviewer', '--model', MODEL,
                                   '--format', 'json', '--file', 'request-and-pages.json', message],
                                  cwd=folder, capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired as error:
            raise OpenCodeError('timed out') from error
    events = [json.loads(line) for line in done.stdout.splitlines() if line.strip().startswith('{')]
    errors = [e for e in events if e.get('type') == 'error']
    if errors:
        raise OpenCodeError((errors[0].get('error') or {}).get('type') or 'error')
    text = ''.join(e['part'].get('text', '') for e in events if e.get('type') == 'text')
    usage = {'input_tokens': 0, 'output_tokens': 0}
    for e in events:
        tokens = (e.get('part') or {}).get('tokens') or {}
        usage['input_tokens'] += int(tokens.get('input') or 0)
        usage['output_tokens'] += int(tokens.get('output') or 0) + int(tokens.get('reasoning') or 0)
    return _json(text), usage
