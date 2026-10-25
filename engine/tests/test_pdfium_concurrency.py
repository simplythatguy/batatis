"""Exercise real PDF readers in a child process: a PDFium race can segfault Python."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONCURRENT_READS = r'''
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

from reportlab.pdfgen import canvas

from engine.export.g3 import page_texts, render_problems
from engine.intake.pdf import read_pdf as intake_pdf
from engine.review.pdf_reader import read_pdf as review_pdf

documents, expected = [], []
for number in range(3):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    texts = [f'SYNTHETIC document {number} page {page}' for page in (1, 2)]
    for text in texts:
        pdf.drawString(72, 700, text)
        pdf.showPage()
    pdf.save()
    documents.append(buffer.getvalue())
    expected.append(texts)

# Initialise PDFium before the threads; the race is in document use, not imports.
intake_pdf(documents[0])
start = Barrier(3)

def read(number):
    mode = sys.argv[1]
    if mode == 'mixed':
        mode = ('intake', 'review', 'export')[number]
    data = documents[number]
    for _ in range(20):
        start.wait(timeout=20)
        if mode == 'intake':
            result = intake_pdf(data)
            texts = [page.text.strip() for page in result.text_pages]
        elif mode == 'review':
            result = review_pdf(data, f'document-{number}.pdf')
            assert result.role == 'attachment', result.note
            texts = [page.text.strip() for page in result.text_pages]
            assert result.locate(0, expected[number][0]) is not None
            assert result.unreadable_pages() == []
            assert not result.passage_has_marks(0, None, None)
        else:
            texts = [text.strip() for text in page_texts(data)]
            # render_problems calls page_texts while its own document is open.
            assert render_problems(SimpleNamespace(pdf=data, form_pages=0, placements=[])) == []
        assert texts == expected[number], (mode, texts, expected[number])
    return texts

with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(read, range(3)))
print(json.dumps(results))
'''


@pytest.mark.parametrize('reader', ['intake', 'review', 'export', 'mixed'])
def test_concurrent_pdf_readers(reader):
    run = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', CONCURRENT_READS, reader],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, f'PDF reader child exited {run.returncode}\n{run.stdout}\n{run.stderr}'
    assert json.loads(run.stdout) == [
        [f'SYNTHETIC document {number} page {page}' for page in (1, 2)] for number in range(3)
    ]
