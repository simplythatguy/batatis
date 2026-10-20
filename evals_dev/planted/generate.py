"""Write the planted-defect fixtures. This file does not import the checker.

Run: python3 -m evals_dev.planted.generate
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from engine.completeness_elements import ELEMENTS

ROOT = Path(__file__).resolve().parent
APPS = ROOT / 'apps'
GOLD = ROOT / 'gold'

BASE = {
    'owner_name': ('Owner', 'Avery Synthetic'),
    'representative': ('Owner Rep', 'Riley Synthetic'),
    'mailing_address': ('Mailing Address', '100 Example Avenue, Edmonton, Alberta'),
    'application_date': ('Date of Reqeuest', '2026-10-20'),
    'signature': ('', 'signed'),
    'owner_rep_signature_date': ('Date2', '2026-10-20'),
    'civic_address': ('Municipal Address', '100 Example Avenue, Edmonton, Alberta'),
    'legal_description': ('', 'Lot 4 Block 8 Plan 1234567'),
    'lot': ('Lot', '4'),
    'block': ('Block', '8'),
    'plan': ('Plan', '1234567'),
    'alternative_description': ('',
        'The proposed soffit stays vented aluminum where the north exposing wall has a limiting distance '
        'of 1.2 m and a 450 mm overhang. This is a site-specific departure for a single detached house.'),
    'code_or_standard': ('Code or Standard',
        'National Building Code - 2023 Alberta Edition (2nd printing), Division B'),
    'section_c.article': ('Article(s)', '9.10.15.5.(8)'),
    'objective': ('Objective', 'OP3.1'),
    'function': ('Function', 'F03'),
    'section_c.intent': ('Intent statement',
        'NBC 2020 Intent Statements, explanatory only. National explanatory material is not copied here and is not Alberta law.'),
    'heading': ('', 'spatial separation soffit overhang'),
    'risk_assessment': ('',
        'If the soffit remains vented over the north wall at the stated 1.2 m limiting distance, flame could reach '
        'the neighbouring property. The applicant describes that departure-specific risk here.'),
    'mitigating_measures': ('',
        'Non-vented soffit material and protection on the north overhang address the limiting-distance departure described above.'),
    'assumptions_and_limits': ('',
        'Assumes the north wall limiting distance stays 1.2 m, the house remains a single detached house, and the '
        'overhang stays 450 mm. A change in distance or soffit type requires the applicant to reassess. These are assumptions.'),
    'supporting_doc': ('Supporting Doc', 'Synthetic product sheet for the soffit assembly'),
    'responsible_party': ('Name Responsible', 'Casey Synthetic, product specialist'),
    'document_date': ('', '2026-10-01'),
    'engineering_required': ('', 'no'),
    'professional_name': ('', ''),
    'professional_qualifications': ('', ''),
    # IB-2025-11-18: included documentation, not a drafted analysis.
    'division_c_2_3_1': ('',
        'The Division C Section 2.3.1 documentation for this alternative solution is included with this application.'),
}
MEASURES = {
    'limiting distance': '1.2 m',
    'storeys': '2',
    'sprinklered': 'no',
    'product thickness': '10 mm',
}
SECTION = {
    'owner_name': 'A', 'representative': 'A', 'mailing_address': 'A', 'application_date': 'A',
    'signature': 'A', 'owner_rep_signature_date': 'A', 'civic_address': 'B', 'legal_description': 'B',
    'lot': 'B', 'block': 'B', 'plan': 'B', 'alternative_description': 'B', 'code_or_standard': 'C',
    'section_c.article': 'C', 'objective': 'C', 'function': 'C', 'section_c.intent': 'C', 'heading': 'C',
    'risk_assessment': 'process', 'mitigating_measures': 'process', 'assumptions_and_limits': 'process',
    'supporting_doc': 'D', 'responsible_party': 'D', 'document_date': 'D', 'engineering_required': 'D',
    'professional_name': 'D', 'professional_qualifications': 'D',
    'division_c_2_3_1': 'B', 'additional_location': 'B',
}


def _defect(field, cls, problem, verdict, planted, original, section):
    return {'field': field, 'class': cls, 'problem': problem, 'verdict': verdict,
            'planted_value': planted, 'original_value': original,
            'location': f'Section {section} / {field}'}


PLANTS = [
    {'id': 'clean-01', 'control': True},
    {'id': 'clean-02', 'control': True, 'set': {
        'owner_name': ('Owner', 'Blake Synthetic'),
        'civic_address': ('Municipal Address', '200 Example Road, Edmonton, Alberta'),
        'mailing_address': ('Mailing Address', '200 Example Road, Edmonton, Alberta'),
    }},
    {'id': 'd01-blank', 'blank': ['owner_name'], 'defects': [
        _defect('owner_name', 'D01', 'blank', 'missing', '', 'Avery Synthetic', 'A')]},
    {'id': 'd01-omitted', 'omit': ['owner_name'], 'defects': [
        _defect('owner_name', 'D01', 'not_found', 'missing', None, 'Avery Synthetic', 'A')]},
    {'id': 'd02-blank-date', 'blank': ['application_date'], 'defects': [
        _defect('application_date', 'D02', 'blank', 'missing', '', '2026-10-20', 'A')]},
    {'id': 'd02-blank-signature-date', 'blank': ['owner_rep_signature_date'], 'defects': [
        _defect('owner_rep_signature_date', 'D02', 'blank', 'missing', '', '2026-10-20', 'A')]},
    {'id': 'd03-blank', 'blank': ['civic_address'], 'defects': [
        _defect('civic_address', 'D03', 'blank', 'missing', '', '100 Example Avenue, Edmonton, Alberta', 'B')]},
    {'id': 'd03-omitted', 'omit': ['civic_address'], 'defects': [
        _defect('civic_address', 'D03', 'not_found', 'missing', None, '100 Example Avenue, Edmonton, Alberta', 'B')]},
    {'id': 'd04-blank', 'blank': ['legal_description', 'lot', 'block', 'plan'], 'defects': [
        _defect('legal_description', 'D04', 'blank', 'missing', '', 'Lot 4 Block 8 Plan 1234567', 'B')]},
    {'id': 'd04-tbd', 'set': {'legal_description': ('', 'TBD')}, 'defects': [
        _defect('legal_description', 'D04', 'placeholder', 'missing', 'TBD', 'Lot 4 Block 8 Plan 1234567', 'B')]},
    {'id': 'd05-fake-a', 'set': {'section_c.article': ('Article(s)', '9.99.99.99.(99)')}, 'defects': [
        _defect('section_c.provision_found', 'D05', 'not_found_in_code', 'missing', '9.99.99.99.(99)', '9.10.15.5.(8)', 'C')]},
    {'id': 'd05-fake-b', 'set': {'section_c.article': ('Article(s)', '9.99.99.98.(1)')}, 'defects': [
        _defect('section_c.provision_found', 'D05', 'not_found_in_code', 'missing', '9.99.99.98.(1)', '9.10.15.5.(8)', 'C')]},
    {'id': 'd06-labelled-2019', 'set': {
        'section_c.article': ('Article(s)', 'NBC(AE) 2019, Div B, Sentence 9.10.15.5.(8)')}, 'defects': [
        _defect('section_c.edition', 'D06', 'superseded_edition', 'unclear', 'NBC(AE) 2019', 'NBC(AE) 2023', 'C')]},
    {'id': 'd06-unlabelled-crosswalk', 'set': {
        'section_c.article': ('Article(s)', '3.1.6.5.(1)'),
        'heading': ('', 'Flame Resistance')}, 'defects': [
        _defect('section_c.edition', 'D06', 'superseded_edition', 'unclear', '3.1.6.5.(1) Flame Resistance',
                'precedent index successor', 'C')]},
    {'id': 'd06-historical', 'set': {
        'section_c.article': ('Article(s)', 'NBC(AE) 2019, Div B, Sentence 9.10.15.5.(8) (historical context)')}},
    {'id': 'd07-wrong-pair-a', 'set': {'objective': ('Objective', 'OS1.2')}, 'defects': [
        _defect('section_c.pair_match', 'D07', 'wrong_pair', 'unclear', 'F03-OS1.2', 'F03-OP3.1', 'C')]},
    {'id': 'd07-wrong-pair-b', 'set': {'function': ('Function', 'F02'), 'objective': ('Objective', 'OP1.1')}, 'defects': [
        _defect('section_c.pair_match', 'D07', 'wrong_pair', 'unclear', 'F02-OP1.1', 'F03-OP3.1', 'C')]},
    {'id': 'd08-alberta-label', 'set': {
        'section_c.intent': ('Intent statement', 'Alberta legal requirement for this sentence.')}, 'defects': [
        _defect('section_c.intent', 'D08', 'intent_label', 'unclear', 'Alberta legal requirement',
                'NBC 2020 Intent Statements, explanatory only', 'C')]},
    {'id': 'd08-unlabelled', 'set': {
        'section_c.intent': ('Intent statement', 'The purpose is to limit fire spread to the neighbour.')}, 'defects': [
        _defect('section_c.intent', 'D08', 'intent_label', 'unclear', 'unlabelled paraphrase',
                'NBC 2020 Intent Statements, explanatory only', 'C')]},
    {'id': 'd09-blank', 'blank': ['risk_assessment'], 'defects': [
        _defect('risk_assessment', 'D09', 'blank', 'missing', '', 'applicant risk text', 'B')]},
    {'id': 'd09-generic', 'set': {'risk_assessment': ('', 'low risk')}, 'defects': [
        _defect('risk_assessment', 'D09', 'generic', 'unclear', 'low risk', 'applicant risk text', 'B')]},
    {'id': 'd10-blank', 'blank': ['mitigating_measures'], 'defects': [
        _defect('mitigating_measures', 'D10', 'blank', 'missing', '', 'applicant measures', 'B')]},
    {'id': 'd10-unrelated', 'set': {'mitigating_measures': ('', 'Paint the mailbox red each spring.')}, 'defects': [
        _defect('mitigating_measures', 'D10', 'unrelated', 'unclear', 'Paint the mailbox red each spring.',
                'applicant measures', 'B')]},
    {'id': 'd11-blank', 'blank': ['assumptions_and_limits'], 'defects': [
        _defect('assumptions_and_limits', 'D11', 'blank', 'missing', '', 'applicant assumptions', 'B')]},
    {'id': 'd11-tbd', 'set': {'assumptions_and_limits': ('', 'TBD')}, 'defects': [
        _defect('assumptions_and_limits', 'D11', 'placeholder', 'missing', 'TBD', 'applicant assumptions', 'B')]},
    {'id': 'd12-unnamed', 'set': {
        'engineering_required': ('', 'yes'), 'professional_qualifications': ('', 'Synthetic stated qualifications')},
     'defects': [_defect('responsible_professional', 'D12', 'professional_unnamed', 'missing', '', 'named professional', 'D')]},
    {'id': 'd12-no-qualifications', 'set': {
        'engineering_required': ('', 'yes'), 'professional_name': ('', 'Jordan Synthetic')},
     'defects': [_defect('professional_qualifications', 'D12', 'qualifications_missing', 'missing', '', 'qualifications', 'D')]},
    {'id': 'd13-no-responsible', 'blank': ['responsible_party'], 'defects': [
        _defect('supporting_doc', 'D13', 'no_responsible', 'missing', '', 'Casey Synthetic, product specialist', 'D')]},
    {'id': 'd13-no-date', 'blank': ['document_date'], 'defects': [
        _defect('supporting_doc', 'D13', 'no_date', 'unclear', '', '2026-10-01', 'D')]},
    {'id': 'd14-distance', 'attachment': {'limiting distance': '3.0 m'}, 'defects': [
        _defect('section_b.consistency', 'D14', 'contradiction', 'unclear', '3.0 m', '1.2 m', 'B')]},
    {'id': 'd14-storeys', 'attachment': {'storeys': '4'}, 'defects': [
        _defect('section_b.consistency', 'D14', 'contradiction', 'unclear', '4', '2', 'B')]},
    {'id': 'd15-stair-on-soffit', 'set': {
        'section_c.article': ('Article(s)', '9.8.2.1.(2)'), 'heading': ('', 'stair width')}, 'defects': [
        _defect('section_c.relevance', 'D15', 'irrelevant', 'unclear', '9.8.2.1.(2)', '9.10.15.5.(8)', 'C')]},
    {'id': 'd15-fire-on-stair', 'set': {
        'section_c.article': ('Article(s)', '9.10.9.16.(1)'),
        'heading': ('', 'fire separation'),
        'alternative_description': ('', 'The exit stair width is narrower than the acceptable stair width for this house.')},
     'defects': [_defect('section_c.relevance', 'D15', 'irrelevant', 'unclear', '9.10.9.16.(1)', 'stair departure', 'C')]},
    {'id': 'd16-blank-row', 'blank': ['section_c.article'], 'defects': [
        _defect('section_c.article', 'D16', 'blank', 'missing', '', '9.10.15.5.(8)', 'C')]},
    {'id': 'd16-omitted-row', 'omit': ['section_c.article'], 'defects': [
        _defect('section_c.article', 'D16', 'not_found', 'missing', None, '9.10.15.5.(8)', 'C')]},
    # IB-2025-11-18: the Division C Section 2.3.1 documentation is absent.
    {'id': 'ib-doc-omitted', 'omit': ['division_c_2_3_1'], 'defects': [
        _defect('division_c_2_3_1', 'IB-DOC', 'not_found', 'missing', None,
                'Division C Section 2.3.1 documentation', 'B')]},
    # IB-2026-10-01: one registration per specific location.
    {'id': 'ib-two-locations', 'set': {
        'additional_location': ('', '200 Example Road, Edmonton, Alberta')}, 'defects': [
        _defect('single_location', 'IB-LOC', 'multiple_locations', 'missing',
                '200 Example Road, Edmonton, Alberta', '100 Example Avenue, Edmonton, Alberta', 'B')]},
]


def _record(plant: dict) -> tuple[dict, dict]:
    values = {key: pair[1] for key, pair in BASE.items()}
    widgets = {key: pair[0] for key, pair in BASE.items()}
    for key, pair in (plant.get('set') or {}).items():
        widgets[key], values[key] = pair
    for key in plant.get('blank') or []:
        values[key] = ''
    for key in plant.get('omit') or []:
        values.pop(key, None)
    attachment = dict(MEASURES)
    attachment.update(plant.get('attachment') or {})
    return {'id': plant['id'], 'values': values, 'widgets': widgets}, attachment


def render_text(record: dict, attachment: dict) -> str:
    lines = [f'# synthetic variance application {record["id"]}', '']
    current = None
    for key, value in record['values'].items():
        section = SECTION.get(key, 'B')
        if section != current:
            lines += ['', f'[section {section}]']
            current = section
        widget = record['widgets'].get(key, '')
        lines.append(f'FIELD | {key} | {widget} | {value}')
        if key == 'alternative_description':
            for name, measure in MEASURES.items():
                lines.append(f'{name}: {measure}')
    lines += ['', '[attachment drawings]']
    for name, measure in attachment.items():
        lines.append(f'{name}: {measure}')
    lines.append('')
    return '\n'.join(lines)


def _pdf(path: Path, text: str, widgets: dict[str, str], flatten: bool) -> None:
    canvas = Canvas(str(path), pagesize=(612, 792), pageCompression=0)
    form = canvas.acroForm
    y = 760
    for line in text.splitlines():
        if y < 40:
            canvas.showPage()
            y = 760
        canvas.setFont('Helvetica', 8)
        canvas.drawString(36, y, line[:110])
        y -= 10
    if not flatten:
        y = 760
        for name, value in widgets.items():
            if not name:
                continue
            form.textfield(name=name, x=400, y=max(40, y), width=180, height=12, value=value or '', fontSize=6, borderWidth=0)
            y -= 14
    canvas.save()


def _gold(plant: dict) -> dict:
    defects = plant.get('defects') or []
    by_field = {item['field']: item for item in defects}
    elements = []
    for spec in ELEMENTS:
        defect = by_field.get(spec.field)
        elements.append({
            'field': spec.field,
            'section': spec.template_section,
            'form_fields': list(spec.form_fields),
            'expected_verdict': defect['verdict'] if defect else 'present',
            'problem': defect['problem'] if defect else None,
            'defect_class': defect['class'] if defect else None,
            'requires_codedb': spec.requires_codedb,
        })
    return {
        'id': plant['id'],
        'author': 'pipeline-implementer',
        'checker_aware': True,
        'control': bool(plant.get('control')),
        'base_case': 'synthetic-clean-form',
        'defects': [{key: value for key, value in defect.items() if key != 'verdict'} | {'expected_verdict': defect['verdict']}
                    for defect in defects],
        'elements': elements,
    }


def main() -> None:
    APPS.mkdir(parents=True, exist_ok=True)
    GOLD.mkdir(parents=True, exist_ok=True)
    for plant in PLANTS:
        record, attachment = _record(plant)
        text = render_text(record, attachment)
        (APPS / f'{plant["id"]}.txt').write_text(text)
        widgets = {}
        for key, value in record['values'].items():
            widget = record['widgets'].get(key) or ''
            if widget:
                widgets[widget] = value
        _pdf(APPS / f'{plant["id"]}.pdf', text, widgets, flatten=False)
        _pdf(APPS / f'{plant["id"]}.flat.pdf', text, {}, flatten=True)
        (GOLD / f'{plant["id"]}.json').write_text(json.dumps(_gold(plant), indent=2) + '\n')
    print(f'wrote {len(PLANTS)} applications to {APPS}')


if __name__ == '__main__':
    main()
