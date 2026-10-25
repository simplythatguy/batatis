"""Text I/O in production code must name its encoding.

On macOS and Linux the default text encoding is UTF-8, so `path.read_text()`
works. On Windows it is the ANSI code page (cp1252), and a file containing any
other character raises UnicodeDecodeError. The export gate crashed that way:
`engine/completeness.py` read `research/precedents/index.json` without an
encoding and every completeness and export test failed on Windows.

Naming the encoding makes the read platform-independent. Tests may keep bare
calls where they read their own fixtures; production modules may not.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEXT_IO = {'read_text', 'write_text'}
PRODUCTION = ('engine', 'codedb', 'scripts')


def _production_files():
    for folder in PRODUCTION:
        for path in sorted((ROOT / folder).rglob('*.py')):
            parts = path.relative_to(ROOT).parts
            if 'tests' in parts or 'test' in path.stem:
                continue
            yield path


def test_production_text_io_names_its_encoding():
    offenders = []
    for path in _production_files():
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in TEXT_IO:
                continue
            named = any(kw.arg == 'encoding' for kw in node.keywords)
            if not named:
                offenders.append(f'{path.relative_to(ROOT)}:{node.lineno} {node.func.attr}()')
    assert not offenders, (
        'text I/O without encoding= is UTF-8 on macOS and cp1252 on Windows:\n  '
        + '\n  '.join(offenders))


def test_crosswalk_lookup_survives_a_non_utf8_default_encoding():
    """The exact call that crashed the export gate, in a process without UTF-8 mode."""
    result = subprocess.run(
        [sys.executable, '-c',
         'import codecs, locale; '
         'assert codecs.lookup(locale.getpreferredencoding(False)).name != "utf-8"; '
         'from engine.completeness import _edition_crosswalks; '
         'print(len(_edition_crosswalks()))'],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
        env={**os.environ, 'PYTHONUTF8': '0', 'PYTHONCOERCECLOCALE': '0',
             'LC_ALL': 'C', 'LANG': 'C', 'PYTHONPATH': str(ROOT)},
    )
    assert result.returncode == 0, (
        f'reading the crosswalk file failed without UTF-8 mode:\n{result.stderr}')
    assert result.stdout.strip().isdigit()
    assert int(result.stdout.strip()) > 0
