"""An explicitly SYNTHETIC BTRboard-like administrative fixture and PDF/PNG sample CLI.

No test, engineering study, professional opinion, appointment or seal is real. The test attachment
is a committed synthetic text fixture, never fabricated evidence returned by production modules.

Run: python -m engine.export.sample [out_dir]     (default /tmp/batatis-export)
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..codes import Codes
from ..models import Case, EvidenceItem, Fact, Jurisdiction, Source
from ..section_c import section_c_rows
from ..section_d import section_d_plan

# Continuous exterior sheathing insulation on a Part 9 wood-frame house. The applicant, firm and address are fictional.
PROVISIONS = ['9.25.5.1.', '9.25.2.2.(1)', '9.23.17.2.(1)', '9.27.3.4.(1)', '9.32.1.3.(2)']

FACTS = {
    'owner_name': 'SYNTHETIC - Prairie Ridge Homes Ltd.',
    'owner_rep_name': 'SYNTHETIC - Jordan Ellery (test representative)',
    'mailing_address': '210, 4410 Example Trail NW\nCalgary, AB T3A 0Z9',
    'request_date': '2026-10-20',
    'submitted_to_scc': False,
    'permit_number': 'BP-2026-0000-DEMO',
    'municipal_address': '1234 Sample Crescent SW, Calgary, AB T2X 0Y0',
    'lot': '14', 'block': '7', 'plan': '2610001',
    'scope': 'site',
    'alternative_description': 'SYNTHETIC TEST: Continuous exterior sheathing insulation on a Part 9 wood-frame house. '
                               'This exercises administrative fields and contains no technical equivalency conclusion.',
    'rationale': 'SYNTHETIC applicant rationale: test an exterior-insulation departure against the selected benchmark.',
    'risk_assessment': 'SYNTHETIC applicant risk passage: consider moisture accumulation and the changed wall interfaces. '
                       'No risk level or technical assessment is asserted by this test fixture.',
    'mitigating_measures': 'SYNTHETIC applicant measures passage: the responsible designer would document the '
                           'installation, review and evidence needed for each benchmark. No measure is judged adequate.',
    'assumptions_limits': 'SYNTHETIC applicant limits: the example is a Part 9 house and the selected wall configuration only.',
    'operation_maintenance': 'SYNTHETIC applicant operation/maintenance passage: identify owner duties, inspection '
                             'intervals and commissioning conditions with the responsible designer.',
    'qualifications': 'SYNTHETIC applicant qualifications passage: a fictional design author is used only to exercise '
                      'administrative presence checks. No licence or competence is claimed.',
    'occupancy': 'single_family', 'part4_design': True, 'preserved_wood_foundation_part4': False,
    'roof_trusses': False, 'prescriptive_route_confirmed': False, 'ahj_requires_professional': False,
    'special_safety_concerns': False, 'professional_judgement_required': True, 'professional_scope_resolved': True,
    'fire_suppression': False, 'fire_alarm': False,
    'professional_name': 'SYNTHETIC TEST professional identity (no real appointment)',
    'professional_seal': 'SYNTHETIC TEST authentication metadata (no real seal or review)',
    'supporting_doc.1.name': 'SYNTHETIC product-literature attachment',
    'supporting_doc.1.responsible': 'SYNTHETIC manufacturer role',
    'supporting_doc.2.name': 'SYNTHETIC envelope-analysis attachment',
    'supporting_doc.2.responsible': 'SYNTHETIC design-author role',
    'supporting_doc.3.name': 'SYNTHETIC material-test attachment (no testing performed)',
    'supporting_doc.3.responsible': 'SYNTHETIC laboratory role',
    'supporting_doc.4.name': 'SYNTHETIC wall-detail attachment',
    'supporting_doc.4.responsible': 'SYNTHETIC drawing-author role',
    'supporting_doc.5.name': 'SYNTHETIC fastening-evidence attachment (no testing performed)',
    'supporting_doc.5.responsible': 'SYNTHETIC laboratory role',
    'supporting_doc.6.name': 'SYNTHETIC air-barrier-detail attachment',
    'supporting_doc.6.responsible': 'SYNTHETIC design-author role',
}


def sample_case(codes: Codes, provisions: list[str] = PROVISIONS, facts: dict = FACTS) -> Case:
    def synthetic_fact(key, value):
        return Fact(field=key, value=value, kind='pointed', status='confirmed',
                    source=Source(type='user_text', ref='synthetic-test-fixture:applicant', quote=str(value)))

    case = Case(title='SYNTHETIC BTRboard-like continuous sheathing insulation (test fixture)',
                jurisdiction=Jurisdiction(id='calgary', name='City of Calgary'),
                facts=[synthetic_fact(k, v) for k, v in facts.items()],
                provisions=provisions, section_c=section_c_rows(provisions, codes))
    source_file = Path(__file__).parent / 'fixtures' / 'synthetic-evidence.txt'
    text = source_file.read_text()
    for n in range(1, 7):
        eid = f'synthetic_{n}'
        name, who = facts.get(f'supporting_doc.{n}.name'), facts.get(f'supporting_doc.{n}.responsible')
        if not name:
            continue
        case.evidence.append(EvidenceItem(id=eid, description=name, status='evidence_listed'))
        case.facts.append(synthetic_fact(f'evidence.{eid}.file_ref', str(source_file)))
        case.facts[-1].source = Source(type='file', ref=str(source_file), quote=text)
        case.facts += [synthetic_fact(f'evidence.{eid}.{key}', value) for key, value in
                       (('title', name), ('responsible_party', who or ''), ('issuer', 'SYNTHETIC test fixture'),
                        ('date', '2026-10-20'))]
    for n, item in enumerate(section_d_plan(case, codes).items):
        case.facts.append(synthetic_fact(f'evidence.synthetic_{n % 6 + 1}.covers.{item.id}', True))
    return case


def main(out_dir: str = '/tmp/batatis-export') -> None:
    import pypdfium2 as pdfium

    from . import export_case
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    codes = Codes()
    case = sample_case(codes)
    incomplete = case.model_copy(deep=True)
    incomplete.facts = [fact for fact in incomplete.facts if fact.field != 'risk_assessment']
    incomplete.facts.append(Fact(field='owner_name', value='Unconfirmed synthetic revised owner', kind='pointed',
        source=Source(type='user_text', ref='synthetic-test-fixture:unconfirmed-revision')))
    for name, draft, source_case in (('sample.pdf', False, case), ('sample-draft.pdf', True, incomplete)):
        res = export_case(source_case, codes=codes, draft=draft)
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
