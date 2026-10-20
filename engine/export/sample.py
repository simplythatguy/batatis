"""A BTRboard-like fixture case (fictional applicant) and a CLI that writes a sample export with PNG previews.

Run: python -m engine.export.sample [out_dir]     (default /tmp/batatis-export)
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..codes import Codes
from ..models import Case, Fact, Jurisdiction, Source
from ..section_c import section_c_rows

# Continuous exterior sheathing insulation on a Part 9 wood-frame house. The applicant, firm and address are fictional.
PROVISIONS = ['9.25.5.1.', '9.25.2.2.(1)', '9.23.17.2.(1)', '9.27.3.4.(1)', '9.32.1.3.(2)']

FACTS = {
    'owner_name': 'Prairie Ridge Homes Ltd.',
    'owner_rep_name': 'Jordan Ellery, Northgate Building Envelope Consulting',
    'mailing_address': '210, 4410 Example Trail NW\nCalgary, AB T3A 0Z9',
    'request_date': '2026-10-20',
    'submitted_to_scc': False,
    'permit_number': 'BP-2026-0000-DEMO',
    'municipal_address': '1234 Sample Crescent SW, Calgary, AB T2X 0Y0',
    'lot': '14', 'block': '7', 'plan': '2610001',
    'supporting_doc.1.name': 'BTRboard-like product data sheet, rev. C',
    'supporting_doc.1.responsible': 'Fictional Panel Co. Ltd. (manufacturer)',
    'supporting_doc.2.name': 'Hygrothermal (WUFI) analysis of wall assembly W1',
    'supporting_doc.2.responsible': 'J. Ellery, P.Eng., Northgate Building Envelope Consulting',
    'supporting_doc.3.name': 'CAN/ULC-S701 thermal resistance test report',
    'supporting_doc.3.responsible': 'Fictional Test Laboratory Inc.',
    'supporting_doc.4.name': 'Wall section drawings A-301 to A-304',
    'supporting_doc.4.responsible': 'Prairie Ridge Homes Ltd.',
    'supporting_doc.5.name': 'Fastener withdrawal test summary for cladding through 50 mm insulation',
    'supporting_doc.5.responsible': 'Fictional Test Laboratory Inc.',
    'supporting_doc.6.name': 'Air barrier continuity details',
    'supporting_doc.6.responsible': 'Northgate Building Envelope Consulting',
}


def sample_case(codes: Codes, provisions: list[str] = PROVISIONS, facts: dict = FACTS) -> Case:
    src = Source(type='user_text', ref='fixture')
    return Case(title='BTRboard-like continuous sheathing insulation (fixture)',
                jurisdiction=Jurisdiction(id='calgary', name='City of Calgary'),
                facts=[Fact(field=k, value=v, kind='pointed', source=src, status='confirmed') for k, v in facts.items()],
                provisions=provisions, section_c=section_c_rows(provisions, codes))


def main(out_dir: str = '/tmp/batatis-export') -> None:
    import pypdfium2 as pdfium

    from . import export_case
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    codes = Codes()
    case = sample_case(codes)
    for name, draft in (('sample.pdf', False), ('sample-draft.pdf', True)):
        res = export_case(case, codes=codes, draft=draft)
        (out / name).write_bytes(res.pdf)
        doc = pdfium.PdfDocument(res.pdf)
        stem = name.removesuffix('.pdf')
        for label, idx in (('page1', 0), ('page2', 1), ('appendix1', res.form_pages)):
            png = out / f'{stem}-{label}.png'
            doc[idx].render(scale=2).to_pil().save(png)
            print(png)
        print(out / name, f'{res.form_pages} form pages + {res.appendix_pages} appendix pages;',
              'blank:', ', '.join(res.blank_fields) or 'none')


if __name__ == '__main__':
    main(*sys.argv[1:])
