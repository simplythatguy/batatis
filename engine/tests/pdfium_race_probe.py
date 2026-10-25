"""Concurrent PDFium work across the request paths, run as a child process by test_pdfium_lock.py.

PDFium is not thread-safe: unguarded, this probe ends in a native crash (SIGSEGV or SIGTRAP), which
would take a test process down with it, hence the separate process. Threads start together at a
barrier and mix the preview route (TestClient, no port), intake PDF reading and the package reader
with its lazy page checks. Every result must equal the serial result for the same bytes.

Run: python -m engine.tests.pdfium_race_probe THREADS JOBS   (prints one JSON summary line)
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main(threads: int, jobs: int) -> None:
    import base64
    import io

    from fastapi.testclient import TestClient
    from pypdf import PdfReader

    from engine.api import create_app
    from engine.codes import Codes
    from engine.export.demo_cases import demo_case
    from engine.intake.pdf import read_pdf as intake_read
    from engine.review.pdf_reader import read_pdf as review_read
    from engine.store import CaseStore
    from engine.tests.case_builder_fixtures import store_with_synthetic_files

    with tempfile.TemporaryDirectory(prefix='batatis-pdfium-race-') as tmp:
        codes = Codes()
        store = CaseStore(Path(tmp) / 'cases.sqlite')
        case = store_with_synthetic_files(store, demo_case('c-homebuilder-infill-house', codes))
        with TestClient(create_app(store=store, codes=codes)) as client:
            route = f'/cases/{case.id}/export/preview'

            def preview() -> str:
                response = client.get(route)
                assert response.status_code == 200, response.text[:200]
                return response.text

            def intake() -> str:
                return json.dumps([(p.number, p.text) for p in intake_read(pdf).text_pages])

            def review() -> str:
                read = review_read(pdf, 'draft.pdf')
                fields = sorted((n, v.status, v.value) for n, v in read.fields.items())
                return json.dumps([read.role, read.form_version, fields, read.unreadable_pages(),
                                   read.passage_has_marks(read.pages - 1, None, None), read.locate(0, 'Owner')])

            serial_preview = preview()
            pdf = base64.b64decode(json.loads(serial_preview)['pdf'].split(',', 1)[1])
            work = (preview, intake, review)
            serial = {fn.__name__: fn() for fn in work}
            barrier = threading.Barrier(threads)

            def job(index: int) -> tuple[str, bool]:
                fn = work[index % len(work)]
                if index < threads:
                    barrier.wait()
                return fn.__name__, fn() == serial[fn.__name__]

            with ThreadPoolExecutor(max_workers=threads) as pool:
                results = list(pool.map(job, range(jobs)))
    body = json.loads(serial_preview)
    print(json.dumps({'jobs': len(results), 'same_as_serial': all(same for _, same in results),
                      'kinds': sorted({name for name, _ in results}), 'pages': body['page_count'],
                      'images': len(body['pages']), 'pdf_pages': len(PdfReader(io.BytesIO(pdf)).pages)}))


if __name__ == '__main__':
    main(int(sys.argv[1]), int(sys.argv[2]))
