"""Live mode is OpenAI only, and only engine/spend.py may call that API."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'engine'
HOST = 'api.' + 'openai.com'
CLIENTS = {'OpenAI', 'AsyncOpenAI', 'AzureOpenAI'}


def _needles():
    # Split so this file does not contain the contiguous literals the scan rejects.
    return (
        'api.' + 'openai.com',
        'import ' + 'openai',
        'from ' + 'openai',
        'Open' + 'AI(',
    )


def _engine_files():
    """Files under engine/, except spend.py. apps/ is not scanned."""
    for path in ENGINE.rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts or 'apps' in path.parts:
            continue
        if path.resolve() == (ENGINE / 'spend.py').resolve():
            continue
        if path.suffix == '.pyc':
            continue
        yield path


def _offenders(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'openai' or alias.name.startswith('openai.'):
                    found.append(f'import {alias.name}')
        elif isinstance(node, ast.ImportFrom) and node.module and (
            node.module == 'openai' or node.module.startswith('openai.')
        ):
            found.append(f'from {node.module}')
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            if name in CLIENTS:
                found.append(f'call {name}')
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and HOST in node.value:
            found.append('api host')
    return found


def test_only_spend_py_may_construct_or_call_openai():
    """AST plus a text scan. apps/ is outside engine/ and is not scanned."""
    needles = _needles()
    problems = []
    for path in _engine_files():
        text = path.read_text(errors='ignore')
        for needle in needles:
            if needle in text:
                problems.append(f'{path.relative_to(ROOT)}: text')
                break
        if path.suffix == '.py':
            hits = _offenders(path)
            if hits:
                problems.append(f'{path.relative_to(ROOT)}: {", ".join(hits)}')
    assert problems == []
    spend = (ENGINE / 'spend.py').read_text()
    assert needles[0] in spend
    assert 'def openai_chat_json' in spend
    assert 'def keyed_openai_call' not in spend


def test_deployed_routes_do_not_call_the_anthropic_verifier():
    for relative in ('engine/api.py', 'engine/identify_http.py', 'engine/routes_case.py'):
        text = (ROOT / relative).read_text()
        assert 'anthropic' not in text.lower()
        assert 'ClaudeVerifier' not in text
    spend = (ROOT / 'engine/spend.py').read_text()
    assert 'ClaudeVerifier' not in spend
    assert ('import ' + 'anthropic') not in spend.lower()


def test_anthropic_verifier_cannot_run_on_the_deployed_path(monkeypatch):
    from engine.identify.verify import ClaudeVerifier, anthropic_verifier_allowed

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-anthropic-key')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.delenv('VERCEL', raising=False)
    assert anthropic_verifier_allowed() is False
    with pytest.raises(RuntimeError, match='OpenAI only'):
        ClaudeVerifier('codedb/build/codedb.sqlite')

    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.setenv('VERCEL', '1')
    assert anthropic_verifier_allowed() is False
    with pytest.raises(RuntimeError, match='OpenAI only'):
        ClaudeVerifier('codedb/build/codedb.sqlite')


def _paid_needles():
    # Split so this file does not contain the contiguous literals the scan rejects.
    return (
        'import ' + 'anthropic',
        'from ' + 'anthropic',
        'Anthropic' + '(',
        'api.' + 'typesafe.ai',
        'openrouter.' + 'ai/api',
        'HTTPS' + 'Connection',
        'HTTP' + 'Connection(',
        'client' + '.ask(',
        'import ' + 'jevkit',
        'from ' + '.jevkit',
        '.identify.' + 'jevkit',
    )


_PAID_ALLOWED = {
    Path('engine/identify/verify.py'),
    Path('engine/cli_sut.py'),
}


def _paid_allowed(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if relative in _PAID_ALLOWED:
        return True
    parts = relative.parts
    if parts[:3] == ('engine', 'identify', 'jevkit'):
        return True
    if 'tests' in parts:
        return True
    if parts and parts[0] in {'evals', 'evals_dev'}:
        return True
    if parts[:2] == ('docs', 'research'):
        return True
    return False


def test_paid_clients_stay_in_cli_and_eval_modules():
    """Anthropic and Jev/TypeSafe call sites outside the CLI and eval modules fail CI.

    The scan includes ``api.typesafe.ai`` and jevkit call sites (``client.ask``,
    a jevkit import). The vendored client, the CLI runner, evals, and tests are allowed.
    """
    needles = _paid_needles()
    roots = [ROOT / 'engine', ROOT / 'evals', ROOT / 'evals_dev', ROOT / 'docs' / 'research']
    problems = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            if _paid_allowed(path):
                continue
            text = path.read_text(errors='ignore')
            for needle in needles:
                if needle in text:
                    problems.append(f'{path.relative_to(ROOT)}: paid client')
                    break
    assert problems == []


def test_live_refuses_jev_and_typesafe(monkeypatch):
    from engine.identify.jevkit.client import JevError, ask, noul

    calls = []

    def transport(body, headers, timeout):
        calls.append(body)
        return b'{}'

    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.delenv('VERCEL', raising=False)
    with pytest.raises(JevError, match='OpenAI only'):
        ask('a house', {'governs': noul('it governs')}, api_key='test-jev-key', transport=transport)
    assert calls == []

    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.setenv('VERCEL', '1')
    with pytest.raises(JevError, match='OpenAI only'):
        ask('a house', {'governs': noul('it governs')}, api_key='test-jev-key', transport=transport)
    assert calls == []

    monkeypatch.delenv('VERCEL', raising=False)
    with pytest.raises(JevError, match='malformed'):
        ask('a house', {'governs': noul('it governs')}, api_key='test-jev-key', transport=transport)
    assert len(calls) == 1

    from engine.identify.screen import Judge, jev_ask
    monkeypatch.setenv('BATATIS_LIVE', '1')
    with pytest.raises(RuntimeError, match='OpenAI only'):
        jev_ask()
    with pytest.raises(RuntimeError, match='OpenAI only'):
        Judge()
    screen = (ENGINE / 'identify' / 'screen.py').read_text()
    for needle in ('client' + '.ask(', 'import ' + 'jevkit', 'from ' + '.jevkit', 'api.' + 'typesafe.ai'):
        assert needle not in screen


def test_live_refuses_anthropic_provider(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from engine.api import create_app
    from engine.llm_gate import reset_for_tests
    from engine.spend import SpendError, openai_chat_json
    from engine.tests.test_spend import _prepare

    path = _prepare(tmp_path, monkeypatch)
    monkeypatch.setenv('BATATIS_LLM_PROVIDER', 'Anthropic')
    seen = []
    monkeypatch.setattr('engine.spend._post_chat', lambda payload, key: seen.append(payload))
    with pytest.raises(SpendError, match='OpenAI only'):
        openai_chat_json(
            [{'role': 'user', 'content': 'hi'}], model='gpt-4.1-mini', max_completion_tokens=8)
    assert seen == []
    import sqlite3
    with sqlite3.connect(path) as con:
        assert con.execute('SELECT COUNT(*) FROM spend_ledger').fetchone()[0] == 0

    reset_for_tests()
    monkeypatch.setattr(
        'engine.identify.corpus.bm25_rank',
        lambda query, db_path, limit=20: ['9.10.15.4.'],
    )
    response = TestClient(create_app()).post('/identify', json={'query': 'soffit'})
    assert response.status_code == 200
    body = response.json()
    assert body['label'] == 'API fallback'
    assert body['hits'] == ['9.10.15.4.']
    assert seen == []


def test_cli_verifier_does_not_call_anthropic_when_live(monkeypatch):
    from engine.cli_sut import _verify

    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-anthropic-key')
    trace: dict = {}
    assert _verify('a house', ENGINE / 'missing.sqlite', ['9.10.15.4.'], trace) is None
    assert trace['verifier'].startswith('failed:')
