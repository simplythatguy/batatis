"""Live mode is OpenAI only, and only engine/spend.py may call that API."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'engine'
HOST = 'api.' + 'openai.com'
CLIENTS = {'OpenAI', 'AsyncOpenAI', 'AzureOpenAI'}


def _py_files():
    return [path for path in ENGINE.rglob('*.py') if path.name != 'spend.py']


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
    problems = []
    for path in _py_files():
        hits = _offenders(path)
        if hits:
            problems.append(f'{path.relative_to(ROOT)}: {", ".join(hits)}')
    assert problems == []


def test_deployed_routes_do_not_call_the_anthropic_verifier():
    for relative in ('engine/api.py', 'engine/identify_http.py', 'engine/routes_case.py', 'engine/spend.py'):
        text = (ROOT / relative).read_text()
        assert 'anthropic' not in text.lower()
        assert 'ClaudeVerifier' not in text


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


def test_cli_verifier_does_not_call_anthropic_when_live(monkeypatch):
    from engine.cli_sut import _verify

    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-anthropic-key')
    trace: dict = {}
    assert _verify('a house', ENGINE / 'missing.sqlite', ['9.10.15.4.'], trace) is None
    assert trace['verifier'].startswith('failed:')
