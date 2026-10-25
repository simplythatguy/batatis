"""PDFium is not thread-safe: every document the engine opens is opened under one process-wide lock."""
import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from engine.export import form_path

ROOT = Path(__file__).resolve().parents[2]


def _locked(function: ast.AST) -> bool:
    return any((isinstance(d, ast.Name) and d.id == 'pdfium_locked')
               or (isinstance(d, ast.Attribute) and d.attr == 'pdfium_locked') for d in function.decorator_list)


def _yields(function: ast.AST) -> bool:
    """A generator would run, and release its objects, after its call returned the lock."""
    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(child, (ast.Yield, ast.YieldFrom)) or walk(child):
                return True
        return False
    return walk(function)


def test_every_pdfium_document_the_engine_opens_is_opened_under_the_lock():
    unlocked, generators, opened = [], [], 0
    for path in sorted((ROOT / 'engine').rglob('*.py')):
        if 'tests' in path.relative_to(ROOT).parts:
            continue
        where = path.relative_to(ROOT)

        def visit(node, owners):
            nonlocal opened
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owners = [*owners, node]
                if _locked(node) and _yields(node):
                    generators.append(f'{where}:{node.lineno}')
            func = getattr(node, 'func', None)
            if isinstance(node, ast.Call) and getattr(func, 'attr', getattr(func, 'id', None)) == 'PdfDocument':
                opened += 1
                if not any(_locked(owner) for owner in owners):
                    unlocked.append(f'{where}:{node.lineno}')
            for child in ast.iter_child_nodes(node):
                visit(child, owners)
        visit(ast.parse(path.read_text()), [])
    assert opened >= 14, 'the scan no longer sees the engine PDFium call sites'
    assert not unlocked and not generators, (unlocked, generators)


@pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')
def test_concurrent_previews_and_pdf_reads_finish_and_match_their_serial_results():
    # A native crash in a child process is a failed run, not a crashed test session.
    run = subprocess.run([sys.executable, '-X', 'faulthandler', '-m', 'engine.tests.pdfium_race_probe', '6', '24'],
                         cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, f'exit {run.returncode}\n{run.stderr[-3000:]}'
    summary = json.loads(run.stdout.strip().splitlines()[-1])
    assert summary == {'jobs': 24, 'same_as_serial': True, 'kinds': ['intake', 'preview', 'review'],
                       'pages': 11, 'images': 11}
