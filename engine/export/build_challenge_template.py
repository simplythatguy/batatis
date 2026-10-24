"""Reproduce the packaged editable template from the user's exact supplied PDF.

Run with the original eleven-page file; no network fetch or substitute source.
Requires the project's pypdf version 6.21.1 for byte-identical serialization.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from .challenge_form import SOURCE_SHA256, VERSION, independent_fields

ASSET = Path(__file__).parent / 'templates' / f'{VERSION}.pdf'


def build(source: Path) -> bytes:
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Expected the exact user-supplied Building Codes Challenge Scope PDF')
    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) != 11:
        raise ValueError('The supplied source must have eleven physical pages')
    writer = PdfWriter()
    writer.append(reader, pages=(4, 11), import_outline=False)
    independent_fields(writer)
    writer.add_metadata({'/Title': 'Variance Form for Proposed Alternative Solution',
                         '/Producer': 'Batatis mechanical source extraction',
                         '/BatatisSourceSHA256': SOURCE_SHA256,
                         '/BatatisSourcePages': '5-11', '/BatatisFormVersion': VERSION,
                         '/BatatisAttributionRows': '5', '/BatatisFormPages': '7'})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--check', action='store_true', help='Compare with the tracked asset without writing')
    args = parser.parse_args()
    data = build(args.source)
    if args.check:
        if data != ASSET.read_bytes():
            raise SystemExit('Packaged challenge template differs from mechanical extraction')
    else:
        ASSET.parent.mkdir(exist_ok=True)
        ASSET.write_bytes(data)
    print(json.dumps({'asset': str(ASSET), 'sha256': hashlib.sha256(data).hexdigest(),
                      'source_sha256': SOURCE_SHA256, 'physical_pages': list(range(5, 12))}))


if __name__ == '__main__':
    main()
